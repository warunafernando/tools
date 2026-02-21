# SmartBall Implementation Plan — XIAO nRF52840 Sense Only

## Scope

- **Hardware:** XIAO nRF52840 Sense only (no SPI sensors, no external flash)
- **Onboard:** nRF52840 MCU, internal IMU (LSM6DS3TR on Sense), on-chip flash, BLE, FICR identity
- **Communication:** Nordic UART Service (NUS), binary protocol v2

---

## 1. Project Setup & Build System

| Task | Description |
|------|-------------|
| 1.1 | Create nRF Connect SDK (or Arduino) project for XIAO nRF52840 Sense |
| 1.2 | Set board target to `xiao_nrf52840_sense` |
| 1.3 | Enable NUS for BLE communication |
| 1.4 | Configure build/flash workflow (west/nrfjprog or Arduino CLI) |

---

## 2. Bootloader & OTA A/B

| Task | Description |
|------|-------------|
| 2.1 | Enable MCUboot (or equivalent) with A/B slots |
| 2.2 | Implement CRC32 verification of OTA image before commit |
| 2.3 | Implement test boot (boot new image, keep old as fallback) |
| 2.4 | Require `CMD_OTA_CONFIRM` before swapping slots |
| 2.5 | Automatic rollback on watchdog or boot failure |
| 2.6 | OTA only when device state = DISARMED and battery above threshold |

---

## 3. Device Identity

| Task | Description |
|------|-------------|
| 3.1 | Read `FICR->DEVICEID[0]` and `DEVICEID[1]` (64-bit) |
| 3.2 | Format as serial/UID for `RSP_ID` |
| 3.3 | Define hardware revision (e.g. 0x01 = Sense-only) |
| 3.4 | Implement `RSP_ID` frame: fw_version, protocol_version=2, hw_revision, uid |

---

## 4. Internal IMU Bring-up

| Task | Description |
|------|-------------|
| 4.1 | Initialize LSM6DS3TR (I²C on XIAO Sense) |
| 4.2 | Configurable `accel_range`, `gyro_range`, `sample_rate_hz` |
| 4.3 | Maintain gyro saturation counter |
| 4.4 | Use RTC or cycle counter for microsecond timestamps |
| 4.5 | Use `imu_source = 0` (INTERNAL_IMU) |

---

## 5. BLE Command Parser

| Task | Description |
|------|-------------|
| 5.1 | Implement binary frame parser: Type (1) + Length (2 LE) + Payload (N) |
| 5.2 | Dispatch by message ID, handle unknown IDs gracefully |
| 5.3 | Implement `RSP_STATUS` (48 bytes) with all required fields |
| 5.4 | Implement streaming enable flags for MSG_ACCEL (0x84) and MSG_GYRO (0x89) |
| 5.5 | Send `RSP_STATUS` at regular intervals |
| 5.6 | Implement OTA commands: 0x10–0x13, 0x16, 0x17 |

---

## 6. Logging Pipeline (On-Chip Flash)

| Task | Description |
|------|-------------|
| 6.1 | Define ring buffer in RAM for samples |
| 6.2 | Writer task that flushes ring buffer to on-chip flash |
| 6.3 | Shot file format v3 (.svtshot): magic, version, sample rate, count, sensor mask, header CRC32 |
| 6.4 | Sample format: t_ms, ax/ay/az, gx/gy/gz (float32) |
| 6.5 | Footer CRC32 over all samples |
| 6.6 | Support continuous recording (limited by on-chip flash capacity) |

---

## 7. Health System

| Task | Description |
|------|-------------|
| 7.1 | Track `last_error`, `error_flags`, `reset_reason` |
| 7.2 | SELFTEST routine: IMU init, memory check, BLE test |
| 7.3 | Expose health via `RSP_STATUS` |
| 7.4 | Device states: BOOT, IDLE, ARMED, RECORDING, FLUSHING, OTA, ERROR |

---

## 8. State Machine

| State | Description | Transitions |
|-------|-------------|-------------|
| BOOT | Startup, SELFTEST | → IDLE or ERROR |
| IDLE | Ready, not recording | → ARMED, OTA |
| ARMED | Armed, waiting for trigger | → RECORDING |
| RECORDING | Capturing IMU data | → FLUSHING |
| FLUSHING | Writing buffers to flash | → IDLE |
| OTA | OTA in progress | → IDLE or ERROR |
| ERROR | Error state, halt | → IDLE after recovery |

---

## 9. Implementation Order

```
Phase 1: Foundation
  1. Project setup (1.1–1.4)
  2. Device identity (3.1–3.4)
  3. BLE parser skeleton + RSP_ID + RSP_STATUS (5.1–5.5)

Phase 2: IMU & Logging
  4. Internal IMU bring-up (4.1–4.5)
  5. Streaming (MSG_ACCEL, MSG_GYRO) (5.4)
  6. Logging pipeline + Shot v3 (6.1–6.6)

Phase 3: OTA & Health
  7. Bootloader + OTA A/B (2.1–2.6)
  8. Health system + SELFTEST (7.1–7.4)
```

---

## 10. Constraints & Assumptions (Sense-Only)

| Item | Value |
|------|-------|
| IMU | LSM6DS3TR over I²C |
| Storage | On-chip flash only (no W25Q64) |
| OTA staging | Use secondary app slot only |
| `storage_used` / `storage_free` | On-chip flash partition used for logs |
| `battery_voltage` | ADC from battery sense pin if available; else 0 or placeholder |
| `temperature` | Internal nRF52840 temp sensor |

---

## 11. Completion Criteria (Stage 1)

- [ ] OTA A/B verified with rollback
- [ ] Internal IMU streaming stable
- [ ] Shot v3 logging to on-chip flash working
- [ ] RSP_STATUS and RSP_ID reporting correctly
- [ ] Health/SELFTEST implemented
- [ ] State machine operational
