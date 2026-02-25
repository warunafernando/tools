#!/usr/bin/env python3
"""
1. Reset device via OpenOCD
2. Wait for USB re-enumeration
3. Open serial (try both ACM ports if needed) and send spi read commands

Usage: python3 read_imu_debugger_reset_then_read.py [PORT]
Default: try /dev/ttyACM1 then /dev/ttyACM0
"""
import subprocess
import sys
import re
import time
import glob
import os

BAUD = 115200

def find_xiao_port():
    """After reset, XIAO may be ACM0 or ACM1. Prefer by-id ZEPHYR (XIAO)."""
    by_id = "/dev/serial/by-id"
    if os.path.isdir(by_id):
        for p in sorted(os.listdir(by_id)):
            if "ZEPHYR" in p or "2fe3" in p.lower():
                path = os.path.realpath(os.path.join(by_id, p))
                if path.startswith("/dev/"):
                    return path
    for port in ["/dev/ttyACM1", "/dev/ttyACM0"]:
        if os.path.exists(port):
            return port
    return None

def main():
    try:
        import serial
    except ImportError:
        print("pip install pyserial"); sys.exit(1)

    print("Resetting XIAO via OpenOCD...")
    subprocess.run(
        ["openocd", "-f", "interface/cmsis-dap.cfg", "-f", "target/nrf52.cfg",
         "-c", "init; reset run; shutdown"],
        cwd="/home/mini/tools", capture_output=True, timeout=8)
    print("Waiting 5s for USB re-enumeration...")
    time.sleep(5)

    port = sys.argv[1] if len(sys.argv) > 1 else find_xiao_port()
    if not port:
        port = "/dev/ttyACM1"
    ports_to_try = [port] if port else ["/dev/ttyACM1", "/dev/ttyACM0"]
    ser = None
    for p in ports_to_try:
        if not os.path.exists(p):
            continue
        try:
            ser = serial.Serial(p, BAUD, timeout=0.1)
            print(f"Opened {p}")
            break
        except Exception as e:
            print(f"{p}: {e}")
    if ser is None:
        print("No serial port available. List: ls /dev/ttyACM* /dev/serial/by-id/")
        sys.exit(1)

    # Shell may need a moment; send newline then commands
    time.sleep(0.5)
    ser.reset_input_buffer()

    commands = [
        ("LSM6 WHO_AM_I (0x0F)", "spi read 0 0x0F 1"),
        ("LSM6 accel (0x28)", "spi read 0 0x28 6"),
        ("LSM6 gyro (0x22)", "spi read 0 0x22 6"),
        ("ADXL DEVID (0x00)", "spi read 1 0x00 1"),
        ("ADXL DATA (0x32)", "spi read 1 0x32 6"),
    ]
    for name, cmd in commands:
        ser.reset_input_buffer()
        ser.write((cmd + "\r\n").encode())
        time.sleep(0.3)
        buf = b""
        t0 = time.monotonic()
        while time.monotonic() - t0 < 2.5:
            if ser.in_waiting:
                buf += ser.read(ser.in_waiting)
            time.sleep(0.05)
        text = buf.decode("utf-8", errors="replace")
        hex_match = re.search(r"\(\d+ byte\(s\)\)\):?\s*([\s0-9A-Fa-f]+?)(?:\r?\n|$)", text)
        if hex_match:
            hex_str = hex_match.group(1).strip()
            try:
                bytes_list = [int(x, 16) for x in hex_str.split()]
                print(f"  {name}: {' '.join(f'{b:02X}' for b in bytes_list)}")
            except ValueError:
                print(f"  {name}: (parse) {hex_str[:80]}")
        elif "failed" in text:
            print(f"  {name}: FAILED — {text.strip()[:150]}")
        else:
            print(f"  {name}: no response (got {len(buf)} bytes)")
            if buf:
                print("    raw:", buf[:200])

    ser.close()
    print("Done.")

if __name__ == "__main__":
    main()
