#!/usr/bin/env python3
"""
Find SmartBall via BLE: scan by name "SmartBall" or probe unnamed devices for NUS.
Usage: python ble_find.py [--timeout 20] [--probe-all]
"""
import asyncio
import argparse
import sys

try:
    from bleak import BleakScanner, BleakClient
except ImportError:
    print("Install bleak: pip install bleak")
    sys.exit(1)

NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"


async def main():
    ap = argparse.ArgumentParser(description="Find SmartBall over BLE")
    ap.add_argument("--timeout", type=float, default=15.0, help="Scan timeout seconds")
    ap.add_argument("--probe-all", action="store_true", help="Probe all unnamed devices for NUS (slower)")
    args = ap.parse_args()

    print(f"Scanning BLE for {args.timeout}s...")
    devices = await BleakScanner.discover(timeout=args.timeout)
    target = next((d for d in devices if "SmartBall" in (d.name or "")), None)

    if target:
        print(f"Found SmartBall by name: {target.address} ({target.name})")
        return

    unnamed = [d for d in devices if not (d.name or "").strip()]
    to_probe = unnamed if args.probe_all else unnamed[:8]
    print(f"SmartBall not in name. Probing {len(to_probe)} unnamed device(s) for NUS...")

    for d in to_probe:
        try:
            async with BleakClient(d.address, timeout=3.0) as client:
                for s in client.services:
                    if s.uuid and NUS_SERVICE.lower() in str(s.uuid).lower():
                        print(f"Found SmartBall by NUS: {d.address} (no name advertised)")
                        return
        except Exception:
            pass

    print("SmartBall not found.")
    print(f"Nearby devices ({len(devices)}):")
    for d in devices[:20]:
        print(f"  {d.address}  {d.name or '(no name)'}")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
