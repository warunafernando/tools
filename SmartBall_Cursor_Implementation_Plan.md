# SmartBall Cursor Implementation Plan

Based on SmartBall_Full_SPI_Architecture_v3.md. Cursor must execute phases in order.
Do not modify or refactor any IMPLEMENTED (DONE) components.

------------------------------------------------------------------------

# RULES

-   Do NOT ask clarification questions. Choose safest engineering defaults.
-   Do NOT change, remove, or refactor items marked [DONE].
-   Build after each phase. Fix errors before proceeding.
-   Run tests when applicable.
-   If an error occurs: inspect, fix, retry. Do not stop.

------------------------------------------------------------------------

# [DONE] DO NOT MODIFY

The following are implemented and working. Do not change them:

## OTA System (§11)

-   MCUboot dual-slot A/B
-   MCUmgr SMP over BLE + UART (USB CDC)
-   Firmware variants v1/v2 (single/double blink)
-   Paths: ncs-workspace/nrf/app/, prj.conf, prj_v1.conf, prj_v2.conf

## Device Identity (§12)

-   SMP group 65, command 0 (serial + part)
-   device_mgmt.c in nrf/app/src/
-   Port verification logic

## Host Tools & Web GUI (§13)

-   msr1_ota/web_gui/app.py
-   msr1_ota/device_identity.py
-   msr1_ota/build_ota_images.sh
-   msr1_ota/images/ (app_v1.bin, app_v2.bin)

------------------------------------------------------------------------

# PHASE 1 — BLE Binary Protocol (Architecture §3, §4)

Implement BLE binary frames alongside existing NUS (MCUmgr uses NUS; binary protocol is separate or coexists as documented).

## 1.1 Frame Parser

-   Format: Type (1) | Length (2 LE) | Payload (N)
-   Add parser module: parse header, dispatch by Type
-   Integrate with existing BLE NUS RX path (or define coexistence)

## 1.2 Command Dispatcher

-   CMD_ID, CMD_STATUS, CMD_DIAG, CMD_SELFTEST, CMD_CLEAR_ERRORS
-   CMD_SET, CMD_GET_CFG, CMD_SAVE_CFG, CMD_LOAD_CFG, CMD_FACTORY_RESET
-   CMD_START_RECORD, CMD_STOP_RECORD, CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_DEL_SHOT, CMD_FORMAT_STORAGE
-   CMD_BUS_SCAN
-   Stub handlers OK initially; return minimal valid response

## 1.3 Response Helpers

-   RSP_ID, RSP_STATUS, RSP_DIAG — build frames per §4, §10
-   Use FICR DEVICEID for serial (already in device_mgmt); include fw_version, protocol_version, hw_revision

------------------------------------------------------------------------

# PHASE 2 — Internal IMU & Health (Architecture §6.1, §10)

## 2.1 Internal IMU

-   Initialize XIAO Sense internal IMU (LSM6DS3TR-C or equivalent)
-   Configurable: accel_range, gyro_range, sample_rate_hz
-   Maintain gyro saturation counter
-   Timestamp samples with microsecond timer

## 2.2 RSP_STATUS

-   Implement full RSP_STATUS payload per §10:
    -   uptime_ms, last_error, error_flags, device_state
    -   samples_recorded, imu_saturation_counter_internal, imu_saturation_counter_lsm
    -   storage_used_bytes, storage_free_bytes
    -   battery_voltage, temperature, reset_reason, firmware_build_id

## 2.3 RSP_DIAG & SELFTEST

-   RSP_DIAG: internal IMU presence, voltage, temperature
-   SELFTEST: internal IMU init, RAM integrity, BLE stack/advertising

------------------------------------------------------------------------

# PHASE 3 — Logging & Shot Format (Architecture §8, §9)

## 3.1 Storage Abstraction

-   Primary: W25Q64 (when SPI present); Fallback: internal flash
-   Layout: superblock, session index, shot region
-   Append-only writes, CRC per block, recovery scan on boot

## 3.2 Shot Format SVTSHOT3

-   Header: magic SVTSHOT3, version, sample_rate_hz, count, sensor_mask, imu_source_mask, header_crc32
-   Sample: 28 bytes (single IMU) or 40+ bytes (multi-sensor) per §9
-   Footer: footer_crc32

## 3.3 Recording Pipeline

-   Ring buffer in RAM
-   Writer task to flash
-   CMD_START_RECORD / CMD_STOP_RECORD implementation

------------------------------------------------------------------------

# PHASE 4 — SPI Bus & Drivers (Architecture §2, §5)

## 4.1 SPI Bus Manager

-   Shared SCK, MOSI, MISO
-   Dedicated CS: CS_LSM6, CS_ADXL, CS_FLASH
-   Mutex for bus access
-   Board overlay: pin assignments for LSM6DSOX, ADXL375, W25Q64

## 4.2 LSM6DSOX Driver

-   SPI WHO_AM_I check
-   Configurable ODR, range
-   Optional INT_LSM6 (data-ready)
-   Gyro + accel; saturation flags

## 4.3 ADXL375 Driver

-   SPI DEVID check
-   High-G interrupt (INT_ADXL) for impact trigger
-   Event trigger logic

## 4.4 W25Q64 Driver

-   JEDEC ID, read/write/erase
-   Log-structured layout per §8
-   Power-loss recovery scan

## 4.5 CMD_BUS_SCAN

-   Scan SPI: LSM6 WHOAMI, ADXL DEVID, W25Q64 JEDEC
-   Scan I2C: enumerate addresses
-   Return response per §5

------------------------------------------------------------------------

# PHASE 5 — Multi-IMU & Event Recording (Architecture §6, §7)

## 5.1 Multi-IMU Strategy

-   Internal IMU: low-range precision
-   LSM6DSOX: mid/high dynamics
-   ADXL375: impact detection
-   Fusion/range-selection: switch by saturation or record all; mark per-sample saturation

## 5.2 Event Recording Mode

-   Circular pre-trigger RAM buffer
-   On ADXL375 impact: save pre_ms, post_ms, full shot per SVTSHOT3

## 5.3 BLE Runtime Metrics (§10.1)

-   rssi_dbm, rssi_avg_dbm, ble_conn_interval_ms, ble_mtu_size, ble_phy_mode
-   ble_tx_power_dbm, ble_packets_tx, ble_packets_rx, ble_disconnect_count, ble_crc_error_count, ble_throughput_bps
-   Add to RSP_STATUS or dedicated BLE_STATUS response

------------------------------------------------------------------------

# PHASE 6 — Configuration & Storage (Architecture §4)

## 6.1 Configuration Commands

-   CMD_SET, CMD_GET_CFG, CMD_SAVE_CFG, CMD_LOAD_CFG
-   Persist to NVS or W25Q64 config partition
-   CMD_FACTORY_RESET

## 6.2 Shot Management

-   CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_DEL_SHOT
-   CMD_FORMAT_STORAGE

------------------------------------------------------------------------

# COMPLETION CRITERIA

-   Phase 1: Binary protocol parser and dispatcher; stub responses for all commands
-   Phase 2: Internal IMU working; RSP_STATUS, RSP_DIAG, SELFTEST implemented
-   Phase 3: Logging pipeline; SVTSHOT3 format; start/stop recording
-   Phase 4: SPI bus; LSM6DSOX, ADXL375, W25Q64 drivers; CMD_BUS_SCAN
-   Phase 5: Multi-IMU fusion; event recording; BLE metrics
-   Phase 6: Config persistence; shot list/get/delete; format

Each phase must build and run. OTA, device identity, and Web GUI must remain unchanged.

------------------------------------------------------------------------
