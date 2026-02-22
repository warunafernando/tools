# SmartBall Firmware Architecture (SPI Enabled)

------------------------------------------------------------------------

# 1. System Overview

This document defines the SmartBall firmware architecture with:

-   XIAO nRF52840 Sense
-   Internal IMU (low-range precision motion sensing)
-   LSM6DSOX (SPI mid/high-range IMU)
-   ADXL375 (SPI high-G sensor)
-   W25Q64 (SPI external flash)
-   BLE binary protocol
-   Shot logging system
-   OTA update system (MCUmgr SMP over BLE + USB serial)
-   Device identity (serial/part via SMP)
-   Web GUI for upgrade, verify, activate

Both internal IMU and LSM6DSOX are active sensors used for different
dynamic ranges.

------------------------------------------------------------------------

# 2. Hardware Architecture

## 2.1 SPI Bus

Shared lines: - SCK - MOSI - MISO

Dedicated CS lines: - CS_LSM6 - CS_ADXL - CS_FLASH

Optional interrupt lines: - INT_LSM6 (data-ready) - INT_ADXL (impact
trigger)

------------------------------------------------------------------------

# 3. BLE Binary Communication

Frame format:

  Offset   Size   Description
  -------- ------ --------------------
  0        1      Type
  1        2      Length (uint16 LE)
  3        N      Payload

All numeric values little-endian.

------------------------------------------------------------------------

# 4. Supported Commands

Identity & Status: - CMD_ID - CMD_STATUS - CMD_DIAG - CMD_SELFTEST -
CMD_CLEAR_ERRORS - Device identity via MCUmgr group 65 (see §12)

Configuration: - CMD_SET - CMD_GET_CFG - CMD_SAVE_CFG - CMD_LOAD_CFG -
CMD_FACTORY_RESET

Recording: - CMD_START_RECORD - CMD_STOP_RECORD - CMD_LIST_SHOTS -
CMD_GET_SHOT - CMD_DEL_SHOT - CMD_FORMAT_STORAGE

Bus discovery: - CMD_BUS_SCAN

------------------------------------------------------------------------

# 5. Bus Scan Command

CMD_BUS_SCAN scans:

-   SPI devices
-   I2C devices

Response includes:

SPI entries: - device type - CS index - ID bytes (WHOAMI/DEVID/JEDEC) -
flags

I2C entries: - 7-bit address - flags

------------------------------------------------------------------------

# 6. Sensor Roles

## 6.1 Internal IMU (Low-Range Precision)

-   Used for fine motion tracking
-   Optimized for low-noise measurements
-   Best for small rotations and low acceleration events
-   Active at all times during recording

## 6.2 ADXL375 (High-G Detection)

-   200g high-G accelerometer
-   Dedicated to impact detection
-   Used in trigger-based recording mode

## 6.3 LSM6DSOX (Mid/High Dynamic Range)

-   Gyro + accelerometer
-   Used for medium-to-high dynamic motion
-   Complements internal IMU for broader measurement range
-   Provides robust tracking during rapid spins and impacts

------------------------------------------------------------------------

# 7. Multi-IMU Strategy

During recording:

-   Internal IMU handles low-noise fine motion
-   LSM6DSOX handles medium/high dynamics
-   ADXL375 handles extreme impact events

Fusion or range-selection logic may: - Switch sources based on
saturation flags - Record all sensors simultaneously - Mark per-sample
saturation counters

------------------------------------------------------------------------

# 8. Logging Architecture

## 8.1 Storage Target

Primary: W25Q64 external flash\
Fallback: internal flash

## 8.2 Flash Layout

-   Superblock
-   Session Index
-   Shot Data Region

Append-only write model\
CRC per block\
Recovery scan on boot

------------------------------------------------------------------------

# 9. Shot File Format (SVTSHOT3)

Header:

-   magic = SVTSHOT3
-   version
-   sample_rate_hz
-   count
-   sensor_mask
-   imu_source_mask (bitmask of active IMUs)
-   header_crc32

Sample formats:

28 bytes (single IMU accel + gyro): - t_ms - ax, ay, az (float32) - gx,
gy, gz (float32)

40+ bytes (multi-sensor): - t_ms - internal_ax, internal_ay,
internal_az - internal_gx, internal_gy, internal_gz - lsm_ax, lsm_ay,
lsm_az - lsm_gx, lsm_gy, lsm_gz - optional highg_ax, highg_ay, highg_az

Footer: - footer_crc32

------------------------------------------------------------------------

------------------------------------------------------------------------

# 10. Health, Diagnostics & BLE Metrics

RSP_STATUS includes:

-   uptime_ms
-   last_error
-   error_flags
-   device_state
-   samples_recorded
-   imu_saturation_counter_internal
-   imu_saturation_counter_lsm
-   storage_used_bytes
-   storage_free_bytes
-   battery_voltage
-   temperature
-   reset_reason
-   firmware_build_id

## 10.1 BLE Runtime Metrics

The system shall also track and report BLE-related metrics:

-   rssi_dbm (int8) -- latest received signal strength
-   rssi_avg_dbm (int8) -- moving average RSSI
-   ble_conn_interval_ms (uint16) -- current connection interval
-   ble_mtu_size (uint16) -- negotiated MTU
-   ble_phy_mode (uint8) -- 1=1M, 2=2M, 3=Coded
-   ble_tx_power_dbm (int8) -- current TX power
-   ble_packets_tx (uint32) -- total TX packets
-   ble_packets_rx (uint32) -- total RX packets
-   ble_disconnect_count (uint32) -- lifetime disconnect counter
-   ble_crc_error_count (uint32) -- packet CRC failures
-   ble_throughput_bps (uint32) -- measured application throughput

These fields may be added to RSP_STATUS payload or returned via a
dedicated BLE_STATUS response if desired.

## 10.2 RSP_DIAG includes

-   internal IMU presence
-   LSM6DSOX WHOAMI
-   ADXL375 DEVID
-   W25Q64 JEDEC ID
-   voltage
-   temperature

## 10.3 Self-Test

SELFTEST verifies:

-   Internal IMU initialization
-   LSM6DSOX SPI communication
-   ADXL375 SPI communication
-   W25Q64 read/write test sector
-   RAM integrity
-   BLE stack active
-   BLE advertising functional
-   BLE connection parameter validation

------------------------------------------------------------------------

# 11. OTA Update System (Implemented)

## 11.1 Stack

-   MCUboot (dual-slot A/B)
-   MCUmgr SMP over BLE (primary)
-   MCUmgr SMP over UART (USB CDC serial)
-   Image signing, CRC verification
-   Test boot with confirm; rollback on timeout/failure

## 11.2 A/B Slots

-   Slot 0 (A): primary/active
-   Slot 1 (B): secondary (upgrade target)
-   Upgrade flow: write to slot 1 → reboot into test boot → CMD_OTA_CONFIRM to commit
-   Rollback if not confirmed (watchdog/timeout)

## 11.3 Transport

| Transport  | Protocol              | Use case              |
|-----------|------------------------|------------------------|
| BLE       | SMP over GATT          | Wireless OTA           |
| Serial    | SMP over USB CDC       | Wired, port verify     |
| Debugger  | west flash (pyocd)     | Initial/full flash     |

## 11.4 Firmware Variants

-   v1: single-blink pattern (CONFIG_APP_BLINK_DOUBLE=n)
-   v2: double-blink pattern (CONFIG_APP_BLINK_DOUBLE=y)
-   Version tags: 1.0.0+1 (v1), 1.0.0+2 (v2)

------------------------------------------------------------------------

# 12. Device Identity (Implemented)

## 12.1 MCUmgr Group 65, Command 0

Custom SMP handler for detection and verification:

-   Request: SMP read, group_id=65, command_id=0
-   Response: CBOR map { "rc": 0, "serial": "<16-char hex>", "part": "<part_number>" }

-   serial: 64-bit nRF52840 FICR DEVICEID as 16-char hex string
-   part: Part number string (e.g. "XIAO-BLE-SENSE")

## 12.2 Port Verification

Serial port is verified by opening and reading IDs; valid only when both serial
and part are returned. Fallback: smpmgr image state-read for older firmware.

------------------------------------------------------------------------

# 13. Host Tools & Web GUI (Implemented)

## 13.1 Web GUI (Flask)

-   Scan BLE: bluetoothctl cache + scan, connect, store address
-   Scan Serial: list /dev/ttyACM*, open each, read device IDs
-   Scan Debugger: pyocd list probes
-   Verify Port: open port, read serial+part via SMP group 65
-   Upgrade: smpmgr image erase 1, upgrade --slot 1 (BLE/Serial) or west flash (Debugger)
-   Read Version: smpmgr image state-read
-   Activate: SMP ImageStatesWrite + ResetWrite (slot B → confirm + reboot)

## 13.2 Paths

| Component      | Path                                      |
|----------------|-------------------------------------------|
| Web app        | msr1_ota/web_gui/app.py                   |
| Images         | msr1_ota/images/app_v1.bin, app_v2.bin    |
| Device identity| msr1_ota/device_identity.py               |
| Build script   | msr1_ota/build_ota_images.sh              |
| Firmware       | ncs-workspace/nrf/app/                    |

## 13.3 device_identity.py

-   `device_identity.py serial /dev/ttyACM0`
-   `device_identity.py ble AA:BB:CC:DD:EE:FF`
-   Opens transport, sends SMP read (group 65, cmd 0), parses CBOR for serial and part.

## 13.4 Build

```bash
./msr1_ota/build_ota_images.sh   # Build v1 and v2 signed images
cd msr1_ota/web_gui && python3 app.py   # Start web server (port 5050)
```

------------------------------------------------------------------------
