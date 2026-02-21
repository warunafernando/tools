#!/usr/bin/env python3
"""
BLE signal strength diagnostic: report RSSI for SmartBall.
RSSI = Received Signal Strength Indicator (dBm). Typical: -30 excellent, -50 good,
-70 fair, -90 weak, below -90 often unreliable.
Usage: python ble_rssi_diagnostic.py [--timeout 20] [--passes 5]
"""
import asyncio
import argparse
import sys

try:
    from bleak import BleakScanner
except ImportError:
    print("Install bleak: pip install bleak")
    sys.exit(1)


def rssi_level(rssi):
    if rssi is None:
        return "N/A"
    if rssi >= -50:
        return "Excellent"
    if rssi >= -70:
        return "Good"
    if rssi >= -85:
        return "Fair"
    if rssi >= -95:
        return "Weak"
    return "Very weak / unreliable"


async def main():
    ap = argparse.ArgumentParser(description="BLE RSSI diagnostic for SmartBall")
    ap.add_argument("--timeout", type=float, default=15.0, help="Scan timeout per pass (seconds)")
    ap.add_argument("--passes", type=int, default=5, help="Number of scan passes for stats")
    args = ap.parse_args()

    print("BLE Signal Strength Diagnostic")
    print("RSSI (dBm): -30 excellent | -50 good | -70 fair | -85 weak | -90+ unreliable")
    print("-" * 60)

    found_any = False
    rssi_values = []

    for p in range(args.passes):
        devices = await BleakScanner.discover(timeout=args.timeout, return_adv=True)
        for addr, (d, adv) in devices.items():
            if "SmartBall" not in (d.name or ""):
                continue
            rssi = getattr(adv, "rssi", None)
            if rssi is not None:
                rssi_values.append(rssi)
                found_any = True
            level = rssi_level(rssi)
            print(f"Pass {p + 1}/{args.passes}: SmartBall {d.address}  RSSI={rssi} dBm  ({level})")

    if not found_any:
        print("SmartBall not found in any pass.")
        print("Nearby devices with RSSI:")
        devices = await BleakScanner.discover(timeout=args.timeout, return_adv=True)
        for addr, (d, adv) in list(devices.items())[:15]:
            rssi = getattr(adv, "rssi", None)
            print(f"  {d.address}  {d.name or '(no name)'}  RSSI={rssi} dBm")
        sys.exit(1)

    if rssi_values:
        avg = sum(rssi_values) / len(rssi_values)
        mn, mx = min(rssi_values), max(rssi_values)
        print("-" * 60)
        print(f"SmartBall RSSI: min={mn}  avg={avg:.1f}  max={mx}  n={len(rssi_values)}")
        print(f"Level: {rssi_level(int(avg))}")
        if avg < -85:
            print("-> Weak signal may cause connection drops or discovery failure.")
        elif avg < -70:
            print("-> Fair signal; keep device within 1-2m for reliable OTA.")

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
