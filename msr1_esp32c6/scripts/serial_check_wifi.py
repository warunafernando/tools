#!/usr/bin/env python3
"""
DEBUGGING ONLY — Serial monitor for ESP32-C6. Not used by the backend.
Read device serial output (115200 baud) to debug WiFi: see boot logs, Got IP,
DISCONNECTED reasons, auth failures. Run with device connected via USB.

Usage:
  python serial_check_wifi.py [PORT] [TIMEOUT_SEC]
  e.g. python serial_check_wifi.py /dev/ttyACM0 25

If PORT is omitted, tries /dev/ttyACM0, /dev/ttyUSB0.
Reset the device to capture full boot and WiFi connection logs.
"""
import re
import sys
import glob

def find_serial_port():
    for pattern in ["/dev/ttyACM*", "/dev/ttyUSB*", "/dev/serial/by-id/*"]:
        for path in sorted(glob.glob(pattern)):
            return path
    return None

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else None
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 70
    if not port:
        port = find_serial_port()
    if not port:
        print("No serial port found. Plug in ESP32 (USB) or pass: python serial_check_wifi.py /dev/ttyACM0")
        sys.exit(1)
    try:
        import serial
    except ImportError:
        print("Install pyserial: pip install pyserial")
        sys.exit(1)
    try:
        ser = serial.Serial(port, 115200, timeout=0.5)
    except Exception as e:
        print("Open %s: %s" % (port, e))
        print("Try: sudo chmod 666 %s  or run with sudo" % port)
        sys.exit(1)
    import time
    # Trigger ESP32 reset via DTR so we capture boot + WiFi logs
    ser.setDTR(False)
    time.sleep(0.1)
    ser.setDTR(True)
    time.sleep(0.8)
    ser.reset_input_buffer()
    print("Reading from %s for %ds (device reset, capturing boot + WiFi)..." % (port, timeout))
    print("-" * 60)
    buf = ""
    ip = None
    got_any = False
    api_line = None
    disconnected = []
    no_ip = False
    auth_fail = False
    ready = False
    import time
    t0 = time.monotonic()
    while (time.monotonic() - t0) < timeout:
        try:
            raw = ser.read(256)
            if raw:
                got_any = True
                buf += raw.decode("utf-8", errors="replace")
                while "\n" in buf or "\r" in buf:
                    line, _, buf = buf.partition("\n")
                    if not line.strip():
                        line = buf.partition("\r")[0] or line
                    line = line.strip().replace("\r", "")
                    if not line:
                        continue
                    print(line)
                    # Parse for status
                    if "Got IP:" in line or "Got IP (retry):" in line:
                        m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                        if m:
                            ip = m.group(1)
                    if "API: http://" in line:
                        api_line = line
                        m = re.search(r"http://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                        if m:
                            ip = m.group(1)
                    if "DISCONNECTED" in line or "disconnected" in line.lower():
                        disconnected.append(line[:80])
                    if "No IP after" in line or "No IP" in line:
                        no_ip = True
                    if "auth fail" in line.lower() or "wrong password" in line.lower():
                        auth_fail = True
                    if "Ready." in line or "GET http://" in line:
                        ready = True
            else:
                time.sleep(0.05)
        except (KeyboardInterrupt, serial.SerialException):
            break
    ser.close()
    print("-" * 60)
    print("Summary:")
    if not got_any:
        print("  No data from device. Check: (1) USB cable (2) port %s (3) device powered" % port)
    elif ip:
        print("  IP: %s  -> use http://%s in the GUI" % (ip, ip))
    else:
        print("  IP: not seen (device may not have joined WiFi yet)")
    if no_ip:
        print("  No IP: firmware did not get DHCP (check SSID/password or AP range)")
    if auth_fail:
        print("  Auth: likely wrong WiFi password for SSID 'SinhaleD'")
    if disconnected:
        print("  Disconnect: %s" % disconnected[-1][:60])
    if ready and ip:
        print("  Server: device is up; try: curl http://%s/api/ip" % ip)
    elif not ip:
        print("  Tip: Reset the device (button or replug USB) and run this script again to capture boot logs.")
    return 0 if ip else 1

if __name__ == "__main__":
    sys.exit(main())
