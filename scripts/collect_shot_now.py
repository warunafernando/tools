#!/usr/bin/env python3
"""
Collect one shot from SmartBall over BLE and print debug (first sample + min/max per channel).
Run when ready to capture; device should already have recorded a shot (or run START_RECORD, move, STOP_RECORD first).
Usage: python3 scripts/collect_shot_now.py <BLE_ADDR>
"""
import asyncio
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".venv" / "lib" / "python3.11" / "site-packages"))

SB_RX_CHAR = "53564231-5342-4c31-8000-000000000002"
SB_TX_CHAR = "53564231-5342-4c31-8000-000000000003"

CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_GET_SHOT_CHUNK = 0x0D, 0x0E, 0x12
RSP_SHOT, RSP_SHOT_LIST = 0x8A, 0x8C
CHUNK_SIZE = 240


def make_frame(cmd: int, payload: bytes | None = None) -> bytes:
    if payload is None:
        payload = b"\x00"
    return struct.pack("<BH", cmd, len(payload)) + payload


async def send_cmd(client, frame: bytes) -> bytes | None:
    rsp = [None]
    def notif(_, data: bytearray):
        rsp[0] = bytes(data)
    await client.start_notify(SB_TX_CHAR, notif)
    await asyncio.sleep(0.2)
    await client.write_gatt_char(SB_RX_CHAR, frame, response=False)
    for _ in range(50):
        await asyncio.sleep(0.1)
        if rsp[0] is not None:
            return rsp[0]
    return None


def parse_svtshot3_full(data: bytes) -> dict | None:
    if len(data) < 24 or data[:8] != b"SVTSHOT3":
        return None
    sample_rate = struct.unpack_from("<H", data, 10)[0]
    count = struct.unpack_from("<I", data, 12)[0]
    imu_mask = data[17]
    sample_size = 68 if (imu_mask & 0x06) else 28
    header_size, footer_size = 24, 4
    if len(data) < header_size + count * sample_size + footer_size:
        return None
    samples = []
    for i in range(count):
        off = header_size + i * sample_size
        t_ms = struct.unpack_from("<I", data, off)[0]
        row = {"t_ms": t_ms}
        if sample_size == 28:
            row["ax"], row["ay"], row["az"] = struct.unpack_from("<fff", data, off + 4)
            row["gx"], row["gy"], row["gz"] = struct.unpack_from("<fff", data, off + 16)
        else:
            row["i_ax"], row["i_ay"], row["i_az"] = struct.unpack_from("<fff", data, off + 8)
            row["i_gx"], row["i_gy"], row["i_gz"] = struct.unpack_from("<fff", data, off + 20)
            row["l_ax"], row["l_ay"], row["l_az"] = struct.unpack_from("<fff", data, off + 32)
            row["l_gx"], row["l_gy"], row["l_gz"] = struct.unpack_from("<fff", data, off + 44)
            row["h_ax"], row["h_ay"], row["h_az"] = struct.unpack_from("<fff", data, off + 56)
        samples.append(row)
    return {"sample_rate": sample_rate, "count": count, "imu_mask": imu_mask, "sample_size": sample_size, "samples": samples}


def min_max(samples, key):
    if not samples or key not in samples[0]:
        return None
    lo = hi = samples[0][key]
    for s in samples[1:]:
        v = s[key]
        if v < lo: lo = v
        if v > hi: hi = v
    return lo, hi


async def main(addr: str):
    from bleak import BleakClient

    print(f"Connecting to {addr}...")
    async with BleakClient(addr) as client:
        rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
        if not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT_LIST:
            print("LIST_SHOTS failed or no response")
            return 1
        n = rsp[3]
        if n == 0:
            print("No shots on device. Start recording, move the setup, stop recording, then run this again.")
            return 1
        sid = struct.unpack_from("<I", rsp, 4)[0]
        sz = struct.unpack_from("<I", rsp, 8)[0]
        print(f"Fetching shot id={sid} size={sz} B...")

        payload = b""
        if sz <= CHUNK_SIZE:
            rsp2 = await send_cmd(client, make_frame(CMD_GET_SHOT, struct.pack("<I", sid)))
            if not rsp2 or rsp2[0] != RSP_SHOT:
                print("GET_SHOT failed")
                return 1
            plen = struct.unpack_from("<H", rsp2, 1)[0]
            payload = rsp2[3:3 + plen]
        else:
            offset = 0
            while offset < sz:
                rsp2 = await send_cmd(client, make_frame(CMD_GET_SHOT_CHUNK, struct.pack("<IH", sid, offset)))
                if not rsp2 or rsp2[0] != RSP_SHOT:
                    print(f"GET_SHOT_CHUNK failed at offset {offset}")
                    return 1
                plen = struct.unpack_from("<H", rsp2, 1)[0]
                payload += rsp2[3:3 + plen]
                offset += plen
                if plen < CHUNK_SIZE:
                    break

        parsed = parse_svtshot3_full(payload)
        if not parsed:
            print("Parse failed")
            return 1

        m = parsed["imu_mask"]
        s0 = parsed["samples"][0]
        print()
        print("--- IMU data check ---")
        print(f"imu_source_mask: 0x{m:02X} (1=Internal, 2=LSM6, 4=ADXL)")
        print(f"Rate: {parsed['sample_rate']} Hz  Samples: {parsed['count']}")
        print()
        print("First sample:")
        if parsed["sample_size"] == 28:
            print(f"  Internal: ax={s0['ax']:.3f} ay={s0['ay']:.3f} az={s0['az']:.3f}  gx={s0['gx']:.4f} gy={s0['gy']:.4f} gz={s0['gz']:.4f}")
        else:
            print(f"  Internal: i_ax={s0['i_ax']:.3f} i_ay={s0['i_ay']:.3f} i_az={s0['i_az']:.3f}  i_gx={s0['i_gx']:.4f} i_gy={s0['i_gy']:.4f} i_gz={s0['i_gz']:.4f}")
            print(f"  IMU (ext): l_ax={s0['l_ax']:.3f} l_ay={s0['l_ay']:.3f} l_az={s0['l_az']:.3f}  l_gx={s0['l_gx']:.4f} l_gy={s0['l_gy']:.4f} l_gz={s0['l_gz']:.4f}")
            print(f"  Impact:   h_ax={s0['h_ax']:.3f} h_ay={s0['h_ay']:.3f} h_az={s0['h_az']:.3f}")
        print()
        print("Min / Max:")
        for key in ("i_ax", "i_ay", "i_az", "i_gx", "i_gy", "i_gz") if parsed["sample_size"] == 68 else ("ax", "ay", "az", "gx", "gy", "gz"):
            r = min_max(parsed["samples"], key)
            if r:
                tag = " (all zero)" if r[0] == r[1] and r[0] == 0 else " (constant)" if r[0] == r[1] else ""
                print(f"  {key}: {r[0]:.4f} / {r[1]:.4f}{tag}")
        if parsed["sample_size"] == 68:
            for key in ("l_ax", "l_ay", "l_az", "l_gx", "l_gy", "l_gz", "h_ax", "h_ay", "h_az"):
                r = min_max(parsed["samples"], key)
                if r:
                    tag = " (all zero)" if r[0] == r[1] and r[0] == 0 else " (constant)" if r[0] == r[1] else ""
                    print(f"  {key}: {r[0]:.4f} / {r[1]:.4f}{tag}")
        print()
    return 0


if __name__ == "__main__":
    addr = sys.argv[1] if len(sys.argv) > 1 else None
    if not addr:
        print("Usage: python3 collect_shot_now.py <BLE_ADDR>")
        print("Example: python3 collect_shot_now.py D0:8D:27:9F:56:14")
        sys.exit(1)
    sys.exit(asyncio.run(main(addr)))
