#!/usr/bin/env python3
"""
Compare Internal IMU vs external IMU (LSM6) from shot data. Ignores impact detector (ADXL).

Input: shot data as raw hex (SVTSHOT3). Get it by:
  - Fetch from device: python3 compare_internal_vs_imu.py --fetch BLE_ADDR [shot_id]
  - Load saved:        python3 compare_internal_vs_imu.py --file msr1_ota/web_gui/saved_shots/<id>.json
  - Pipe hex:          python3 compare_internal_vs_imu.py < hex.txt
  - As argument:       python3 compare_internal_vs_imu.py <hex_string>

Requires: bleak (for --fetch). Run from repo root.
"""
import sys
import struct
import json
import argparse
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "msr1_ota" / "web_gui"))

HEADER_SIZE = 24
FOOTER_SIZE = 4


def parse_svtshot3(raw: bytes):
    if len(raw) < HEADER_SIZE + 4:
        return None
    if raw[:8] != b"SVTSHOT3":
        return None
    sample_rate = struct.unpack_from("<H", raw, 10)[0]
    count = struct.unpack_from("<I", raw, 12)[0]
    imu_mask = raw[17]
    sample_size = 68 if (imu_mask & 0x06) else 28  # LSM6=2 or ADXL=4
    expected = HEADER_SIZE + count * sample_size + FOOTER_SIZE
    if len(raw) < expected:
        return None
    samples = []
    for i in range(count):
        off = HEADER_SIZE + i * sample_size
        t_ms = struct.unpack_from("<I", raw, off)[0]
        s = {"t_ms": t_ms}
        if sample_size == 28:
            s["ax"], s["ay"], s["az"] = struct.unpack_from("<fff", raw, off + 4)
            s["gx"], s["gy"], s["gz"] = struct.unpack_from("<fff", raw, off + 16)
        else:
            s["i_ax"], s["i_ay"], s["i_az"] = struct.unpack_from("<fff", raw, off + 8)
            s["i_gx"], s["i_gy"], s["i_gz"] = struct.unpack_from("<fff", raw, off + 20)
            if sample_size == 68:
                s["l_ax"], s["l_ay"], s["l_az"] = struct.unpack_from("<fff", raw, off + 32)
                s["l_gx"], s["l_gy"], s["l_gz"] = struct.unpack_from("<fff", raw, off + 44)
        samples.append(s)
    return {
        "sample_rate": sample_rate,
        "count": count,
        "imu_mask": imu_mask,
        "sample_size": sample_size,
        "samples": samples,
    }


def stats(arr, key):
    vals = [s[key] for s in arr if key in s and s[key] is not None]
    if not vals:
        return None
    return {
        "first": vals[0],
        "min": min(vals),
        "max": max(vals),
        "mean": sum(vals) / len(vals),
    }


def main():
    ap = argparse.ArgumentParser(description="Compare Internal IMU vs LSM6 (ignore impact)")
    ap.add_argument("--fetch", metavar="ADDR", help="Fetch shot from device (optional shot_id as next arg)")
    ap.add_argument("--file", metavar="PATH", help="Load shot from saved JSON file")
    ap.add_argument("hex_input", nargs="?", help="Raw hex string of SVTSHOT3 payload")
    args = ap.parse_args()

    raw_hex = None
    if args.fetch:
        addr = args.fetch
        shot_id = None
        if args.hex_input and args.hex_input.isdigit():
            shot_id = int(args.hex_input)
        from ble_binary_client import make_frame, send_binary_cmd_sync, CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_GET_SHOT_CHUNK, RSP_SHOT, RSP_SHOT_LIST
        import struct
        # Get shot list if no shot_id
        if shot_id is None:
            frame = make_frame(CMD_LIST_SHOTS, payload=b"\x00")
            rsp, err = send_binary_cmd_sync(addr, frame)
            if err or not rsp or rsp[0] != 0x8C:
                print("List shots failed:", err or "no response")
                sys.exit(1)
            n = rsp[3]
            if n == 0:
                print("No shots on device. Record a shot first.")
                sys.exit(1)
            shot_id = struct.unpack_from("<I", rsp, 4)[0]
            size = struct.unpack_from("<I", rsp, 8)[0]
        else:
            frame = make_frame(CMD_LIST_SHOTS, payload=b"\x00")
            rsp, err = send_binary_cmd_sync(addr, frame)
            if err or not rsp:
                print("List failed:", err)
                sys.exit(1)
            n = rsp[3]
            size = 0
            for i in range(n):
                sid = struct.unpack_from("<I", rsp, 4 + i * 8)[0]
                sz = struct.unpack_from("<I", rsp, 4 + i * 8 + 4)[0]
                if sid == shot_id:
                    size = sz
                    break
            if size == 0:
                print("Shot id", shot_id, "not found")
                sys.exit(1)
        CHUNK = 240
        payload = b""
        offset = 0
        while offset < size:
            frame = make_frame(CMD_GET_SHOT_CHUNK, payload=struct.pack("<IH", shot_id, offset))
            rsp, err = send_binary_cmd_sync(addr, frame)
            if err or not rsp or rsp[0] != RSP_SHOT:
                print("Chunk failed:", err)
                sys.exit(1)
            plen = struct.unpack_from("<H", rsp, 1)[0]
            payload += rsp[3:3 + plen]
            offset += plen
            if plen < CHUNK:
                break
        raw_hex = payload.hex()
    elif args.file:
        p = Path(args.file)
        if not p.is_file():
            print("File not found:", p)
            sys.exit(1)
        with open(p) as f:
            data = json.load(f)
        raw_hex = data.get("raw_hex") or data.get("payload_hex")
        if not raw_hex:
            print("No raw_hex in file")
            sys.exit(1)
    elif args.hex_input:
        raw_hex = args.hex_input.replace(" ", "").strip()
    else:
        raw_hex = sys.stdin.read().replace(" ", "").replace("\n", "").strip()

    if not raw_hex:
        ap.print_help()
        sys.exit(1)

    try:
        raw = bytes.fromhex(raw_hex)
    except ValueError:
        print("Invalid hex")
        sys.exit(1)

    parsed = parse_svtshot3(raw)
    if not parsed:
        print("Invalid or truncated SVTSHOT3")
        sys.exit(1)

    samples = parsed["samples"]
    rate = parsed["sample_rate"]
    mask = parsed["imu_mask"]
    sample_size = parsed["sample_size"]

    print(f"Shot: {len(samples)} samples @ {rate} Hz  imu_source_mask=0x{mask:X} (1=Internal 2=LSM6 4=ADXL)")
    if sample_size != 68:
        print("Not multi-IMU (68-byte samples). Only internal or single IMU present.")
        if sample_size == 28 and samples:
            s0 = samples[0]
            print("  Internal: ax={:.4f} ay={:.4f} az={:.4f}  gx={:.5f} gy={:.5f} gz={:.5f}".format(
                s0.get("ax", 0), s0.get("ay", 0), s0.get("az", 0),
                s0.get("gx", 0), s0.get("gy", 0), s0.get("gz", 0)))
        sys.exit(0)

    if not (mask & 2):
        print("LSM6 not in mask; no external IMU data to compare.")
        sys.exit(0)

    # Compare Internal vs LSM6 only (ignore h_*)
    axes = [
        ("Accel X", "i_ax", "l_ax", "m/s²"),
        ("Accel Y", "i_ay", "l_ay", "m/s²"),
        ("Accel Z", "i_az", "l_az", "m/s²"),
        ("Gyro X", "i_gx", "l_gx", "rad/s"),
        ("Gyro Y", "i_gy", "l_gy", "rad/s"),
        ("Gyro Z", "i_gz", "l_gz", "rad/s"),
    ]
    print()
    print("Internal IMU vs IMU (LSM6) — impact detector ignored")
    print("-" * 72)
    print(f"{'Axis':<10} {'Internal (first/min/max/mean)':<32} {'IMU (first/min/max/mean)':<28} {'Diff mean':<10}")
    print("-" * 72)

    for label, ik, lk, unit in axes:
        si = stats(samples, ik)
        sl = stats(samples, lk)
        if si is None and sl is None:
            continue
        internal_str = ""
        if si:
            internal_str = f"{si['first']:.4f}  {si['min']:.4f}/{si['max']:.4f}  μ={si['mean']:.4f}"
        imu_str = ""
        if sl:
            imu_str = f"{sl['first']:.4f}  {sl['min']:.4f}/{sl['max']:.4f}  μ={sl['mean']:.4f}"
        diff_str = ""
        if si and sl:
            diff_str = f"{si['mean'] - sl['mean']:.4f}"
        print(f"{label:<10} {internal_str:<32} {imu_str:<28} {diff_str:<10}")

    print("-" * 72)
    print("(Units: accel m/s², gyro rad/s)")


if __name__ == "__main__":
    main()
