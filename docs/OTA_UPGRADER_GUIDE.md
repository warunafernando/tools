# BLE OTA Upgrader — Run Guide

How to run OTA upgrades and stress tests for SmartBall (Seeed XIAO nRF52840 Sense).

---

## Prerequisites

- **Board:** Seeed XIAO nRF52840 Sense (xiao_ble_sense)
- **Host:** Linux with BlueZ, D-Bus, and Python 3
- **Probe:** CMSIS-DAP (e.g. Raspberry Pi Debug Probe) for initial flash
- **Tools:**
  - NCS workspace at `ncs-workspace` with venv at `.venv`
  - `smpmgr` installed in venv: `pip install smpmgr`

---

## 1. Build Images

### Two-version images (v1 / v2 for stress test)

```bash
cd /home/mini/tools
./msr1_ota/build_ota_images.sh
```

Produces:
- `msr1_ota/images/app_v1.bin` — green LED, version 1.0.0+1
- `msr1_ota/images/app_v2.bin` — red LED, version 1.0.0+2

### Single image (normal build)

```bash
cd /home/mini/tools/ncs-workspace
source .venv/bin/activate
source zephyr/zephyr-env.sh
west build -b xiao_ble_sense nrf/app --sysbuild
```

OTA image: `build/app/zephyr/zephyr.signed.bin`

---

## 2. Flash Initial Firmware

Use SWD via OpenOCD. If another debugger is using the probe, close it first.

```bash
cd /home/mini/tools
./scripts/flash_xiao.sh
```

Or manually:

```bash
cd ncs-workspace
source .venv/bin/activate
source zephyr/zephyr-env.sh
west flash --runner openocd
```

---

## 3. Find the Device BLE Address

```bash
bluetoothctl scan on
# Wait 5–10 seconds
bluetoothctl devices
bluetoothctl scan off
```

Note the address for SmartBall (e.g. `F9:C6:99:8C:38:30`). It may change after reboot.

---

## 4. Run OTA Upgrade (Single Image)

```bash
cd /home/mini/tools
./msr1_ota/ota_ble_mcumgr.sh <BLE_ADDR>
```

Example:
```bash
./msr1_ota/ota_ble_mcumgr.sh F9:C6:99:8C:38:30
```

**Image:** Uses `build/app/zephyr/zephyr.signed.bin` by default. Override:
```bash
./msr1_ota/ota_ble_mcumgr.sh <BLE_ADDR> /path/to/image.bin
```

**Optional pre-check:**
```bash
./msr1_ota/ota_ble_mcumgr.sh --with-check <BLE_ADDR>
```
Runs `image state-read` before upgrade. May add ~8s and can hit "No Bluetooth adapters found" in some setups.

---

## 5. Run OTA Stress Test (v1 ↔ v2, 100 cycles)

1. Flash v1 first (or ensure device is on v1):
   ```bash
   cd ncs-workspace && west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \
     -DEXTRA_CONF_FILE=prj_v1.conf -DAPP_LED_SLOT=1
   ./scripts/flash_xiao.sh
   ```

2. Build both images:
   ```bash
   ./msr1_ota/build_ota_images.sh
   ```

3. Run stress test:
   ```bash
   ./msr1_ota/ota_stress_100.sh <BLE_ADDR>
   ```

   Quick 5-cycle test:
   ```bash
   ./msr1_ota/ota_stress_100.sh <BLE_ADDR> 5
   ```

**LEDs:**
- v1 = green blinking
- v2 = red blinking

**Logs:** `msr1_ota/logs/stress_*.log`

---

## 6. Troubleshooting

### "No Bluetooth adapters found"

- Run from a normal terminal (not a sandboxed IDE shell)
- Ensure: `bluetoothctl list` shows an adapter
- Script sets `DBUS_SESSION_BUS_ADDRESS="unix:path=/var/run/dbus/system_bus_socket"`

### Stress test fails on second upgrade

- Retry logic handles transient errors (BlueZ adapter race, disconnects)
- If failures persist, run from a normal terminal
- Check `msr1_ota/logs/` for details

### Probe / debugger busy

```bash
./scripts/debugger_ctl.sh
# Then retry flash
```

### Device not advertising

- Power cycle the board
- Confirm it was flashed successfully
- Rescan: `bluetoothctl scan on` (wait 10s)

---

## 7. Quick Reference

| Action | Command |
|--------|---------|
| Build v1+v2 | `./msr1_ota/build_ota_images.sh` |
| Flash | `./scripts/flash_xiao.sh` |
| Single OTA | `./msr1_ota/ota_ble_mcumgr.sh <ADDR>` |
| Stress 100 | `./msr1_ota/ota_stress_100.sh <ADDR>` |
| Stress 5 | `./msr1_ota/ota_stress_100.sh <ADDR> 5` |
| Find device | `bluetoothctl scan on` then `bluetoothctl devices` |
