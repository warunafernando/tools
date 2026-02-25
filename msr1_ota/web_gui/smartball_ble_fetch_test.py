#!/usr/bin/env python3
"""
SmartBall BLE fetch test: known test shot (0xAAAAAAAA, 15360 bytes) on device.
Tests one-connection and per-connection methods multiple times, verifies against known file.
Usage: BLE_ADDR=XX:XX:... python3 smartball_ble_fetch_test.py
       or run without BLE_ADDR to scan for SmartBall.
"""
import asyncio
import os
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_venv = Path(__file__).resolve().parents[2] / ".venv" / "lib" / "python3.11" / "site-packages"
sys.path.insert(0, str(_venv))

from bleak import BleakScanner
from ble_binary_client import (
    make_frame,
    send_binary_cmd_sync,
    fetch_shot_one_connection_sync,
    fetch_shot_chunked_sync,
    CMD_LIST_SHOTS,
    RSP_SHOT_LIST,
    FETCH_SHOT_CHUNK_SIZE,
    _is_disconnect_error,
)

TEST_SHOT_ID = 0xAAAAAAAA
TEST_SHOT_SIZE = 15360


def build_expected_test_shot():
    """Same content as firmware test_shot_byte_at / test_shot_fill."""
    out = bytearray(TEST_SHOT_SIZE)
    out[0:8] = b"SVTSHOT3"
    out[8:24] = bytes([0x01, 0x00, 0x64, 0x00, 0x23, 0x02, 0x00, 0x00,
                      0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    for i in range(24, TEST_SHOT_SIZE - 4):
        out[i] = ((i * 31) & 0xFF)
    for i in range(TEST_SHOT_SIZE - 4, TEST_SHOT_SIZE):
        out[i] = i & 0xFF
    return bytes(out)


EXPECTED_TEST_SHOT = build_expected_test_shot()


def get_addr():
    addr = os.environ.get("BLE_ADDR", "").strip()
    if addr:
        return addr
    print("Scanning 8s for SmartBall...")
    devices = asyncio.run(BleakScanner.discover(timeout=8.0))
    for d in devices:
        if d.name and ("SmartBall" in d.name or "XIAO" in d.name):
            return d.address
    if devices:
        return devices[0].address
    return None


def get_shot_list(addr):
    frame = make_frame(CMD_LIST_SHOTS)
    rsp, err = send_binary_cmd_sync(addr, frame)
    if err or not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT_LIST:
        return [], err or "no list"
    n = rsp[3]
    shots = []
    for i in range(min(n, 32)):
        if 4 + (i + 1) * 8 <= len(rsp):
            sid = struct.unpack_from("<I", rsp, 4 + i * 8)[0]
            sz = struct.unpack_from("<I", rsp, 4 + i * 8 + 4)[0]
            shots.append((sid, sz))
    return shots, None


def ensure_test_shot_in_list(addr, timing_only=False):
    """Get shot list. If timing_only, use first shot; else require test shot first."""
    shots, err = get_shot_list(addr)
    if err or not shots:
        return None, None, err or "list empty"
    sid, sz = shots[0]
    if timing_only:
        return sid, sz, None
    if sid != TEST_SHOT_ID or sz != TEST_SHOT_SIZE:
        return None, None, (
            f"first shot id={sid} size={sz} (expected test shot {TEST_SHOT_ID} {TEST_SHOT_SIZE}). "
            "Flash FW with test shot, or run with --timing-only to use first shot for timing."
        )
    return TEST_SHOT_ID, TEST_SHOT_SIZE, None


def verify_payload(payload, label, expected_size, expect_known_content=True):
    if not payload or len(payload) < expected_size:
        return False, f"{label}: len={len(payload) if payload else 0} expected >={expected_size}"
    if payload[:8] != b"SVTSHOT3":
        return False, f"{label}: bad magic {payload[:8]!r}"
    if expect_known_content and expected_size == TEST_SHOT_SIZE:
        if len(payload) < TEST_SHOT_SIZE or payload[:TEST_SHOT_SIZE] != EXPECTED_TEST_SHOT:
            for i in range(min(TEST_SHOT_SIZE, len(payload))):
                if payload[i] != EXPECTED_TEST_SHOT[i]:
                    return False, f"{label}: first mismatch at offset {i}"
            return False, f"{label}: length/compare fail"
    return True, None


def run_one_connection(addr, shot_id, size, delay_sec, chunk_size, run_num, expect_known):
    t0 = time.perf_counter()
    payload, err = fetch_shot_one_connection_sync(
        addr, shot_id, size,
        chunk_size=chunk_size,
        timeout_per_chunk=10.0,
        delay_between_chunks_sec=delay_sec,
    )
    elapsed = time.perf_counter() - t0
    ok, msg = verify_payload(payload, f"one_conn d={delay_sec} run={run_num}", size, expect_known)
    return ok, elapsed, err, msg


def run_per_connection(addr, shot_id, size, run_num, expect_known):
    """Per-connection (chunked) fetch with 240-byte chunks."""
    t0 = time.perf_counter()
    payload, err = fetch_shot_chunked_sync(
        addr, shot_id, size,
        chunk_size=240,
        timeout_per_chunk=8.0,
        between_segment_callback=None,
    )
    elapsed = time.perf_counter() - t0
    ok, msg = verify_payload(payload, f"per_conn run={run_num}", size, expect_known)
    return ok, elapsed, err, msg


def main():
    argv = sys.argv[1:]
    timing_only = "--timing-only" in argv
    runs_240 = 3
    if "--runs" in argv:
        i = argv.index("--runs")
        if i + 1 < len(argv):
            try:
                runs_240 = int(argv[i + 1])
            except ValueError:
                pass
    addr = get_addr()
    if not addr:
        print("No BLE address. Set BLE_ADDR or ensure SmartBall is advertising.")
        return 1
    print(f"Address: {addr}")
    shot_id, size, err = ensure_test_shot_in_list(addr, timing_only=timing_only)
    if err:
        print(f"Error: {err}")
        return 1
    expect_known = (shot_id == TEST_SHOT_ID and size == TEST_SHOT_SIZE)
    if expect_known:
        print(f"Test shot: id=0x{TEST_SHOT_ID:08X} size={TEST_SHOT_SIZE} (verify known content)")
    else:
        print(f"First shot: id={shot_id} size={size} (timing only, no content verify)")
    print()

    runs_per_method = 2 if timing_only else 3
    results = []
    sys.stdout.flush()

    # One-connection with various delays (chunk 495)
    print("--- One connection, chunk=495 ---")
    sys.stdout.flush()
    for delay in (0.0, 0.04, 0.10):
        for r in range(runs_per_method):
            ok, elapsed, err, msg = run_one_connection(addr, shot_id, size, delay, 495, r + 1, expect_known)
            results.append(("one_conn_495", delay, r, ok, elapsed, err, msg))
            status = "PASS" if ok else f"FAIL {msg or err}"
            print(f"  delay={delay:.2f}s run={r+1}: {elapsed:.1f}s  {status}")
            if not ok and err:
                print(f"    err: {err}")

    # One-connection with chunk=240 (older FW style)
    print(f"\n--- One connection, chunk=240 ({runs_240} runs) ---")
    sys.stdout.flush()
    for delay in (0.04,):
        for r in range(runs_240):
            ok, elapsed, err, msg = run_one_connection(addr, shot_id, size, delay, 240, r + 1, expect_known)
            results.append(("one_conn_240", delay, r, ok, elapsed, err, msg))
            status = "PASS" if ok else f"FAIL {msg or err}"
            print(f"  delay={delay:.2f}s run={r+1}: {elapsed:.1f}s  {status}")

    # Per-connection (chunked, 240)
    print("\n--- Per-connection (chunked 240) ---")
    sys.stdout.flush()
    for r in range(runs_per_method):
        ok, elapsed, err, msg = run_per_connection(addr, shot_id, size, r + 1, expect_known)
        results.append(("per_conn_240", None, r, ok, elapsed, err, msg))
        status = "PASS" if ok else f"FAIL {msg or err}"
        print(f"  run={r+1}: {elapsed:.1f}s  {status}")

    # Summary
    passed = sum(1 for r in results if r[3])
    total = len(results)
    print(f"\n--- Summary: {passed}/{total} passed ---")
    one_ok = [r for r in results if r[0].startswith("one_conn") and r[3]]
    if one_ok:
        times = [r[4] for r in one_ok]
        print(f"One-connection: min={min(times):.1f}s max={max(times):.1f}s (target 10-20s)")
    per_ok = [r for r in results if r[0] == "per_conn_240" and r[3]]
    if per_ok:
        times = [r[4] for r in per_ok]
        print(f"Per-connection:  min={min(times):.1f}s max={max(times):.1f}s")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
