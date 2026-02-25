#!/usr/bin/env python3
"""
Experiment: one long-lived BLE connection for shot download.
Tests multiple delay values and reports time + success.
Usage: BLE_ADDR=XX:XX:... python3 experiment_one_connection.py
       or run with --scan to find SmartBall and use first device.
"""
import asyncio
import os
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
Path(__file__).resolve().parents[2] / ".venv"
_venv = Path(__file__).resolve().parents[2] / ".venv" / "lib" / "python3.11" / "site-packages"
sys.path.insert(0, str(_venv))

from bleak import BleakScanner
from ble_binary_client import (
    make_frame,
    send_binary_cmd_sync,
    fetch_shot_one_connection_sync,
    CMD_LIST_SHOTS,
    RSP_SHOT_LIST,
    FETCH_SHOT_CHUNK_SIZE,
)


def get_addr():
    addr = os.environ.get("BLE_ADDR", "").strip()
    if addr:
        return addr
    print("Scanning 6s for SmartBall...")
    devices = asyncio.run(BleakScanner.discover(timeout=6.0))
    for d in devices:
        if d.name and "SmartBall" in d.name:
            return d.address
        if d.name and "XIAO" in d.name:
            return d.address
    if devices:
        return devices[0].address
    return None


def get_shot_list(addr):
    frame = make_frame(CMD_LIST_SHOTS)
    rsp, err = send_binary_cmd_sync(addr, frame)
    if err or not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT_LIST:
        return None, None
    n = rsp[3]
    shots = []
    for i in range(min(n, 16)):
        if 4 + (i + 1) * 8 <= len(rsp):
            sid = struct.unpack_from("<I", rsp, 4 + i * 8)[0]
            sz = struct.unpack_from("<I", rsp, 4 + i * 8 + 4)[0]
            shots.append((sid, sz))
    return shots, None


def run_one(addr, shot_id, size, delay_sec, chunk_size):
    t0 = time.perf_counter()
    payload, err = fetch_shot_one_connection_sync(
        addr, shot_id, size,
        chunk_size=chunk_size,
        timeout_per_chunk=8.0,
        delay_between_chunks_sec=delay_sec,
    )
    elapsed = time.perf_counter() - t0
    ok = err is None and payload is not None and len(payload) >= size
    if ok and payload and len(payload) >= 8:
        magic = payload[:8].decode("ascii", errors="replace")
        ok = magic == "SVTSHOT3"
    return ok, elapsed, err


def main():
    addr = get_addr()
    if not addr:
        print("No BLE address. Set BLE_ADDR or use --scan (default).")
        return 1
    print(f"Using address: {addr}")

    shots, _ = get_shot_list(addr)
    if not shots:
        print("No shots on device. Record a shot first, or we'll use a fixed size for timing.")
        shot_id, size = 1, 15360
    else:
        shot_id, size = shots[0]
        print(f"First shot: id={shot_id} size={size}")

    # Try chunk sizes: 495 (new FW) and 240 (old FW)
    for chunk_size in (495, 240):
        if chunk_size > size:
            continue
        print(f"\n--- Chunk size {chunk_size} ---")
        for delay in (0.0, 0.02, 0.04, 0.06, 0.10):
            ok, elapsed, err = run_one(addr, shot_id, size, delay, chunk_size)
            status = "OK" if ok else ("FAIL: " + (err or "unknown")[:50])
            print(f"  delay={delay:.2f}s  time={elapsed:.1f}s  {status}")
            if ok and elapsed <= 25:
                print(f"  -> Target 10-20s: {'YES' if elapsed <= 20 else 'close'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
