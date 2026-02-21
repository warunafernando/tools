#!/usr/bin/env python3
"""
Monitor SmartBall BLE visibility; log when it appears/disappears.
Usage: python ble_watch.py [--interval 10] [--timeout 8]
"""
import argparse
import asyncio
import sys
import time

try:
    from bleak import BleakScanner
except ImportError:
    print("Install bleak: pip install bleak")
    sys.exit(1)


def ts():
    return time.strftime("%H:%M:%S", time.localtime())


async def scan_once(timeout: float):
    devices = await BleakScanner.discover(timeout=timeout)
    return next((d for d in devices if "SmartBall" in (d.name or "")), None)


async def main():
    ap = argparse.ArgumentParser(description="Monitor SmartBall BLE visibility")
    ap.add_argument("--interval", type=float, default=10.0, help="Seconds between scans")
    ap.add_argument("--timeout", type=float, default=8.0, help="BLE scan timeout per run")
    ap.add_argument("--duration", type=float, default=0, help="Stop after N seconds (0 = run forever)")
    args = ap.parse_args()

    last_seen = None
    last_lost = None
    start = time.time()
    print(f"[{ts()}] Watching for SmartBall (scan every {args.interval}s, timeout {args.timeout}s)...")
    if args.duration > 0:
        print(f"[{ts()}] Will run for {args.duration:.0f}s")
    print("-" * 50)

    while True:
        if args.duration > 0 and (time.time() - start) >= args.duration:
            print(f"[{ts()}] Duration reached, stopping.")
            break
        try:
            target = await scan_once(args.timeout)
            if target:
                if last_seen is None or last_lost is not None:
                    print(f"[{ts()}] FOUND  {target.address} ({target.name})")
                last_seen = time.time()
                last_lost = None
            else:
                if last_seen is not None and last_lost is None:
                    last_lost = time.time()
                    age = last_lost - last_seen if last_seen else 0
                    print(f"[{ts()}] LOST   (was visible for {age:.0f}s)")
                elif last_lost is not None:
                    print(f"[{ts()}] absent")
                else:
                    print(f"[{ts()}] not seen yet")
        except KeyboardInterrupt:
            print(f"\n[{ts()}] Stopped.")
            break
        except Exception as e:
            print(f"[{ts()}] scan error: {e}")
        await asyncio.sleep(args.interval)


if __name__ == "__main__":
    asyncio.run(main())
