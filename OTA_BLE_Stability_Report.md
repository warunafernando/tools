# Stable OTA Update over BLE – What Was Done and What Was Found

This document summarizes the work to make SmartBall firmware updates over BLE stable: root cause, changes made, and how to use the tools.

---

## 1. Goal

- Support **OTA over BLE** (Nordic UART Service, NUS) with a **single image**: load → verify checksum → activate (reboot) → confirm device is back online.
- Avoid requiring a power cycle for reliability; identify and fix causes of failed or flaky BLE OTA.

---

## 2. What Was Found (Root Cause of Unstable BLE OTA)

### 2.1 Main cause: blocking flash erase during OTA_START

**Observation:** BLE OTA often failed with “OTA_START failed” or “Not connected” shortly after connecting, or the connection dropped at the first data chunk.

**Root cause:** On the device, handling **CMD_OTA_START** did a **single, long flash erase** of the entire staging region (~496 KB) with **no BLE processing** in between:

- `ota_feed()` ran synchronously: `flash.erase(OTA_SLOT_B_ADDR, sz)` for the full size.
- Erase can take **many seconds** (e.g. 10–30+ s) on the nRF52.
- During that time the main loop did not run, so **`BLE.poll()` was never called**.
- The link looked dead to the central (Windows): supervision/connection timeouts or “Not connected” when the host retried or sent the first OTA_DATA.

So the instability came from the **device blocking for a long time during erase** without servicing BLE.

### 2.2 Other contributing factors

- **Host timeout:** The host only waited a few seconds for the OTA_START response; with a long erase, the device could not reply in time.
- **No delay after OTA_START:** Sending OTA_DATA immediately after START could stress the link before the device was ready.
- **Deploying the fix:** The fix lives in new firmware; the device had to receive that firmware at least once (e.g. via Serial OTA) before BLE OTA could benefit from it.

---

## 3. What Was Done

### 3.1 Firmware (device) – `firmware/src/ota.cpp`

- **Chunked erase with BLE yield**
  - Replaced the single `flash.erase(OTA_SLOT_B_ADDR, sz)` with erase in **4 KB chunks**.
  - After each 4 KB erase, the code calls **`s_yield()`**, which runs **`BLE.poll()`** (see `main_ota_ble.cpp`), so the connection is serviced during erase.
  - Constants added:
    - `OTA_ERASE_PAGE = 4096` for erase chunk size.
    - Existing `OTA_FLASH_PAGE = 64` was already used for program chunks with yield during OTA_DATA.

- **Result:** The device stays responsive on BLE during OTA_START and can send the OTA_START ack within a reasonable time (typically 15–40 s depending on flash size).

### 3.2 Host – `tools/ota_ble.py`

- **Longer timeout for OTA_START**
  - Added **`OTA_START_RESP_TIMEOUT = 60.0`** seconds (later increased from 45 s) for the OTA_START response only.
  - Other responses still use `RESP_TIMEOUT = 8.0` s.

- **Stabilization delay after OTA_START**
  - After receiving “OTA_START ok”, the script **waits 1 second** before sending the first OTA_DATA chunk, to let the connection and device state settle.

- **Post-reboot online check**
  - After sending CMD_OTA_REBOOT, the script waits (default 10 s), then **scans for “SmartBall”** and reports “Device online: &lt;address&gt;” or “Device not seen after reboot”.
  - Exit code 0 only if OTA completes and the device is seen again; otherwise exit 1.

### 3.3 Serial OTA – deploying the fix without power cycle

- **`tools/ota_serial.py`** was adjusted for reliability when the device is left in a bad state or resets on open:
  - **Boot wait:** After opening the COM port, wait **4 seconds** so the device can boot (if it resets when the port is opened).
  - **Double OTA_ABORT:** Send **CMD_OTA_ABORT** twice with short delays before CMD_OTA_START to clear any previous OTA state (e.g. OTA_RECEIVING).
  - **Longer timeouts:** 20–30 s for serial responses so the device has time to finish erase and respond.

- **Usage:** With the SmartBall on USB (e.g. COM16):
  ```bash
  python ota_serial.py COM16 fw_v1.bin 1
  ```
  After one successful Serial OTA, the device runs the firmware that includes the **chunked erase** fix; from then on, BLE OTA can be more stable.

### 3.4 BLE OTA flow (single image: load → checksum → activate → verify)

- **Load:** Transfer image in 128-byte chunks with **per-chunk CRC**; device rejects bad chunks (0x05) and host retries (up to 4 times per chunk).
- **Checksum:** At **CMD_OTA_FINISH** the device checks the **full-image CRC**; on mismatch it reports error and does not set the pending flag.
- **Activate:** Host sends **CMD_OTA_REBOOT**; device reboots and the bootloader applies the new image (A/B swap).
- **Verify online:** Host waits, then scans for “SmartBall” and reports whether the device is seen again.

**Command:**
```bash
python ota_ble.py <firmware.bin> [version]
# Example:
python ota_ble.py fw_v2.bin 2
```

---

## 4. Files Touched

| Location | Change |
|--------|--------|
| `firmware/src/ota.cpp` | Chunked flash erase (4 KB) with `s_yield()` between chunks during OTA_START. |
| `firmware/include/ota.h` | (No API change; OTA_ERASE_PAGE is internal in ota.cpp.) |
| `tools/ota_ble.py` | `OTA_START_RESP_TIMEOUT`, 1 s delay after OTA_START, `wait_for_device_online()` after reboot. |
| `tools/ota_serial.py` | 4 s boot wait after open, double ABORT before START, longer timeouts. |
| `tools/ble_find.py` | Helper to find SmartBall by name or by probing NUS on unnamed devices. |
| `tools/ota_ble_stress_test.py` | 100-run BLE OTA stress test (A/B images), with optional log file. |
| `tools/fw_v1.bin`, `tools/fw_v2.bin` | Pre-built A/B test images (from `ota_ble_v1`, `ota_ble_v2`). |

---

## 5. Current Status and Remaining Observations

- **Serial OTA:** Works reliably when the device is in a good state (e.g. after unplug/replug and 4 s boot wait). Used successfully to deploy the chunked-erase firmware.
- **BLE OTA – OTA_START:** With the new firmware on the device, OTA_START has been observed to **succeed** (device ack received), so the chunked-erase + yield fix is effective when the new image is running.
- **BLE OTA – full run:** Full BLE OTA runs (load → checksum → activate → verify online) can still be affected by:
  - **Connection drop during the OTA_START phase:** Even with chunked erase, the device may take 15–40 s to erase and send the ack. Some Windows BLE stacks or environments may still drop the link if there is no traffic for a long time.
  - **Connection drop at start of OTA_DATA:** Occasionally the link drops right after OTA_START ok (e.g. “Connection lost at 0/size”).
  - **“OTA_START failed”** after several retries: Device may be in a state where it does not accept START, or the notification with the ack is not received (stack/radio behavior).

**Recommendations for most reliable BLE OTA:**

1. **Deploy the fixed firmware once via Serial OTA** (USB connected), then reboot the device.
2. **Keep the SmartBall close** to the host (e.g. within 1 m) during BLE OTA.
3. **Reboot the device** (RESET or unplug/replug) if the previous BLE OTA attempt left it in an unclear state, then run BLE OTA again.
4. Use **`ble_find.py`** to confirm the device is advertising before starting BLE OTA.

---

## 6. Full Autonomous OTA Stabilization Plan (Implemented)

Per **SmartBall_Full_Autonomous_OTA_Stabilization_Plan.md** the following is in place:

- **Device:** OTA state machine (IDLE → PREPARE_ERASE → READY_FOR_DATA → RECEIVING → VERIFYING → PENDING_REBOOT); immediate OTA_START ACK; background 4 KB sector erase with `ota_poll()` and MSG_OTA_PROGRESS every 500 ms; MSG_OTA_READY when done; OTA_DATA with `next_expected_offset`, BAD_OFFSET for out-of-order, re-ACK for duplicate; sliding window (host ≤ 4 chunks ahead); OTA_FINISH verifies CRC and reboots; 30 s pending-confirm timer with rollback; extended CMD_OTA_STATUS (24 bytes); ring buffer log and CMD_OTA_GET_LOG.
- **Host:** Golden flow: ABORT → START → wait for MSG_OTA_READY (or legacy 0x90 0x00) → OTA_DATA with window 4 → OTA_FINISH → wait reboot → verify online. Resume after disconnect: reconnect, CMD_OTA_STATUS, resume from `next_expected_offset`. Chunk ACK timeout 3 s, 5 retries.
- **Fallback:** `ota_auto.py` tries BLE first; on failure or if SmartBall not found, falls back to Serial OTA (USB).

## 7. Quick Reference

| Task | Command |
|------|--------|
| **OTA (BLE first, then Serial)** | `python tools/ota_auto.py tools/fw_v1.bin 1 [--serial-port COM16]` |
| Find SmartBall (BLE) | `python tools/ble_find.py [--timeout 20] [--probe-all]` |
| Serial OTA (device on USB) | `python tools/ota_serial.py COM16 tools/fw_v1.bin 1` |
| BLE OTA (with resume) | `python tools/ota_ble.py tools/fw_v2.bin 2` |
| BLE OTA stress test (100 runs) | `python tools/ota_ble_stress_test.py --runs 100` |
| Build A/B images | `cd firmware && pio run -e ota_ble_v1 -e ota_ble_v2` |

---

*Report updated after Full Autonomous OTA Stabilization Plan. Firmware: immediate START ack, background erase, sliding window, resume; host: wait READY, window 4, resume; BLE fail → Serial fallback.*
