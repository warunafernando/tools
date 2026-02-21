# SmartBall BLE Binary Protocol v2 (Sense + SPI Ready)

------------------------------------------------------------------------

# 1. Overview

This document defines the SmartBall BLE Binary Protocol v2.

Key features: - Binary, little-endian framing - Internal IMU support
(XIAO nRF52840 Sense) - Future SPI IMU (LSM6DSOX) support - Future
High-G (ADXL375) support - External SPI Flash (W25Q64) support - A/B OTA
update with rollback - Device identity + serial number - Full health +
status reporting

All communication uses Nordic UART Service (NUS). No text commands.

------------------------------------------------------------------------

# 2. Frame Format

  Offset   Size   Description
  -------- ------ --------------------
  0        1      Type (message ID)
  1        2      Length (uint16 LE)
  3        N      Payload

Total size = 3 + Length.

------------------------------------------------------------------------

# 3. Identity & Versioning

RSP_ID (0x81) payload:

  Field              Type
  ------------------ ----------------------
  fw_version         uint16
  protocol_version   uint8 (this doc = 2)
  hw_revision        uint8
  uid_len            uint8
  uid                uid_len bytes

Serial number source: nRF52840 FICR DEVICEID (64-bit).

------------------------------------------------------------------------

# 4. Status & Health

RSP_STATUS (0x86) -- 48 bytes

Includes: - uptime_ms - last_error - error_flags - device_state -
imu_source_active - active_slot - pending_slot - samples_recorded -
gyro_saturation_counter - storage_used - storage_free -
battery_voltage - temperature - reset_reason - firmware_build_id

Device states: 0=BOOT 1=IDLE 2=ARMED 3=RECORDING 4=FLUSHING 5=OTA
6=ERROR

------------------------------------------------------------------------

# 5. Internal IMU (Stage 1)

imu_source parameter: 0 = INTERNAL_IMU 1 = LSM6DSOX_SPI 2 = AUTO

Streaming messages:

MSG_ACCEL (0x84) - t_ms (uint32) - ax, ay, az (float32 g)

MSG_GYRO (0x89) - t_ms (uint32) - gx, gy, gz (float32 rad/s)

------------------------------------------------------------------------

# 6. Shot File Format v3 (.svtshot)

Header: Magic: SVTSHOT3 Version: uint16 = 3 Sample rate: uint16 Count:
uint32 Sensor mask: uint8 IMU source: uint8 Header CRC32

Sample format (accel + gyro): t_ms (uint32) ax, ay, az (float32) gx, gy,
gz (float32)

Footer: CRC32 of all samples

------------------------------------------------------------------------

# 7. OTA A/B Update System

OTA Commands: 0x10 CMD_OTA_START 0x11 CMD_OTA_DATA 0x12 CMD_OTA_FINISH
0x13 CMD_OTA_ABORT 0x16 CMD_OTA_STATUS 0x17 CMD_OTA_CONFIRM

OTA Flow: 1. Start (target inactive slot) 2. Send chunks with offsets 3.
Verify CRC32 4. Mark pending 5. Reboot into test boot 6. Application
calls CONFIRM 7. If not confirmed → rollback

Safety: - OTA allowed only in DISARMED state - Battery must be above
threshold

------------------------------------------------------------------------

# 8. Future SPI Expansion

When SPI hardware added:

LSM6DSOX: - Primary motion IMU

ADXL375: - High-G impact detection

W25Q64: - External log storage - OTA staging region

Protocol remains backward compatible.
