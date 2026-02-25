#!/usr/bin/env python3
"""
Read external IMU (LSM6 cs=0, ADXL cs=1) directly over debugger serial using
Zephyr shell 'spi read' commands. Use when BLE/recording shows no external IMU data.

Usage:
  python3 scripts/read_imu_via_debugger.py [PORT]
  Default PORT: /dev/ttyACM1 (XIAO USB). Use /dev/ttyACM0 only if that's the device.

Requires: pyserial (pip install pyserial)
"""
import sys
import re
import time

SERIAL_PORT = "/dev/ttyACM1"
BAUD = 115200
# Wait for shell after open (boot log can take a few seconds)
BOOT_WAIT = 6.0
CMD_DELAY = 0.2
READ_TIMEOUT = 2.5

# LSM6DSOX: WHO_AM_I 0x0F -> 0x6C; accel 0x28 (6), gyro 0x22 (6)
# ADXL375:  DEVID 0x00 -> 0xE5; DATAX0 0x32 (6)
CHECKS = [
    ("LSM6 WHO_AM_I (0x0F)", 0, 0x0F, 1, "0x6C/0x6A/0x69 = OK, else wiring/CS"),
    ("LSM6 CTRL1_XL (0x10)", 0, 0x10, 1, "ODR+FS"),
    ("LSM6 accel OUT (0x28)", 0, 0x28, 6, "AX_L,AX_H,AY_L,AY_H,AZ_L,AZ_H"),
    ("LSM6 gyro OUT (0x22)", 0, 0x22, 6, "GX_L,GX_H,..."),
    ("ADXL DEVID (0x00)", 1, 0x00, 1, "0xE5 = OK"),
    ("ADXL DATAX0 (0x32)", 1, 0x32, 6, "X_L,X_H,Y_L,Y_H,Z_L,Z_H"),
]


def run_spi_read(ser, cs: int, reg: int, length: int) -> tuple[bool, list[int] | None, str]:
    """Send 'spi read <cs> <reg> <len>', parse response. Returns (ok, bytes_or_none, message)."""
    cmd = f"spi read {cs} 0x{reg:02X} {length}\r\n"
    ser.reset_input_buffer()
    ser.write(cmd.encode("utf-8"))
    time.sleep(CMD_DELAY)
    deadline = time.monotonic() + READ_TIMEOUT
    raw = b""
    while time.monotonic() < deadline:
        if ser.in_waiting:
            raw += ser.read(ser.in_waiting)
            if b"byte(s))" in raw or b"failed" in raw:
                break
        time.sleep(0.05)
    text = raw.decode("utf-8", errors="replace")
    if "spi_bus_chip_read failed" in text:
        return False, None, text.strip()
    # Parse " 6C" or " 6C 00 11 ..." (hex bytes after "byte(s)):")
    hex_match = re.search(r"\(\d+ byte\(s\)\)\):?\s*([\s0-9A-Fa-f]+?)(?:\r?\n|$)", text)
    if not hex_match:
        # Also try single line " 6C" after "reg 0x0F"
        hex_match = re.search(r"reg 0x[0-9A-Fa-f]+.*?([0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2})*)", text, re.DOTALL)
    if not hex_match:
        return False, None, "No hex data in response: " + text[:300].replace("\r", " ")
    hex_str = hex_match.group(1).strip()
    try:
        bytes_list = [int(x, 16) for x in hex_str.split()]
    except ValueError:
        return False, None, "Invalid hex: " + hex_str
    return True, bytes_list, hex_str


def main():
    port = sys.argv[1] if len(sys.argv) > 1 else SERIAL_PORT
    try:
        import serial
    except ImportError:
        print("Install pyserial: pip install pyserial")
        sys.exit(1)
    print(f"Opening {port} at {BAUD}...")
    try:
        ser = serial.Serial(port, BAUD, timeout=0.1)
    except Exception as e:
        print(f"Open failed: {e}")
        print("Is the XIAO connected via USB? Try: ls /dev/ttyACM*")
        sys.exit(1)
    print(f"Waiting {BOOT_WAIT}s for boot and shell...")
    time.sleep(BOOT_WAIT)
    ser.reset_input_buffer()
    print("Reading external IMU via debugger shell (spi read)...\n")
    all_ok = True
    for name, cs, reg, length, hint in CHECKS:
        ok, data, msg = run_spi_read(ser, cs, reg, length)
        if ok:
            hex_str = " ".join(f"{b:02X}" for b in data) if data else ""
            print(f"  {name}: {hex_str}  ({hint})")
        else:
            print(f"  {name}: FAILED — {msg}")
            all_ok = False
    ser.close()
    print()
    if all_ok:
        print("All reads OK. If recording still shows no external IMU, check multi_imu init and sample_fetch.")
    else:
        print("Some reads failed. Check SPI wiring (SCK/MOSI/MISO/CS), power, and CS pins (LSM6=cs0, ADXL=cs1).")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
