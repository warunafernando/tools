# Serial port debugging (ESP32-C6)

Use the **serial port only for debugging** — the backend and GUI do not use serial.

## Quick start

1. Connect the ESP32-C6 via USB.
2. Open a serial monitor at **115200 baud** and reset the device to see boot and WiFi logs.

## Options

### Option A: Python script (parsed summary)

```bash
cd /path/to/tools
python3 msr1_esp32c6/scripts/serial_check_wifi.py [/dev/ttyACM0] [timeout_sec]
```

- Reads serial for a set time and prints all lines, then a **Summary** with IP (if seen), "No IP", or disconnect/auth messages.
- Handy to confirm whether the device got an IP and why it might have disconnected.

### Option B: Raw serial monitor (ESP-IDF)

```bash
cd msr1_esp32c6
idf.py -p /dev/ttyACM0 monitor
```

- Full raw log stream. Exit with Ctrl+].

### Option C: screen / minicom

```bash
screen /dev/ttyACM0 115200
# or
minicom -D /dev/ttyACM0 -b 115200
```

## What to look for in logs

- **Got IP: x.x.x.x** — Device joined WiFi; use `http://x.x.x.x` in the GUI.
- **WiFi DISCONNECTED: reason=...** — e.g. wrong password, AP not in range.
- **No IP after 30s** — DHCP failed; check SSID/password and that "SinhaleD" is in range.
- **API: http://x.x.x.x/api/cmd** — HTTP server is up at that IP.

The backend connects to the device over **WiFi** (HTTP). Serial is only for your debugging.

## When the backend can't reach the device ("No route to host")

1. **Use serial first**: run `python3 msr1_esp32c6/scripts/serial_check_wifi.py /dev/ttyACM0 35` (device on USB). The summary shows whether the ESP32 got an IP and any disconnect/auth errors.
2. If serial shows **Got IP: 192.168.68.89** and **Ready** but the backend still gets "No route to host", the **machine running the backend** is on a different network — run the backend on a host that is on the same WiFi as the ESP32 (e.g. SinhaleD).
3. If serial shows **No IP** or **DISCONNECTED**, fix WiFi (SSID/password/range) or wait longer (device can take ~15s after boot to get an IP).
