# SmartBall XIAO ESP32-C6 port

WiFi-based binary protocol server. Same frame format as the nRF BLE version; host sends binary frames via HTTP POST instead of BLE.

## Prerequisites

- **ESP-IDF v5.0+** (for ESP32-C6). Install and set up:

  ```bash
  # Clone IDF (one-time)
  cd ~
  git clone -b v5.1.2 --recursive https://github.com/espressif/esp-idf.git
  cd esp-idf
  ./install.sh esp32c6
  . ./export.sh
  ```

  Or use the [Espressif VS Code extension](https://github.com/espressif/vscode-esp-idf-extension) and open this folder.

## Build and flash

```bash
cd /home/mini/tools/msr1_esp32c6
. $HOME/esp/esp-idf/export.sh   # or your IDF path
idf.py set-target esp32c6
idf.py build
idf.py -p /dev/ttyACM0 flash monitor   # adjust port (e.g. /dev/ttyUSB0)
```

**Linux – no serial port?** The XIAO ESP32-C6 uses the Espressif USB JTAG/serial interface. Load the CDC-ACM driver once so it appears as `/dev/ttyACM0`:

```bash
sudo modprobe cdc_acm
# If the board was already connected, unplug and replug it
./build_and_flash.sh   # or: idf.py -p /dev/ttyACM0 flash
```

Or run `sudo ./scripts/load_cdc_acm.sh` from the project root.

## Runtime

1. Device connects to your **WiFi** (STA): SSID and password configured in `main/main.c` (e.g. Sinhale).
2. **Find the device IP** (any of):
   - Serial monitor: `Got IP: x.x.x.x - use http://x.x.x.x/api/cmd`
   - From another host on the same LAN: `curl http://<any-candidate-ip>/api/ip` — the device returns its assigned IP as plain text.
   - Run `./scripts/find_and_ping_esp32.sh [subnet]` to scan (e.g. `192.168.68`) and print the device IP.
   - Router DHCP client list: hostname **smartball-esp32c6**.
3. **Binary protocol over HTTP**:  
   `POST http://<device_ip>/api/cmd`  
   `GET http://<device_ip>/api/ip` — returns the device’s current IP (e.g. `192.168.68.42`).  
   - Body: raw binary frame (1 byte type + 2 bytes LE length + payload).  
   - Response: raw binary response (same format as BLE).

Supported commands: `CMD_ID`, `CMD_STATUS`, `CMD_LIST_SHOTS`, `CMD_GET_SHOT`, `CMD_GET_SHOT_CHUNK`.  
Test shot: id `0xAAAAAAAA`, size 15360 bytes (same as nRF).

## Host (Python) usage

Use the same frame format as `msr1_ota/web_gui/ble_binary_client.py`; replace BLE with HTTP:

```python
import requests
url = "http://192.168.4.1/api/cmd"
frame = bytes([0x0D, 0x01, 0x00, 0x00])  # CMD_LIST_SHOTS
r = requests.post(url, data=frame, timeout=5)
rsp = r.content  # binary response
```

A small WiFi client module can be added next to `ble_binary_client.py` to share the same high-level API (get_shot_list, fetch_shot_chunked over WiFi).
