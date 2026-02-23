# SmartBall Cursor Implementation Plan

Based on SmartBall_Full_SPI_Architecture_v3.md. Cursor must execute phases in order.
Do not modify or refactor any IMPLEMENTED (DONE) components.

------------------------------------------------------------------------

# RULES

-   Do NOT ask clarification questions. Choose safest engineering defaults.
-   Do NOT change, remove, or refactor items marked [DONE].
-   Build after each phase. Fix errors before proceeding.
-   Run unit tests for each phase before proceeding to next.
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

## 1.4 Unit Tests

-   `test_frame_parser_valid_header`: parse Type|Length|Payload; assert correct Type, Length, Payload split
-   `test_frame_parser_invalid_length_zero`: reject length 0
-   `test_frame_parser_invalid_length_overflow`: reject length > max payload size
-   `test_command_dispatcher_all_cmds`: for each CMD_* , send frame and assert non-empty valid response
-   `test_rsp_id_format`: CMD_ID → RSP_ID; assert frame format, serial present, fw_version, protocol_version, hw_revision
-   `test_rsp_status_format`: CMD_STATUS → RSP_STATUS; assert frame format and expected field layout
-   `test_rsp_diag_format`: CMD_DIAG → RSP_DIAG; assert frame format
-   **Transport (BLE):**
-   `test_cmd_id_via_ble`: send CMD_ID over BLE; receive RSP_ID; assert valid response

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

## 2.4 Unit Tests

-   `test_internal_imu_init`: init IMU; assert no error, sample_rate_hz and ranges applied
-   `test_internal_imu_read_sample`: read sample; assert valid accel/gyro values within range
-   `test_gyro_saturation_counter`: simulate saturation; assert counter increments
-   `test_timestamp_microseconds`: two samples; assert timestamp delta > 0, within expected sample period
-   `test_rsp_status_fields`: CMD_STATUS → assert all fields present: uptime_ms, last_error, error_flags, device_state, samples_recorded, imu_saturation_counter_internal, storage_used_bytes, storage_free_bytes, battery_voltage, temperature, reset_reason, firmware_build_id
-   `test_rsp_diag_imu_presence`: CMD_DIAG → assert internal IMU presence flag, voltage, temperature
-   `test_selftest_imu`: CMD_SELFTEST → assert internal IMU init success
-   `test_selftest_ram`: CMD_SELFTEST → assert RAM integrity pass
-   **Transport (BLE):**
-   `test_cmd_status_via_ble`: CMD_STATUS over BLE → RSP_STATUS; assert all fields
-   `test_cmd_diag_via_ble`: CMD_DIAG over BLE → RSP_DIAG; assert valid
-   `test_cmd_selftest_via_ble`: CMD_SELFTEST over BLE → assert pass

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

## 3.4 Unit Tests

-   `test_storage_superblock_read_write`: write superblock, read back; assert match
-   `test_storage_block_crc`: write block with CRC; read and verify CRC valid; corrupt byte, assert CRC invalid
-   `test_storage_recovery_scan`: simulate partial write; boot recovery; assert superblock/session index consistent
-   `test_svtshot3_header`: build header; assert magic SVTSHOT3, version, sample_rate_hz, count, sensor_mask, imu_source_mask, header_crc32
-   `test_svtshot3_sample_size`: single IMU 28 bytes, multi-sensor 40+ bytes
-   `test_svtshot3_footer`: build shot; assert footer_crc32 validates
-   `test_ring_buffer_push_pop`: push N samples, pop N; assert order and content preserved
-   `test_ring_buffer_overflow`: push beyond capacity; assert overwrite or reject policy correct
-   `test_cmd_start_stop_record`: CMD_START_RECORD → CMD_STOP_RECORD; assert recording state, samples_recorded incremented
-   **Transport (BLE):**
-   `test_cmd_start_record_via_ble`: CMD_START_RECORD over BLE; assert recording started
-   `test_cmd_stop_record_via_ble`: CMD_STOP_RECORD over BLE; assert recording stopped, samples_recorded updated

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

## 4.6 Unit Tests

-   `test_spi_bus_mutex`: two tasks acquire bus; assert serialized access, no corruption
-   `test_lsm6_whoami`: SPI read WHO_AM_I; assert expected value (LSM6DSOX)
-   `test_lsm6_odr_range`: set ODR and range; read back config; assert applied
-   `test_lsm6_saturation_flags`: read status; assert saturation flags present
-   `test_adxl_devid`: SPI read DEVID; assert expected value (ADXL375)
-   `test_adxl_high_g_interrupt`: configure threshold; assert interrupt fires on impact (or mock)
-   `test_w25q64_jedec`: read JEDEC ID; assert expected manufacturer/device
-   `test_w25q64_read_write`: write page, read back; assert match
-   `test_w25q64_erase`: erase sector; read; assert 0xFF
-   `test_cmd_bus_scan_spi`: CMD_BUS_SCAN → assert LSM6, ADXL, W25Q64 presence (or absence) per §5
-   `test_cmd_bus_scan_i2c`: CMD_BUS_SCAN → assert I2C address list returned per §5
-   **Transport (BLE):**
-   `test_cmd_bus_scan_via_ble`: CMD_BUS_SCAN over BLE; assert response format per §5, SPI/I2C results

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

## 5.4 Unit Tests

-   `test_multi_imu_saturation_switch`: saturate internal IMU; assert LSM6/ADXL used or saturation marked
-   `test_per_sample_saturation_mark`: record with saturation; assert per-sample flag set
-   `test_pre_trigger_buffer`: fill circular buffer; trigger; assert pre_ms samples present in shot
-   `test_event_recording_svtshot3`: impact trigger; assert full shot in SVTSHOT3 format, pre_ms/post_ms correct
-   `test_ble_metrics_rssi`: with BLE connected; assert rssi_dbm or rssi_avg_dbm present
-   `test_ble_metrics_mtu_interval`: assert ble_mtu_size, ble_conn_interval_ms in response
-   `test_ble_metrics_packets`: assert ble_packets_tx, ble_packets_rx in response
-   `test_ble_metrics_errors`: assert ble_disconnect_count, ble_crc_error_count in response
-   **Transport (BLE):**
-   `test_event_recording_trigger_via_ble`: configure event mode; trigger via impact; CMD_GET_SHOT over BLE; assert shot present
-   `test_ble_metrics_via_ble`: RSP_STATUS/BLE_STATUS over BLE; assert BLE metrics present (rssi, mtu, etc.)

------------------------------------------------------------------------

# PHASE 6 — Configuration & Storage (Architecture §4)

## 6.1 Configuration Commands

-   CMD_SET, CMD_GET_CFG, CMD_SAVE_CFG, CMD_LOAD_CFG
-   Persist to NVS or W25Q64 config partition
-   CMD_FACTORY_RESET

## 6.2 Shot Management

-   CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_DEL_SHOT
-   CMD_FORMAT_STORAGE

## 6.3 Unit Tests

-   `test_cmd_set_get_cfg`: CMD_SET key/value; CMD_GET_CFG; assert value persisted and returned
-   `test_cmd_save_load_cfg`: CMD_SET multiple keys; CMD_SAVE_CFG; power cycle or reload; CMD_LOAD_CFG; assert config restored
-   `test_cmd_factory_reset`: CMD_FACTORY_RESET; CMD_GET_CFG; assert default values
-   `test_cmd_list_shots`: record shots; CMD_LIST_SHOTS; assert count and shot IDs match
-   `test_cmd_get_shot`: CMD_GET_SHOT id; assert valid SVTSHOT3 payload
-   `test_cmd_del_shot`: CMD_DEL_SHOT id; CMD_LIST_SHOTS; assert shot removed
-   `test_cmd_format_storage`: CMD_FORMAT_STORAGE; CMD_LIST_SHOTS; assert empty; assert config or storage reset per spec
-   **Transport (BLE):**
-   `test_config_via_ble`: CMD_SET over BLE; CMD_GET_CFG over BLE; assert value persisted
-   `test_shot_list_via_ble`: CMD_LIST_SHOTS, CMD_GET_SHOT over BLE; assert valid
-   `test_format_via_ble`: CMD_FORMAT_STORAGE over BLE; CMD_LIST_SHOTS over BLE; assert storage empty

------------------------------------------------------------------------

# COMPLETION CRITERIA

-   Phase 1: Binary protocol parser and dispatcher; stub responses for all commands; all Phase 1 unit tests pass
-   Phase 2: Internal IMU working; RSP_STATUS, RSP_DIAG, SELFTEST implemented; all Phase 2 unit tests pass
-   Phase 3: Logging pipeline; SVTSHOT3 format; start/stop recording; all Phase 3 unit tests pass
-   Phase 4: SPI bus; LSM6DSOX, ADXL375, W25Q64 drivers; CMD_BUS_SCAN; all Phase 4 unit tests pass
-   Phase 5: Multi-IMU fusion; event recording; BLE metrics; all Phase 5 unit tests pass
-   Phase 6: Config persistence; shot list/get/delete; format; all Phase 6 unit tests pass

Each phase must build, run, and pass its unit tests. OTA, device identity, and Web GUI must remain unchanged.

------------------------------------------------------------------------
