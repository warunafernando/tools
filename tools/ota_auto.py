#!/usr/bin/env python3
"""
SmartBall OTA: try BLE first; on failure fall back to Serial.
Usage: python ota_auto.py <firmware.bin> [version] [--serial-port COM16]
"""
import sys
import asyncio
import subprocess
import argparse
from pathlib import Path

try:
    from bleak import BleakScanner
except ImportError:
    BleakScanner = None

SCRIPT_DIR = Path(__file__).resolve().parent


def find_serial_port():
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            if "USB" in (p.description or "") and "Serial" in (p.description or ""):
                return p.device
            if "nRF" in (p.description or "") or "XIAO" in (p.description or ""):
                return p.device
        for p in serial.tools.list_ports.comports():
            if "Bluetooth" not in (p.description or ""):
                return p.device
    except Exception:
        pass
    return None


def run_ble_ota(path, version):
    return subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "ota_ble.py"), path, str(version)],
        cwd=str(SCRIPT_DIR),
        timeout=600,
    )


def run_serial_ota(path, version, port):
    if not port:
        port = find_serial_port()
        if not port:
            print("No serial port found for fallback.")
            return 1
        print(f"Using serial port: {port}")
    return subprocess.run(
        [sys.executable, str(SCRIPT_DIR / "ota_serial.py"), port, path, str(version)],
        cwd=str(SCRIPT_DIR),
        timeout=300,
    )


async def try_ble_first(path, version):
    if BleakScanner is None:
        return False
    try:
        devices = await BleakScanner.discover(timeout=8.0)
        if any("SmartBall" in (d.name or "") for d in devices):
            return True
    except Exception:
        pass
    return False


def main():
    ap = argparse.ArgumentParser(description="OTA: BLE first, then Serial fallback")
    ap.add_argument("firmware", help="firmware.bin path")
    ap.add_argument("version", nargs="?", type=int, default=1, help="OTA version (default 1)")
    ap.add_argument("--serial-port", default=None, help="COM port for Serial fallback (e.g. COM16)")
    args = ap.parse_args()

    path = Path(args.firmware)
    if not path.is_file():
        path = SCRIPT_DIR / args.firmware
    if not path.is_file():
        print(f"Firmware not found: {args.firmware}")
        sys.exit(1)

    use_ble = asyncio.run(try_ble_first(str(path), args.version))

    if use_ble:
        print("SmartBall found via BLE. Starting BLE OTA...")
        ret = run_ble_ota(str(path), args.version)
        if ret.returncode == 0:
            sys.exit(0)
        print("BLE OTA failed. Falling back to Serial OTA...")
    else:
        print("SmartBall not found via BLE. Using Serial OTA (connect device via USB).")

    ret = run_serial_ota(str(path), args.version, args.serial_port)
    sys.exit(ret.returncode)


if __name__ == "__main__":
    main()
