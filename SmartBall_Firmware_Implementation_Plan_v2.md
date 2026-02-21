# SmartBall Firmware Implementation Plan (v2)

------------------------------------------------------------------------

# Stage 1 -- XIAO Sense Only

## 1. Bootloader + OTA

-   Enable dual-slot (A/B)
-   Integrate CRC32 verification
-   Support test boot
-   Require CMD_OTA_CONFIRM before commit
-   Automatic rollback on watchdog or failure

## 2. Device Identity

-   Read FICR DEVICEID
-   Format as serial number
-   Store hardware revision
-   Report via RSP_ID

## 3. Internal IMU Bring-up

-   Initialize internal IMU
-   Configurable:
    -   accel_range
    -   gyro_range
    -   sample_rate_hz
-   Maintain gyro saturation counter
-   Timestamp using microsecond timer

## 4. Logging Pipeline

-   Ring buffer in RAM
-   Writer task for flash
-   Support continuous recording
-   Shot file format v3

## 5. BLE Command Parser

-   Binary frame parser
-   Dispatch by message ID
-   Return RSP_STATUS regularly
-   Implement streaming enable flags

## 6. Health System

-   Track:
    -   last_error
    -   error_flags
    -   reset_reason
-   SELFTEST routine:
    -   IMU init test
    -   Memory check
    -   BLE test

------------------------------------------------------------------------

# Stage 2 -- SPI Hardware

## 1. SPI Bus Manager

-   Shared SCK/MOSI/MISO
-   Separate CS lines
-   Mutex lock for bus

## 2. LSM6DSOX Driver

-   SPI WHO_AM_I check
-   Configurable ODR/range
-   Interrupt support

## 3. ADXL375 Driver

-   High-G interrupt
-   Event trigger logic

## 4. External Flash (W25Q64)

-   Log-structured storage
-   Session index
-   Power-loss recovery scan

## 5. Event Recording Mode

-   Circular pre-trigger RAM buffer
-   On impact interrupt:
    -   Save pre_ms
    -   Save post_ms

## 6. OTA Staging Upgrade

-   Store OTA image in W25Q64 staging area
-   Verify CRC
-   Copy to inactive slot
-   Reboot into test boot

------------------------------------------------------------------------

# Completion Criteria

Stage 1 Complete When: - OTA A/B verified - Internal IMU logging
stable - Status + health reporting works

Stage 2 Complete When: - SPI bus stable - LSM6 primary IMU active - ADXL
trigger works - External flash logging verified
