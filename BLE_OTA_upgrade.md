# SmartBall BLE-Only OTA (Sealed Device) — Implementation Plan (Cursor / NCS)

Owner: You + Cursor
Target HW: Seeed XIAO nRF52840 Sense (nRF52840 internal flash)
Host: MS-R1 (Linux, BlueZ)
Constraint: **Sealed device** (no boot button, no USB/serial). BLE is the **only** upgrade path.
Goal: **Brick-proof BLE OTA** using **NCS + MCUboot (A/B + rollback) + mcumgr SMP over BLE + signed images + confirm gate**.

---

## 0) Success Criteria (Definition of Done)

### Functional
- Can upload a new firmware image over BLE from MS-R1 Linux.
- Device reboots into the new image as **test** (not confirmed).
- New image runs health checks and then **confirms** itself.
- If the new image fails to boot or fails health checks, device **automatically rolls back** to the last confirmed image.
- After rollback, BLE OTA is still available.

### Reliability
- 100 consecutive OTA runs succeed on bench at RSSI > -65 dBm with battery above threshold.
- 20 runs succeed at RSSI ~ -75 dBm (with adaptive pacing on host).
- Forced-failure image reliably triggers rollback 10/10 times.
- Power dip / reset during upload does not brick; resume or retry succeeds.

### Security/Integrity
- Only **signed** images are accepted.
- Image confirmation is gated on basic health checks (BLE + sensors + battery OK).

---

## 1) Repo Layout (Recommended)

Create a new repo folder structure:

- `firmware/`
  - `smartball_app/`         (Zephyr app using NCS)
  - `bootloader/`            (MCUboot via west, normally built via sysbuild)
  - `boards/`                (optional overlays for XIAO nRF52840 Sense)
  - `pm_static.yml`          (partition layout if needed)
  - `README.md`
- `tools/`
  - `msr1_ota/`
    - `ota_ble_mcumgr.sh`    (upload/test/reset/confirm wrapper)
    - `ota_stress.sh`        (loop tests + log capture)
    - `logs/`
- `docs/`
  - `OTA_PROTOCOL.md`        (workflow + commands + troubleshooting)
  - `RECOVERY_BEHAVIOR.md`   (rollback rules, boot failure counter rules)
  - `TEST_MATRIX.md`

---

## 2) Environment Setup (Cursor Task)

### Firmware machine prerequisites
- Install Nordic toolchain (NCS) and verify `west` works.
- Create and initialize a NCS workspace.

### MS-R1 Linux prerequisites
- Ensure BlueZ is installed and running.
- Install `mcumgr` (from Zephyr tools) or package if available.
- Install helper BLE tools:
  - `bluetoothctl`, `btmgmt`, `btmon`
- Verify BLE adapter is stable (disable power saving on BT if needed).

Deliverable:
- `docs/ENV_SETUP.md` with exact commands used on your MS-R1 and dev machine.

---

## 3) Firmware Architecture (NCS)

### 3.1 Core components
- **MCUboot**: Provides A/B image management, test/confirm, rollback.
- **mcumgr SMP over BLE**: Transport for uploading images over BLE GATT.
- **Signed images**: Prevent bad/corrupt images from being accepted.

### 3.2 OTA state rules (must implement)
- Upload always targets **secondary slot**.
- New image boots in **test** mode.
- New image must call **confirm** only after health checks pass.
- If new image does not confirm, MCUboot rolls back automatically on next reboot.

Deliverables:
- `docs/RECOVERY_BEHAVIOR.md` describing:
  - confirm timing
  - rollback triggers
  - boot failure counter behavior

---

## 4) Partitioning and Flash Budget (CRITICAL)

nRF52840 has 1MB internal flash. A/B requires:
- MCUboot + padding + metadata
- Slot 0 (primary)
- Slot 1 (secondary)
- Settings storage (NVS/settings)
- Optional scratch area (depends on swap mode)

Cursor tasks:
1. Build a baseline image and record:
   - `.text`, `.rodata`, `.data`, `.bss`
   - final signed image size
2. Ensure image size fits with margin in **half** the available slot allocation.

Decision rule:
- If app image is too large for half flash:
  - reduce features or
  - move assets out of flash or
  - adopt a “recovery-minimal image” approach.

Deliverable:
- `docs/FLASH_BUDGET.md` with current measured sizes and slot plan.

---

## 5) Implement BLE SMP (mcumgr) on the SmartBall App

### 5.1 Enable BLE peripheral + SMP service
Cursor tasks:
- Add required Kconfig options in `prj.conf` to enable:
  - Bluetooth peripheral
  - SMP over BLE (mcumgr transport)
  - image management group for mcumgr
  - settings/NVS backend (for persistent state)

Notes:
- Symbol names can vary by NCS version; Cursor must use the NCS docs for the exact Kconfig set.

Deliverable:
- `firmware/smartball_app/prj.conf` updated and builds cleanly.

### 5.2 BLE connection parameters tuned for OTA
Cursor tasks:
- Configure preferred connection interval for stable throughput.
- Set ATT MTU / data length updates where possible.
- Ensure flash write/erase never blocks BLE thread for long durations:
  - offload to workqueue
  - chunk writes

Deliverable:
- `docs/BLE_TUNING.md` with chosen params and rationale.

---

## 6) Implement Safe Confirm (Health-Gated)

### 6.1 Health checks required before confirm
Minimum checklist:
- BLE stack initialized and advertising/connectable
- Battery above threshold (measure using ADC)
- Sensors init ok (at least IMU responding)
- No “boot failure counter” trip

### 6.2 Confirm logic
- On boot, if current image is in “test” state:
  - run health checks for up to `T_confirm_window` seconds
  - if pass: call confirm API
  - else: do not confirm, optionally reboot to trigger rollback

Deliverable:
- `docs/CONFIRM_POLICY.md` describing:
  - threshold values
  - timing windows
  - failure actions

---

## 7) Sealed-Device Recovery Behaviors (No Buttons)

Since you cannot press boot/USB:
- OTA must remain reachable even after failures.

### 7.1 Boot-failure counter
Cursor tasks:
- Persist a boot counter across resets (settings/NVS).
- If early boot resets exceed `N_fail` within a short window:
  - enter “DFU-safe mode” where the app does minimal work but keeps BLE + SMP active.

### 7.2 DFU-safe mode requirements
- BLE advertising always on
- SMP service active
- minimal sensors (optional)
- no heavy processing that risks crashing

Deliverable:
- `docs/SAFE_MODE.md` and implemented behavior in firmware.

---

## 8) Image Signing and Versioning

Cursor tasks:
- Enable image signing in the build pipeline.
- Store signing keys securely (not inside repo if public).
- Enforce that mcumgr only accepts signed images.

Versioning:
- Embed semantic version in firmware.
- Include build ID (git short SHA) exposed over mcumgr “os” group or custom telemetry.

Deliverable:
- `docs/SIGNING.md` with:
  - key management approach
  - build steps
  - verification procedure

---

## 9) MS-R1 Linux OTA Tooling (mcumgr Wrapper)

### 9.1 Wrapper script workflow
Create `tools/msr1_ota/ota_ble_mcumgr.sh` that performs:

1. Discover device (by name / MAC)
2. Connect (ensure bonded if needed)
3. `image upload <signed.bin>`
4. `image list` and capture hash
5. `image test <hash>`
6. `reset`
7. Reconnect and poll:
   - confirm state
   - device telemetry (battery, version)
8. If healthy: `image confirm <hash>`
9. Final `image list` and save logs

Script requirements:
- Full log output saved with timestamp.
- Retry logic with backoff for connect/upload failures.
- Optional RSSI check gate (reject if below threshold).

Deliverables:
- `tools/msr1_ota/ota_ble_mcumgr.sh`
- `docs/MSR1_OTA_WORKFLOW.md`

### 9.2 Stress test runner
Create `tools/msr1_ota/ota_stress.sh`:
- Runs N times
- Collects pass/fail counts
- Saves per-run logs
- Emits a summary CSV

Deliverables:
- `tools/msr1_ota/ota_stress.sh`
- `docs/TEST_MATRIX.md` updated with pass criteria

---

## 10) Validation Plan (Bench → Ball)

### 10.1 Bench tests
- Basic OTA: upload/test/reset/confirm (10 runs)
- Rollback test:
  - upload a known-bad image that fails health checks
  - verify rollback occurs and device is still updatable (10 runs)
- Interrupt test:
  - kill BLE mid-upload, reboot host, resume/retry (10 runs)
- Battery gate:
  - emulate low battery threshold and verify OTA is refused safely

### 10.2 Pre-seal tests (inside ball but still accessible)
- Repeat stress tests with hardware in final placement
- Confirm RSSI stability at typical distances

### 10.3 After-seal acceptance test
- At least 5 successful OTAs without any physical interaction
- Confirm rollback works even after a purposely broken update

Deliverable:
- `docs/ACCEPTANCE.md` checklist to run before sealing.

---

## 11) Troubleshooting Playbook (Must Write)

Create `docs/TROUBLESHOOTING.md` containing:
- mcumgr common errors and fixes
- BlueZ quirks (MTU, bonding, caching)
- How to capture btmon logs:
  - `sudo btmon` during OTA
- How to reset BT stack on MS-R1 if stuck
- Symptoms → likely cause mapping:
  - fails at same % → pacing/MTU
  - random disconnects → power/RSSI
  - boots but never confirms → health checks failing
  - repeated rollbacks → image compatibility / confirm logic

---

## 12) Cursor Execution Order (Do This In Sequence)

1. Implement baseline NCS app build for XIAO nRF52840 Sense (BLE advertises).
2. Add MCUboot A/B with rollback; verify rollback using forced-failure image (no BLE update yet).
3. Enable mcumgr SMP over BLE; verify `mcumgr echo` and `mcumgr image list`.
4. Implement upload/test/reset flow from MS-R1 via wrapper script.
5. Implement health-gated confirm.
6. Implement boot-failure counter + DFU-safe mode.
7. Add signing and enforce signed-only.
8. Add stress test harness and run 100 cycles.
9. Write acceptance checklist and seal-ready criteria.

---

## 13) Notes / Design Constraints

- BLE OTA in a sealed device is only safe with **A/B + rollback**. No exceptions.
- Keep SMP active in normal mode or at least in a guaranteed window after boot.
- Never confirm instantly; always confirm only after the device proves BLE + sensors are stable.
- Flash operations must not starve BLE event handling.

---

## 14) Deliverables Checklist

- [x] `firmware/smartball_app/` builds with BLE
- [x] MCUboot enabled; A/B slots configured (sysbuild.conf, child_image/)
- [x] SMP over BLE configured (prj.conf)
- [x] `ota_ble_mcumgr.sh` performs upload/test/reset/confirm with logs
- [x] Health-gated confirm implemented (main.c)
- [x] Boot-failure counter + DFU-safe mode implemented (main.c)
- [x] Signing (build_signed.sh, SIGNING.md)
- [x] `ota_stress.sh` + summary CSV
- [x] Docs: ENV_SETUP, FLASH_BUDGET, SIGNING, CONFIRM_POLICY, SAFE_MODE, TEST_MATRIX, ACCEPTANCE, TROUBLESHOOTING, BLE_TUNING, MSR1_OTA_WORKFLOW, OTA_PROTOCOL

---

## 14a) BLE OTA Build — MCUboot + USB Fix (2025-02)

**Goal:** MCUboot + mcumgr SMP over BLE for sealed device (no USB).

**MCUboot USB blocker:** xiao_ble_sense board enables `CONFIG_USB_DEVICE_STACK` and has `zephyr_udc0` in devicetree. NCS adds `usb.overlay` to MCUboot when `MCUBOOT_USB_SUPPORT` (dt: zephyr_udc0 enabled), causing linker errors in MCUboot.

**Fix:**
1. `sysbuild/mcuboot/prj.conf` — add `CONFIG_USB_DEVICE_STACK=n` to override board defconfig.
2. `sysbuild/mcuboot/boards/xiao_ble_sense.overlay` — `&usbd { status = "disabled"; }` (optional DT sanity).
3. Build: `west build -b xiao_ble_sense nrf/app --sysbuild` (from ncs-workspace, venv + zephyr-env).

**Flash via debugger (OpenOCD):**
```bash
cd /home/mini/tools/ncs-workspace
source /home/mini/tools/.venv/bin/activate
source zephyr/zephyr-env.sh
west flash --runner openocd
# If probe busy: close other IDE/debug sessions, retry
```

**Debug with GDB (build with debug symbols, then attach):**
```bash
# Same build (merged.hex); debug attaches to running image
west debug --runner openocd -- --gdb /usr/bin/gdb-multiarch
# In GDB: break main / break mcumgr_bt_register / continue
```

---

## 14b) mcumgr over BLE Test

**Prereqs:** `pip install smpmgr` (in project venv). Device flashed and advertising as "SmartBall".

**Find device:**
```bash
bluetoothctl scan on   # wait 5–10 s
bluetoothctl devices   # look for SmartBall or note generic addr
bluetoothctl scan off
```

**Verify SMP (image state):**
```bash
source /home/mini/tools/.venv/bin/activate
smpmgr --ble <BLE_ADDR> image state-read
```

**OTA upload (upload + test + reset):**
```bash
./msr1_ota/ota_ble_mcumgr.sh <BLE_ADDR>
# Or: smpmgr --ble <ADDR> upgrade build/app/zephyr/zephyr.signed.bin
```

---

## 14b2) BLE Advertising EINVAL (Nordic_LBS / SmartBall not visible) — FIXED

**Symptom:** `bt_le_adv_start` returns -22 (EINVAL). Device does not appear in phone/host BLE scan.

**Root cause:** `BT_LE_ADV_CONN_NAME` adds the device name automatically, but we also passed scan response (sd) with `BT_DATA_NAME_COMPLETE`. In Zephyr `adv.c` `le_adv_update()`:

```c
if ((ad && ad_has_name(ad, ad_len)) || (sd && ad_has_name(sd, sd_len))) {
    /* Cannot use name if name is already set */
    return -EINVAL;
}
```

Duplicate name triggers EINVAL.

**Fix:** Pass `NULL, 0` for scan response when using `BT_LE_ADV_CONN_NAME`:

```c
bt_le_adv_start(BT_LE_ADV_CONN_NAME, ad, ARRAY_SIZE(ad), NULL, 0);
```

Or use `BT_LE_ADV_CONN` (no USE_NAME) and keep explicit name in sd.

**Debug GDB script:** `ncs-workspace/debug_ble_einval.gdb` — breakpoints at `valid_adv_param` and `bt_id_adv_random_addr_check` to trace EINVAL source.

---

## 14b3) MCUboot build failure (xiao_ble_sense) — FIXED

**Symptom:** MCUboot child image fails to link with undefined refs: `k_work_submit_to_queue`, `z_impl_k_sleep`, etc. (USB stack requires multithreading; MCUboot uses minimal config.)

**Root cause:** xiao_ble_sense board defconfig enables `CONFIG_USB_DEVICE_STACK=y`. MCUboot minimal config has `CONFIG_MULTITHREADING=n`; the USB stack depends on work queues and multithreading.

**Fix:** Disable USB and serial recovery for MCUboot in `child_image/mcuboot.conf`:

```
CONFIG_USB_DEVICE_STACK=n
CONFIG_MCUBOOT_SERIAL=n
```

Also use overlay `sysbuild/mcuboot/boards/xiao_ble_sense.overlay` to set `&usbd { status = "disabled"; }`.

---

## 14c) Debug Notes — BLE UsageFault (green→RGB crash) — FIXED

**Symptom:** Green LED (BLE OK) then RGB flash (reset loop).

**Root cause:** `CONFIG_LOG=n` + `CONFIG_CONSOLE=n` + `CONFIG_UART_CONSOLE=n` + custom stack overrides led to UsageFault in BLE `tx_thread`.

**Fix:** Use `CONFIG_NCS_SAMPLES_DEFAULTS=y` and `CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=2048` (match working `peripheral_lbs` sample). DIS and advertising work with this config.

**prj.conf (working):**
```
CONFIG_NCS_SAMPLES_DEFAULTS=y
CONFIG_BT=y
CONFIG_BT_PERIPHERAL=y
CONFIG_BT_DEVICE_NAME="SmartBall"
CONFIG_BT_DIS=y
CONFIG_GPIO=y
CONFIG_SYSTEM_WORKQUEUE_STACK_SIZE=2048
```

**Debug workflow (when needed):**
```bash
# Use scripts - they kill stray OpenOCD first and close debugger on exit
./scripts/debug_xiao.sh      # build + flash + GDB (closes debugger when you quit GDB)
./scripts/flash_xiao.sh      # flash only (kills stray OpenOCD first)

# Manual (ensure no other OpenOCD/GDB is running, or run debugger_ctl first)
west build -b xiao_ble_sense nrf/app -- -DEXTRA_CONF_FILE=prj_debug.conf
source scripts/debugger_ctl.sh && ensure_debugger_free && west flash --runner openocd

# Two-terminal debug: start OpenOCD, then GDB (remember to kill OpenOCD when done)
openocd -f interface/cmsis-dap.cfg -f target/nrf52.cfg -c "init" -c "halt"
gdb-multiarch -ex "target extended-remote :3333" -ex "bt full" build/zephyr/zephyr.elf
```

---

## 14d) BLE OTA debug status (as of last run)

| Step | Status |
|------|--------|
| BLE advertising EINVAL fix | OK – SmartBall visible |
| MCUboot build (xiao_ble_sense) | OK |
| Flash via OpenOCD | OK – use `./scripts/flash_xiao.sh` (kills stray debugger first) |
| mcumgr `image state-read` | OK (standalone) |
| mcumgr `upgrade` | OK – `./msr1_ota/ota_ble_mcumgr.sh <BLE_ADDR>` |

**OTA image path:** `build/app/zephyr/zephyr.signed.bin`

**Script usage:** Default runs upgrade only (recommended). Use `--with-check` to run `image state-read` first (adds ~8s delay; can hit "No Bluetooth adapters found" on upgrade in some environments).

---

## 14e) BLE OTA – "No Bluetooth adapters found"

**Symptom:** `BleakBluetoothNotAvailableError: No Bluetooth adapters found` when running `smpmgr` (or `ota_ble_mcumgr.sh`).

**Causes:** (1) Bleak uses system D-Bus to talk to BlueZ; headless / sandbox / CI may lack proper D-Bus access. (2) Running `image state-read` followed by `upgrade` in the same script can cause the second process to fail (BlueZ adapter race).

**Fixes:**
- Run `ota_ble_mcumgr.sh` with default (upgrade only): `./msr1_ota/ota_ble_mcumgr.sh <BLE_ADDR>`
- Ensure system D-Bus is reachable: `DBUS_SESSION_BUS_ADDRESS="unix:path=/var/run/dbus/system_bus_socket"` (script sets this)
- Verify BT adapter: `bluetoothctl list`
- If state-read + upgrade needed: run them separately with a few seconds between, or use `--with-check` and accept occasional retries

---

## 14f) OTA Stress Test (v1 ↔ v2, 100 cycles)

**Setup:** Two images with different versions and LEDs for reproducibility testing:
- **v1** (1.0.0+1): blinks green LED (led1)
- **v2** (1.0.0+2): blinks red LED (led0)

**Build both images:**
```bash
./msr1_ota/build_ota_images.sh
# Creates msr1_ota/images/app_v1.bin and app_v2.bin
```

**Flash v1 first** (via debugger), then run stress:
```bash
./scripts/flash_xiao.sh   # flash v1
# Get BLE addr: bluetoothctl scan on (wait 5s), bluetoothctl devices
./msr1_ota/ota_stress_100.sh <BLE_ADDR>        # 100 cycles
./msr1_ota/ota_stress_100.sh <BLE_ADDR> 5      # quick 5-cycle test
```

**Note:** Run from a normal terminal (not sandbox). If "No Bluetooth adapters found", ensure `bluetoothctl list` shows an adapter.

---

## 15) Immediate Inputs Needed (Cursor should request from you in-repo)

- NCS version (tag/commit)
- Board target used for XIAO nRF52840 Sense (board name + any overlay)
- Current app features list (to estimate flash size)
- Battery measurement method (ADC pin / divider values)
- BLE device name to advertise (e.g., `SVT-SmartBall-XXXX`)
- Desired minimum battery threshold for OTA (e.g., 3.7V under load)

End.