# SmartBall Firmware - XIAO nRF52840 Sense

Firmware for the SmartBall project using XIAO nRF52840 Sense only (Stage 1).

## Requirements

- [PlatformIO](https://platformio.org/) (VS Code extension or CLI)
- XIAO nRF52840 Sense connected via USB

## Build

```bash
cd firmware
pio run
```

## Upload

1. Put the board in bootloader mode: **double-tap the reset button**
2. Run:
```bash
pio run --target upload
```

## Serial Monitor

```bash
pio device monitor --baud 115200
```

Note: On XIAO Sense, Serial may require opening the monitor for the sketch to start (depending on board configuration).

## BLE Test

Use the Python test script to verify BLE protocol:

```bash
pip install bleak
python tools/ble_test.py
```

This scans for "SmartBall", connects via NUS, and requests RSP_ID and RSP_STATUS.

## Protocol

- **NUS Service**: 6E400001-B5A3-F393-E0A9-E50E24DCCA9E
- **TX** (notify): 6E400002-...
- **RX** (write): 6E400003-...

Frame format: `Type (1) + Length (2 LE) + Payload`

## OTA Update

### Serial OTA
1. Upload OTA-capable firmware: `pio run -e ota_serial --target upload` or `pio run -e ota_ble --target upload`
2. Close serial monitor
3. Run: `python tools/ota_serial.py COM16 firmware.bin`
4. Use firmware from `.pio/build/minimal/firmware.bin` or `.pio/build/ota_serial/firmware.bin`

### BLE OTA
1. Upload `ota_ble` firmware
2. Run: `python tools/ota_ble.py .pio/build/minimal/firmware.bin`
3. Device receives firmware over BLE NUS

Note: OTA writes to staging flash. Boot swap (apply on reboot) requires MCUboot – not yet implemented.

## Implemented (Phase 1–2)

- [x] Device identity (FICR DEVICEID)
- [x] BLE binary frame parser
- [x] RSP_ID, RSP_STATUS
- [x] Internal IMU (LSM6DS3 via Adafruit)
- [x] Streaming MSG_ACCEL, MSG_GYRO (via CMD_SET_STREAM)
- [x] Health system, SELFTEST
- [x] OTA over Serial (ota_serial env)
- [x] OTA over BLE (ota_ble env)
- [ ] Logging pipeline (Shot v3 to flash)
- [ ] OTA boot swap (MCUboot)
