# SmartBall Implementation Reference

Full technical documentation of the SmartBall firmware for the Seeed XIAO nRF52840 Sense, including BLE binary protocol, storage, configuration, and BLE OTA update.

**Quick reference (cite this doc in future):**
- **Direct chip read/write (debug):** §6.2 — Read/write any LSM6 (cs=0) or ADXL (cs=1) register over **BLE** (Web GUI “Chip access” tab, `/api/chip/read`, `/api/chip/write`) or **debugger/serial** (Zephyr shell: `spi read <cs> <reg> [len]`, `spi write <cs> <reg> <hex>`). Commands: CMD_SPI_READ 0x13, CMD_SPI_WRITE 0x14; response RSP_SPI_DATA 0x8D. See §3.2 / §3.3 for payload layout.

---

## 1. Overview

| Item | Value |
|------|-------|
| **Target** | Seeed XIAO nRF52840 Sense |
| **Framework** | Nordic Connect SDK (NCS) / Zephyr 3.5.99 |
| **Board** | `xiao_ble_sense` |
| **Flash** | 1 MB internal (MCUboot A/B slots) |
| **RAM** | 256 KB |
| **Device name** | SmartBall |

### 1.1 Key Paths

| Path | Purpose |
|------|---------|
| `ncs-workspace/nrf/app/` | Main application source |
| `ncs-workspace/nrf/app/src/` | C source files |
| `ncs-workspace/bootloader/mcuboot/` | MCUboot bootloader |
| `msr1_ota/` | OTA scripts, Web GUI, images |
| `scripts/` | Flash, debug, test scripts |

---

## 2. BLE Services

### 2.1 Dual GATT Services

The firmware exposes two BLE services:

1. **Nordic UART Service (NUS)** — used by mcumgr for OTA (SMP transport)
2. **SmartBall Binary Protocol (SVB1)** — custom binary protocol for app commands

### 2.2 SmartBall Binary Service (SVB1)

| UUID | Name | Role |
|------|------|------|
| `53564231-5342-4c31-8000-000000000001` | SmartBall service | Primary service |
| `53564231-5342-4c31-8000-000000000002` | RX | Host writes commands here |
| `53564231-5342-4c31-8000-000000000003` | TX | Device sends responses via GATT Indication |

- RX: write (write-without-response supported)
- TX: indicate (client must subscribe for notifications)

---

## 3. Binary Protocol

### 3.1 Frame Format

```
┌─────────┬──────────────┬────────────────────┐
│ Type    │ Length (LE)  │ Payload            │
│ 1 byte  │ 2 bytes      │ N bytes            │
└─────────┴──────────────┴────────────────────┘
```

- **Type:** Command ID (host→device) or Response ID (device→host)
- **Length:** Little-endian uint16, payload length. Must be > 0 and ≤ 240 (BLE_BIN_MAX_PAYLOAD)
- **Payload:** Command-specific or response-specific data

Frames with `plen=0` or `plen > 240` are rejected (no response).

### 3.2 Commands (Host → Device)

| ID | Name | Payload | Description |
|----|------|---------|-------------|
| 0x01 | CMD_ID | (any) | Device identity |
| 0x02 | CMD_STATUS | (any) | Status + BLE metrics |
| 0x03 | CMD_DIAG | (any) | Diagnostics (IMU, etc.) |
| 0x04 | CMD_SELFTEST | (any) | Self-test |
| 0x05 | CMD_CLEAR_ERRORS | (any) | Clear error flags |
| 0x06 | CMD_SET | klen, vlen, key\0, val | Set config key/value |
| 0x07 | CMD_GET_CFG | [0] or klen, key\0 | Get config: 0=get all |
| 0x08 | CMD_SAVE_CFG | (any) | Save config to flash |
| 0x09 | CMD_LOAD_CFG | (any) | Load config from flash |
| 0x0A | CMD_FACTORY_RESET | (any) | Factory reset |
| 0x0B | CMD_START_RECORD | [0]=0 normal, [0]=1 event | Start recording |
| 0x0C | CMD_STOP_RECORD | (any) | Stop recording |
| 0x0D | CMD_LIST_SHOTS | (any) | List stored shots |
| 0x0E | CMD_GET_SHOT | shot_id (4 LE) | Get shot by ID |
| 0x0F | CMD_DEL_SHOT | shot_id (4 LE) | Delete shot |
| 0x10 | CMD_FORMAT_STORAGE | (any) | Format storage |
| 0x11 | CMD_BUS_SCAN | (any) | Scan SPI/I2C buses |
| 0x12 | CMD_GET_SHOT_CHUNK | id(4 LE), offset(2 LE) | Get shot chunk (≤240 B) |
| 0x13 | CMD_SPI_READ | cs(1), reg(1), len(1) | Read chip register; cs: 0=LSM6, 1=ADXL |
| 0x14 | CMD_SPI_WRITE | cs(1), reg(1), data… | Write chip register |

### 3.3 Responses (Device → Host)

| ID | Name | Payload Layout |
|----|------|----------------|
| 0x81 | RSP_ID | fw_version(2), protocol_ver, hw_rev, uid_len, uid[8] |
| 0x86 | RSP_STATUS | uptime(4), last_error(4), error_flags(4), dev_state(1), samples(4), sat_int(1), sat_lsm(1), storage_used(4), storage_free(4), batt(2), temp(1), reset_reason(1), build_id(4), BLE metrics block |
| 0x87 | RSP_DIAG | imu_ready(1), whoami(1), reserved(2), voltage_mv(2 LE), temp(1) |
| 0x88 | RSP_SELFTEST | result(1) |
| 0x89 | RSP_BUS_SCAN | spi_count, i2c_count, ids… |
| 0x8A | RSP_SHOT | raw SVTSHOT3 blob |
| 0x8B | RSP_CFG | count, [klen, vlen, key, val]... |
| 0x8C | RSP_SHOT_LIST | count, [id(4), size(4)]... |
| 0x8D | RSP_SPI_DATA | data_len(2 LE), data… | SPI read response |

### 3.4 RSP_STATUS Layout (Detailed)

| Offset | Size | Field |
|--------|------|-------|
| 3 | 4 | uptime_ms (LE) |
| 7 | 4 | last_error |
| 11 | 4 | error_flags |
| 15 | 1 | device_state (1=idle, 2=recording) |
| 16 | 4 | samples_recorded |
| 20 | 1 | imu_saturation_internal |
| 21 | 1 | imu_saturation_lsm |
| 22 | 4 | storage_used_bytes |
| 26 | 4 | storage_free_bytes |
| 30 | 2 | battery (placeholder) |
| 32 | 1 | temperature (0.1°C units) |
| 33 | 1 | reset_reason |
| 34 | 4 | firmware_build_id |
| 38+ | variable | BLE metrics (rssi, mtu, packets, etc.) |

### 3.5 Protocol Constants

| Constant | Value |
|----------|-------|
| PROTOCOL_VERSION | 2 |
| FW_VERSION | 0x0100 |
| HW_REVISION | 1 |
| BLE_BIN_MAX_PAYLOAD | 240 |

---

## 4. Configuration (config.c / config.h)

- **Key max length:** 16 bytes
- **Value max length:** 32 bytes
- **Max entries:** 8
- **Backend:** NVS or storage partition

Commands: SET, GET_CFG, SAVE_CFG, LOAD_CFG, FACTORY_RESET.

**GET_CFG “get all”:** Send payload `[0x00]` (plen=1, first byte 0) to return all keys.

---

## 5. Storage & Shots

### 5.1 Storage Layout

- **Primary:** W25Q64 SPI flash (when present)
- **Fallback:** Internal flash / RAM
- **Capacity:** 16 KB (STORAGE_CAPACITY)
- **Config region:** 0–511 bytes
- **Shot region:** 512 bytes onward
- **Max shots:** 32

### 5.2 SVTSHOT3 Format

| Field | Size | Description |
|-------|------|-------------|
| magic | 8 | "SVTSHOT3" |
| version | 1 | 1 |
| _pad1 | 1 | — |
| sample_rate_hz | 2 | LE |
| count | 4 | Sample count |
| sensor_mask | 1 | — |
| imu_source_mask | 1 | — |
| _pad2 | 2 | — |
| header_crc32 | 4 | LE |
| samples | N×28 | Single-IMU: t_ms(4), ax,ay,az(12), gx,gy,gz(12) |
| footer_crc32 | 4 | LE |

- **Single-IMU sample:** 28 bytes
- **Header size:** 32 bytes
- **Footer size:** 4 bytes

---

## 6. IMU & Recording

- **Internal IMU:** LSM6DS3TR-C (XIAO Sense), via Zephyr LSM6DSL driver
- **External IMU (SPI):** LSM6DSOX, ADXL375
- **Multi-IMU:** Internal + LSM6DSOX + ADXL375; saturation counters tracked
- **Recording:** Ring buffer in RAM; writer task to flash; CMD_START_RECORD / CMD_STOP_RECORD
- **Event mode:** CMD_START_RECORD with payload[0]=1; ADXL375 trigger; pre-trigger buffer

### 6.1 Debugging zero or fixed IMU data

- **Web GUI:** After Fetch & Plot or Load, use the **Debug — IMU data check** panel. It shows `imu_source_mask` (1=Internal, 2=LSM6, 4=ADXL), first-sample values per source, and min/max per channel. If a channel shows **(all zero)** or **(constant)**, that source may be unconnected or the read may be failing.
- **BUS_SCAN:** In the Device tab, run **BUS_SCAN** to verify SPI devices (LSM6DSOX, ADXL375) are detected. If LSM6 is not present, `l_*` in shots will be zero.
- **Firmware:** `multi_imu_sample_fetch()` zeros the sample then fills only sources that init’d and read successfully. If `lsm6dsox_spi_read_accel`/`read_gyro` fail (e.g. SPI transfer error), `l_*` stay zero. Check SPI wiring, CS pin, and that the external LSM6DSOX is powered and responding.

### 6.2 Direct chip read/write (debug)

You can read or write any register on the LSM6 (cs=0) or ADXL (cs=1) for debugging.

**Over BLE**

- **Web GUI:** Open the **Chip access** tab. Choose chip (LSM6 or ADXL), enter register in hex (e.g. `0x0F`), set read length, then **Read**; or enter write data as hex (e.g. `00 01 02`) and **Write**.
- **API:** `POST /api/chip/read` body `{ "address?", "cs", "reg", "len" }` → `{ "ok", "data_hex" }`; `POST /api/chip/write` body `{ "address?", "cs", "reg", "data_hex" }` → `{ "ok" }`. Register can be decimal or hex string (e.g. `"0x0F"`).
- **Protocol:** CMD_SPI_READ (0x13) payload `[cs, reg, len]`; response RSP_SPI_DATA (0x8D) with data. CMD_SPI_WRITE (0x14) payload `[cs, reg, data...]`; response RSP_STATUS. Max read 240 bytes, max write 239 bytes. LSM6/ADXL use reg|0x80 for read, reg&0x7F for write; SPI mode 3.

**Over debugger/serial**

- With the device connected via USB (or UART console), the Zephyr shell is enabled. Use:
  - `spi read <cs> <reg> [len]` — e.g. `spi read 0 0x0F 1`
  - `spi write <cs> <reg> <hex_bytes>` — e.g. `spi write 0 0x10 0102`
- Same `spi_bus_chip_read` / `spi_bus_chip_write` are used as for BLE. Useful when debugging with a serial terminal or RTT.

**Script: read external IMU directly (BLE)**

- When recording shows no external IMU data, verify the chips on SPI with:
  ```bash
  python3 scripts/read_imu_via_ble.py [BLE_ADDR]
  ```
  Reads LSM6 WHO_AM_I (0x0F), accel/gyro regs, and ADXL DEVID/DATA. If these succeed, SPI and chips are OK; the issue is likely in multi_imu init or sample_fetch. If they fail, check wiring and CS pins.

**Compare Internal IMU vs external IMU (LSM6; impact ignored)**

- **Web GUI:** After Fetch & Plot or Load saved, the **Debug — IMU data check** panel includes **Compare Internal vs IMU**: mean (μ) per axis for Internal and IMU, and diff(μ) = Internal − IMU (accel m/s², gyro rad/s).
- **Script:** `python3 scripts/compare_internal_vs_imu.py --fetch BLE_ADDR [shot_id]` or `--file path/to/saved.json` or raw hex. Prints side-by-side first/min/max/mean and diff mean for each axis (Internal vs LSM6 only).

---

## 7. BLE OTA Update

### 7.1 Architecture

| Component | Role |
|-----------|------|
| **MCUboot** | A/B slots, test/confirm, rollback |
| **mcumgr SMP** | Management protocol for image upload |
| **Transport** | BLE (NUS) — USB serial optional |
| **Signing** | ECDSA (EC P-256); only signed images accepted |

### 7.2 Partition Layout (MCUboot A/B)

- **Slot 0 (primary):** Active firmware
- **Slot 1 (secondary):** OTA staging; new image uploaded here
- **Settings:** MCUboot metadata, confirm/rollback state

nRF52840: 1 MB flash; MCUboot + app fit in defined partitions.

### 7.3 OTA Flow

1. Host connects over BLE
2. `smpmgr` uploads signed image to slot 1
3. Host runs `image test <hash>` — marks image as test
4. Host runs `reset` — device reboots
5. MCUboot boots new image in **test** mode (not yet confirmed)
6. App calls `boot_write_img_confirmed()` — marks image permanent
7. If app does not confirm or fails health checks, MCUboot rolls back on next reboot

### 7.4 Image Signing

- **Key:** `bootloader/mcuboot/root-ec-p256.pem`
- **Tool:** `imgtool` (from mcumgr / mcuboot)
- **Build:** Sysbuild produces `zephyr.signed.bin` for OTA

### 7.5 MCUboot USB Handling (xiao_ble_sense)

Board enables USB by default. MCUboot overlay disables USB to avoid linker issues:

- `sysbuild/mcuboot/boards/xiao_ble_sense.overlay`: `&usbd { status = "disabled"; }`
- `sysbuild/mcuboot/prj.conf`: `CONFIG_USB_DEVICE_STACK=n` (if needed)

### 7.6 Host Tools

| Tool | Purpose |
|------|---------|
| `smpmgr` | mcumgr CLI; `--ble <ADDR>` for BLE |
| `msr1_ota/ota_ble_mcumgr.sh` | Upload + test + reset |
| `msr1_ota/build_ota_images.sh` | Build v1 (green) and v2 (red) images |
| `msr1_ota/ota_stress_100.sh` | OTA stress test (v1↔v2) |
| `msr1_ota/web_gui/app.py` | Web GUI for scan, upgrade, activate |

### 7.7 OTA Commands (smpmgr)

```bash
# Find device
bluetoothctl scan on   # wait 5–10 s
bluetoothctl devices

# Single OTA (default: build/app/zephyr/zephyr.signed.bin)
./msr1_ota/ota_ble_mcumgr.sh <BLE_ADDR>

# Custom image
./msr1_ota/ota_ble_mcumgr.sh <BLE_ADDR> /path/to/image.signed.bin

# With pre-check (image state-read)
./msr1_ota/ota_ble_mcumgr.sh --with-check <BLE_ADDR>
```

### 7.8 Firmware Variants (v1 / v2)

Used for OTA stress tests:

- **v1:** Single blink (green); prj_v1.conf; version 1.0.0+1
- **v2:** Double blink (red); prj_v2.conf; version 1.0.0+2

Build both:

```bash
./msr1_ota/build_ota_images.sh
# Produces msr1_ota/images/app_v1.bin, app_v2.bin
```

### 7.9 Device Identity (MCUmgr group 65)

Custom group for device identification:

- **Group ID:** 65
- **Command 0 (read):** Returns `{"serial": "<16 hex>", "part": "XIAO-BLE-SENSE"}`

Serial comes from nRF52 FICR DEVICEID.

---

## 8. Build & Flash

### 8.1 Build

```bash
cd /home/mini/tools/ncs-workspace
source .venv/bin/activate   # or: source ../.venv/bin/activate
source zephyr/zephyr-env.sh

# Standard build (prj_v1.conf)
west build -b xiao_ble_sense nrf/app --sysbuild -- -DEXTRA_CONF_FILE=prj_v1.conf

# OTA image
# build/app/zephyr/zephyr.signed.bin
```

### 8.2 Flash (via debugger)

```bash
cd /home/mini/tools
./scripts/flash_xiao.sh
# Uses OpenOCD + CMSIS-DAP; kills stray OpenOCD first
```

### 8.3 Debugging with the debugger

**Prerequisites:** CMSIS-DAP probe (e.g. Raspberry Pi Debug Probe) connected to XIAO SWD (SC→SWDCLK, SD→SWDIO, GND→GND). XIAO USB connected for serial console.

**Release the probe** (if flash/debug says "Resource busy"):

```bash
cd /home/mini/tools
source scripts/debugger_ctl.sh && ensure_debugger_free
```

**Option A — Serial shell (for chip read/write, logs):**

1. Build and flash the app (with shell enabled, see §6.2):
   ```bash
   cd /home/mini/tools/ncs-workspace
   west build -b xiao_ble_sense nrf/app --sysbuild -- -DEXTRA_CONF_FILE=prj_v1.conf
   cd /home/mini/tools && ./scripts/flash_xiao.sh
   ```
2. Connect serial to the XIAO USB port: **115200 8N1** (e.g. `screen /dev/ttyACM0 115200` or minicom).
3. Reset the device if needed; you should see the Zephyr shell prompt. Use:
   - `spi read <cs> <reg> [len]` — e.g. `spi read 0 0x0F 1` (LSM6 WHO_AM_I)
   - `spi write <cs> <reg> <hex>` — e.g. `spi write 0 0x10 01`
   - `help` for other commands.

**Option B — GDB (breakpoints, step, backtrace):**

```bash
cd /home/mini/tools
./scripts/debug_xiao.sh
```

This builds with `prj_debug.conf` (no optimizations), flashes, and starts GDB. Quit GDB with `quit` or Ctrl+D to release the probe. Useful breakpoints: `main`, `spi_bus_chip_read`, `spi_bus_chip_write`, `z_arm_hard_fault` (crashes). See `docs/DEBUG_GDB.md` for commands.

**Manual GDB (if you already built with sysbuild):**

```bash
cd /home/mini/tools/ncs-workspace
source scripts/debugger_ctl.sh && ensure_debugger_free
sudo west debug --runner openocd -- --gdb /usr/bin/gdb-multiarch
```

---

## 9. Unit Tests

### 9.1 Protocol Tests (no hardware)

```bash
python3 scripts/test_smartball_protocol.py
```

Tests: frame parser (valid, invalid length), SVTSHOT3 layout, config payload, RSP shot list format.

### 9.2 BLE Tests (device required)

```bash
python3 scripts/smartball_ble_tests.py [BLE_ADDR]
```

If BLE_ADDR is omitted, scans for "SmartBall".

22 tests: frame validation, all commands, RSP formats, config, shot list/get/delete, format, factory reset, save/load, RSP_STATUS fields, BLE metrics.

---

## 10. Configuration Files

| File | Purpose |
|------|---------|
| `nrf/app/prj.conf` | Base app config (BLE, MCUboot, mcumgr, SPI) |
| `nrf/app/prj_v1.conf` | v1 overlay (single blink) |
| `nrf/app/prj_v2.conf` | v2 overlay (double blink) |
| `nrf/app/prj_ota.conf` | OTA-specific BLE/mcumgr options |
| `nrf/app/boards/xiao_ble_sense.overlay` | LED GPIO swap (red/green) |
| `sysbuild.conf` | MCUboot enabled |
| `sysbuild/mcuboot/boards/xiao_ble_sense.overlay` | MCUboot USB disabled |

---

## 11. Key Source Files

| File | Purpose |
|------|---------|
| `main.c` | BLE init, LED blink, boot confirm |
| `ble_binary.c` | GATT service, RX/TX, workqueue |
| `binary_protocol.c` | Frame parse, command dispatch |
| `config.c` | Key/value config |
| `storage.c` | Shot index, read/write |
| `recording.c` | Start/stop, ring buffer |
| `multi_imu.c` | Internal + external IMU |
| `svtshot3.c` | SVTSHOT3 header/footer |
| `device_mgmt.c` | MCUmgr group 65 |
| `ble_metrics.c` | RSSI, MTU, packets for RSP_STATUS |
| `spi_bus.c`, `lsm6dsox_spi.c`, `adxl375_spi.c`, `w25q64_spi.c` | SPI drivers |

---

## 12. Quick Reference

| Action | Command |
|--------|---------|
| Build | `west build -b xiao_ble_sense nrf/app --sysbuild -- -DEXTRA_CONF_FILE=prj_v1.conf` |
| Flash | `./scripts/flash_xiao.sh` |
| OTA | `./msr1_ota/ota_ble_mcumgr.sh <ADDR>` |
| OTA stress | `./msr1_ota/ota_stress_100.sh <ADDR> [cycles]` |
| Protocol tests | `python3 scripts/test_smartball_protocol.py` |
| BLE tests | `python3 scripts/smartball_ble_tests.py [ADDR]` |
| Web GUI | `cd msr1_ota/web_gui && ./run.sh` → http://localhost:5050 |

---

*Document generated from current implementation. Last updated: February 2025.*
