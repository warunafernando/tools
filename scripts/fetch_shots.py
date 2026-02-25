#!/usr/bin/env python3
"""Fetch shot data from SmartBall over BLE and list samples."""
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


def parse_svtshot3(data: bytes) -> dict | None:
    if len(data) < 24:
        return None
    if data[:8] != b"SVTSHOT3":
        return None
    sample_rate = struct.unpack_from("<H", data, 10)[0]
    count = struct.unpack_from("<I", data, 12)[0]
    imu_mask = data[17]
    sample_size = 68 if (imu_mask & 0x06) else 28
    # Packed header is 24 bytes (magic8+ver1+pad1+rate2+count4+mask1+mask1+pad2+crc4)
    header_size, footer_size = 24, 4
    if len(data) < header_size + count * sample_size + footer_size:
        return None
    samples = []
    for i in range(count):
        off = header_size + i * sample_size
        t_ms = struct.unpack_from("<I", data, off)[0]
        row = {"t_ms": t_ms, "t_s": t_ms / 1000.0}
        if sample_size == 28:
            ax, ay, az = struct.unpack_from("<fff", data, off + 4)
            gx, gy, gz = struct.unpack_from("<fff", data, off + 16)
            row["ax"], row["ay"], row["az"] = ax, ay, az
            row["gx"], row["gy"], row["gz"] = gx, gy, gz
        else:
            i_ax, i_ay, i_az = struct.unpack_from("<fff", data, off + 8)
            i_gx, i_gy, i_gz = struct.unpack_from("<fff", data, off + 20)
            row["i_ax"], row["i_ay"], row["i_az"] = i_ax, i_ay, i_az
            row["i_gx"], row["i_gy"], row["i_gz"] = i_gx, i_gy, i_gz
        samples.append(row)
    return {"sample_rate": sample_rate, "count": count, "imu_mask": imu_mask, "sample_size": sample_size, "samples": samples}


async def main(addr: str):
    from bleak import BleakClient

    print(f"Connecting to {addr}...")
    async with BleakClient(addr) as client:
        rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
        if not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT_LIST:
            print("LIST_SHOTS failed or no response")
            return 1
        n = rsp[3]
        shots = []
        for i in range(n):
            off = 4 + i * 8
            if off + 8 > len(rsp):
                break
            sid = struct.unpack_from("<I", rsp, off)[0]
            sz = struct.unpack_from("<I", rsp, off + 4)[0]
            shots.append((sid, sz))
        print(f"Found {n} shot(s)\n")

        for sid, sz in shots:
            print("=" * 60)
            print(f"Shot ID {sid}  size={sz} B")
            payload = b""
            if sz <= CHUNK_SIZE:
                rsp2 = await send_cmd(client, make_frame(CMD_GET_SHOT, struct.pack("<I", sid)))
                if not rsp2 or len(rsp2) < 4 or rsp2[0] != RSP_SHOT:
                    print("  GET_SHOT failed")
                    continue
                plen = struct.unpack_from("<H", rsp2, 1)[0]
                payload = rsp2[3 : 3 + plen]
            else:
                offset = 0
                while offset < sz:
                    rsp2 = await send_cmd(client, make_frame(CMD_GET_SHOT_CHUNK, struct.pack("<IH", sid, offset)))
                    if not rsp2 or len(rsp2) < 4 or rsp2[0] != RSP_SHOT:
                        print(f"  GET_SHOT_CHUNK failed at offset {offset}")
                        break
                    plen = struct.unpack_from("<H", rsp2, 1)[0]
                    payload += rsp2[3 : 3 + plen]
                    offset += plen
                    if plen < CHUNK_SIZE:
                        break
            if len(payload) < sz:
                print("  Incomplete fetch")
                continue
            parsed = parse_svtshot3(payload)
            if not parsed:
                print("  Parse failed")
                continue
            print(f"  Rate: {parsed['sample_rate']} Hz | Samples: {parsed['count']} | Size: {parsed['sample_size']} B/sample")
            print()
            # Table header
            if parsed["sample_size"] == 28:
                print("  #     t_ms   t(s)      ax      ay      az      gx      gy      gz")
            else:
                print("  #     t_ms   t(s)   i_ax   i_ay   i_az   i_gx   i_gy   i_gz")
            print("  " + "-" * 70)
            for i, s in enumerate(parsed["samples"]):
                if parsed["sample_size"] == 28:
                    print(f"  {i:3d}  {s['t_ms']:6d}  {s['t_s']:.3f}  {s['ax']:7.2f} {s['ay']:7.2f} {s['az']:7.2f}  {s['gx']:7.3f} {s['gy']:7.3f} {s['gz']:7.3f}")
                else:
                    print(f"  {i:3d}  {s['t_ms']:6d}  {s['t_s']:.3f}  {s['i_ax']:6.2f} {s['i_ay']:6.2f} {s['i_az']:6.2f}  {s['i_gx']:6.3f} {s['i_gy']:6.3f} {s['i_gz']:6.3f}")
            print()
    return 0


if __name__ == "__main__":
    addr = sys.argv[1] if len(sys.argv) > 1 else None
    if not addr:
        print("Usage: python fetch_shots.py <BLE_ADDRESS>")
        print("Example: python fetch_shots.py D0:8D:27:9F:56:14")
        sys.exit(1)
    sys.exit(asyncio.run(main(addr)))
