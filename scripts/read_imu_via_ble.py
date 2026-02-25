#!/usr/bin/env python3
"""
Read external IMU (LSM6 cs=0, ADXL cs=1) over BLE using CMD_SPI_READ.
Use when recording shows no external IMU data - this checks if the chips respond on SPI.

Usage:
  python3 scripts/read_imu_via_ble.py [BLE_ADDR]
  If BLE_ADDR omitted, scans for SmartBall.

Requires: bleak (pip install bleak). Run from repo root or set PYTHONPATH.
"""
import sys
import asyncio
from pathlib import Path

# Add web_gui for ble_binary_client
TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS / "msr1_ota" / "web_gui"))

def main():
    addr = sys.argv[1] if len(sys.argv) > 1 else None
    if not addr:
        # Quick scan for SmartBall
        try:
            from bleak import BleakScanner
            print("Scanning for SmartBall (5s)...")
            devs = asyncio.run(BleakScanner.discover(timeout=5.0))
            for d in devs:
                if d.name and "SmartBall" in d.name:
                    addr = d.address
                    print(f"Found: {addr}")
                    break
                if d.name and "smartball" in (d.name or "").lower():
                    addr = d.address
                    print(f"Found: {addr}")
                    break
            if not addr and devs:
                # Use first with no name or random
                for d in devs:
                    if d.address:
                        addr = d.address
                        print(f"Using first device: {addr}")
                        break
        except Exception as e:
            print(f"Scan failed: {e}")
            sys.exit(1)
    if not addr:
        print("No BLE address. Usage: read_imu_via_ble.py [BLE_ADDR]")
        sys.exit(1)

    from ble_binary_client import spi_read_sync

    checks = [
        ("LSM6 WHO_AM_I (0x0F)", 0, 0x0F, 1, "0x6C/0x6A/0x69 = OK"),
        ("LSM6 CTRL1_XL (0x10)", 0, 0x10, 1, ""),
        ("LSM6 accel (0x28)", 0, 0x28, 6, "AX_L..AZ_H"),
        ("LSM6 gyro (0x22)", 0, 0x22, 6, "GX_L..GZ_H"),
        ("ADXL DEVID (0x00)", 1, 0x00, 1, "0xE5 = OK"),
        ("ADXL DATA (0x32)", 1, 0x32, 6, "X,Y,Z"),
    ]
    print(f"Reading external IMU over BLE ({addr})...\n")
    all_ok = True
    for name, cs, reg, length, hint in checks:
        data, err = spi_read_sync(addr, cs, reg, length)
        if err:
            print(f"  {name}: FAILED — {err}")
            all_ok = False
        else:
            hex_str = " ".join(f"{b:02X}" for b in data) if data else ""
            print(f"  {name}: {hex_str}  {hint}")
    print()
    if all_ok:
        print("All reads OK. If recording still shows no external IMU, check multi_imu init/sample_fetch.")
    else:
        print("Some reads failed. Check SPI wiring (SCK/MOSI/MISO/CS), power, CS pins (LSM6=0, ADXL=1).")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
