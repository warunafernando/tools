#!/usr/bin/env python3
"""
Reset XIAO via serial (DTR toggle + 1200 baud) then verify BLE communication.
- Ensures serial port is writable (e.g. chmod 666 /dev/ttyACM0 if needed).
- After reset, waits --boot-wait seconds then runs ble_find.py (--probe-all)
  and ble_test.py. If SmartBall is not found, BLE may be off when USB is
  connected (see BLE_Failure_Investigation_USB_Connected.md; firmware needs USE_LFSYNT).

Usage: python reset_and_check_ble.py [--port /dev/ttyACM0] [--boot-wait 8]
       python reset_and_check_ble.py --skip-reset   # BLE check only
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


def reset_via_serial(port: str) -> bool:
    """Reset the board: DTR toggle (nRF52/PlatformIO) then 1200 baud touch (Arduino-style)."""
    try:
        import serial
    except ImportError:
        print("Install pyserial: pip install pyserial")
        return False
    try:
        # 1) DTR toggle - resets many nRF52/PlatformIO boards
        ser = serial.Serial(port, 115200)
        ser.setDTR(False)
        time.sleep(0.1)
        ser.setDTR(True)
        time.sleep(0.1)
        ser.close()
        time.sleep(0.3)
        # 2) 1200 baud open/close - triggers bootloader/reset on many Arduino boards
        try:
            s = serial.Serial(port, 1200)
            s.close()
        except Exception:
            pass
        print(f"Reset sent on {port} (DTR + 1200 baud)")
        return True
    except Exception as e:
        print(f"Serial reset failed: {e}")
        return False


async def check_ble(timeout: float = 15.0, probe_all: bool = True) -> bool:
    """Run ble_find to verify SmartBall is advertising."""
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "ble_find.py"),
        "--timeout", str(timeout),
    ]
    if probe_all:
        cmd.append("--probe-all")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(SCRIPT_DIR),
    )
    stdout, _ = await proc.communicate()
    out = stdout.decode() if stdout else ""
    print(out)
    return proc.returncode == 0


async def run_ble_test() -> bool:
    """Run ble_test.py to verify BLE protocol (connect + CMD_GET_ID/STATUS)."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        str(SCRIPT_DIR / "ble_test.py"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(SCRIPT_DIR),
    )
    stdout, _ = await proc.communicate()
    out = stdout.decode() if stdout else ""
    print(out)
    return proc.returncode == 0


def main():
    ap = argparse.ArgumentParser(description="Reset XIAO via serial, then check BLE")
    ap.add_argument("--port", default="/dev/ttyACM0", help="Serial port")
    ap.add_argument("--boot-wait", type=float, default=8.0, help="Seconds to wait after reset before BLE check")
    ap.add_argument("--skip-reset", action="store_true", help="Only run BLE check (no reset)")
    args = ap.parse_args()

    if not args.skip_reset:
        if not reset_via_serial(args.port):
            sys.exit(1)
        print(f"Waiting {args.boot_wait:.0f}s for device to boot...")
        time.sleep(args.boot_wait)

    async def run_checks():
        print("\n--- BLE find (SmartBall advertising?) ---")
        found = await check_ble(timeout=15.0)
        if not found:
            return False
        print("BLE find: OK\n")
        print("--- BLE protocol test (connect + GET_ID/STATUS) ---")
        return await run_ble_test()

    ok = asyncio.run(run_checks())
    if not ok:
        print("BLE check failed.")
        sys.exit(1)
    print("BLE test: OK")
    sys.exit(0)


if __name__ == "__main__":
    main()
