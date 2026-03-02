#!/usr/bin/env python3
"""Test WiFi binary protocol: connect to device AP, then LIST_SHOTS and fetch test shot."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "msr1_ota" / "web_gui"))
from wifi_binary_client import DEFAULT_DEVICE_URL, get_shot_list, fetch_shot_chunked_sync

def main():
    url = DEFAULT_DEVICE_URL
    print(f"Device URL: {url}")
    print("Listing shots...")
    shots, err = get_shot_list(url)
    if err:
        print(f"FAIL: {err}")
        return 1
    if not shots:
        print("FAIL: no shots")
        return 1
    print(f"Shots: {shots}")
    shot_id, size = shots[0]
    print(f"Fetching shot 0x{shot_id:08X} ({size} bytes)...")
    payload, err = fetch_shot_chunked_sync(url, shot_id, size)
    if err:
        print(f"FAIL: {err}")
        return 1
    ok = payload and len(payload) >= 8 and payload[:8] == b"SVTSHOT3"
    print(f"PASS: got {len(payload)} bytes, valid={ok}")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
