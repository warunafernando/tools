#!/usr/bin/env python3
"""
PC <-> XIAO nRF52840 throughput test (Serial and BLE, both directions).
Uses existing firmware: CMD_OTA_ABORT for PC->device, CMD_OTA_STATUS for device->PC.
Usage: python throughput_test.py [--serial COM16] [--ble] [--duration 5] [--scan-retries 3]
"""
import sys
import time
import struct
import argparse
import asyncio
from pathlib import Path

SCAN_TIMEOUT = 15.0
SCAN_RETRIES = 3

# CMD_OTA_ABORT = 0x13, empty payload; CMD_OTA_STATUS = 0x16, empty payload
# Response to STATUS = 0x90 + 24 bytes
CMD_OTA_ABORT = 0x13
CMD_OTA_STATUS = 0x16
RSP_OTA = 0x90
NUS_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"


def build_frame(msg_id, payload=b""):
    return bytes([msg_id, len(payload) & 0xFF, len(payload) >> 8]) + payload


def fmt_throughput(bytes_val, sec):
    kbps = (bytes_val * 8) / 1024 if sec > 0 else 0
    return f"{bytes_val/1024:.2f} KB/s ({kbps:.1f} kbps)"


# --- Serial tests ---
def run_serial_pc_to_xiao(port, duration):
    """PC -> XIAO: send CMD_OTA_ABORT frames as fast as possible."""
    import serial
    frame = build_frame(CMD_OTA_ABORT)
    ser = serial.Serial(port, 115200, write_timeout=None)
    ser.reset_input_buffer()
    time.sleep(0.3)
    count = 0
    t0 = time.perf_counter()
    deadline = t0 + duration
    try:
        while time.perf_counter() < deadline:
            ser.write(frame)
            count += len(frame)
    except Exception as e:
        print(f"  Serial TX error: {e}")
    elapsed = time.perf_counter() - t0
    ser.close()
    return count, elapsed


def run_serial_xiao_to_pc(port, duration):
    """XIAO -> PC: request CMD_OTA_STATUS repeatedly, count bytes received."""
    import serial
    frame = build_frame(CMD_OTA_STATUS)
    ser = serial.Serial(port, 115200, timeout=0.5)
    ser.reset_input_buffer()
    time.sleep(0.3)
    total = 0
    t0 = time.perf_counter()
    deadline = t0 + duration
    try:
        while time.perf_counter() < deadline:
            ser.write(frame)
            ser.flush()
            r = ser.read(32)
            total += len(r)
            if len(r) < 27:
                time.sleep(0.01)
    except Exception as e:
        print(f"  Serial RX error: {e}")
    elapsed = time.perf_counter() - t0
    ser.close()
    return total, elapsed


# --- BLE helpers ---
async def find_smartball(retries=SCAN_RETRIES, timeout=SCAN_TIMEOUT):
    """Scan for SmartBall with retries. Returns (device, None) or (None, error_msg)."""
    from bleak import BleakScanner
    for attempt in range(1, retries + 1):
        print(f"  Scan attempt {attempt}/{retries} ({timeout}s)...", end=" ", flush=True)
        devices = await BleakScanner.discover(timeout=timeout)
        target = next((d for d in devices if "SmartBall" in (d.name or "")), None)
        if target:
            print(f"Found {target.name} @ {target.address}")
            return target, None
        print("not found")
    return None, "SmartBall not found after %d scan(s)" % retries


# --- BLE tests ---
async def run_ble_pc_to_xiao(duration, retries=SCAN_RETRIES):
    """PC -> XIAO: write CMD_OTA_ABORT to NUS_RX as fast as possible."""
    from bleak import BleakClient
    target, err = await find_smartball(retries)
    if not target:
        return 0, 0, err
    frame = build_frame(CMD_OTA_ABORT)
    count = 0
    try:
        print("  Connecting...", end=" ", flush=True)
        async with BleakClient(target.address, timeout=30.0) as client:
            print("OK")
            t0 = time.perf_counter()
            deadline = t0 + duration
            while time.perf_counter() < deadline:
                try:
                    await client.write_gatt_char(NUS_RX, frame, response=False)
                    count += len(frame)
                except Exception as e:
                    return count, time.perf_counter() - t0, str(e) or "write failed"
        elapsed = time.perf_counter() - t0
        return count, elapsed, None
    except Exception as e:
        return 0, 0, str(e) or type(e).__name__ or "connection failed"


async def run_ble_xiao_to_pc(duration, retries=SCAN_RETRIES):
    """XIAO -> PC: request CMD_OTA_STATUS, count notifications received."""
    from bleak import BleakClient
    target, err = await find_smartball(retries)
    if not target:
        return 0, 0, err
    frame = build_frame(CMD_OTA_STATUS)
    total = [0]
    def on_notify(_, data):
        total[0] += len(data)
    try:
        print("  Connecting...", end=" ", flush=True)
        async with BleakClient(target.address, timeout=30.0) as client:
            print("OK")
            await client.start_notify(NUS_TX, on_notify)
            t0 = time.perf_counter()
            deadline = t0 + duration
            try:
                while time.perf_counter() < deadline:
                    try:
                        await client.write_gatt_char(NUS_RX, frame, response=False)
                        await asyncio.sleep(0.02)
                    except Exception as e:
                        return total[0], time.perf_counter() - t0, str(e) or "write failed"
            finally:
                try:
                    await client.stop_notify(NUS_TX)
                except Exception:
                    pass
        elapsed = time.perf_counter() - t0
        return total[0], elapsed, None
    except Exception as e:
        return 0, 0, str(e) or type(e).__name__ or "connection failed"


async def main_async(args):
    import asyncio
    duration = args.duration
    print(f"Throughput test ({duration}s per direction)")
    print("=" * 60)

    if args.serial:
        print("\n[Serial USB]")
        print("  PC -> XIAO (TX)...")
        nb, el = run_serial_pc_to_xiao(args.serial, duration)
        print(f"    Sent {nb} bytes in {el:.2f}s  =  {fmt_throughput(nb, el)}")
        time.sleep(0.5)
        print("  XIAO -> PC (RX)...")
        nb, el = run_serial_xiao_to_pc(args.serial, duration)
        print(f"    Received {nb} bytes in {el:.2f}s  =  {fmt_throughput(nb, el)}")

    if args.ble:
        print("\n[BLE NUS]")
        retries = args.scan_retries
        print("  PC -> XIAO (TX)...")
        nb, el, err = await run_ble_pc_to_xiao(duration, retries)
        if err:
            print(f"    FAIL: {err}")
        elif el > 0:
            print(f"    Sent {nb} bytes in {el:.2f}s  =  {fmt_throughput(nb, el)}")
        time.sleep(0.5)
        print("  XIAO -> PC (RX)...")
        nb2, el2, err2 = await run_ble_xiao_to_pc(duration, retries)
        if err2:
            print(f"    FAIL: {err2}")
        elif el2 > 0:
            print(f"    Received {nb2} bytes in {el2:.2f}s  =  {fmt_throughput(nb2, el2)}")

    print("\n" + "=" * 60)
    print("Note: Uses OTA frames (CMD_ABORT/STATUS). Raw throughput may differ.")
    print("Serial baud 115200 => ~11.5 KB/s theoretical max.")


def main():
    ap = argparse.ArgumentParser(description="PC-XIAO throughput test (Serial and BLE)")
    ap.add_argument("--serial", metavar="COM", help="Serial port (e.g. COM16)")
    ap.add_argument("--ble", action="store_true", help="Run BLE tests")
    ap.add_argument("--duration", type=float, default=5.0, help="Seconds per test")
    ap.add_argument("--scan-retries", type=int, default=SCAN_RETRIES, help="BLE scan attempts")
    args = ap.parse_args()
    if not args.serial and not args.ble:
        ap.error("Specify --serial COMx and/or --ble")
    import asyncio
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
