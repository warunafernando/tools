# Plan: Get BLE OTA Working on Linux

## Implementation Status (Completed)

The following changes were implemented in `tools/ota_ble.py`:

- **Phase 1:** Post-connect delay (1.5s), force `list(client.services)` for GATT discovery, use `BLEDevice` object
- **Phase 2:** `disconnected_callback`, `_safe_write` with error handling, reconnect-and-resume loop (5 attempts)
- **Phase 2:** Removed keepalive during READY wait (device sends MSG_OTA_PROGRESS during chunked erase)
- **Phase 2:** Connect retry (3 attempts) for transient BLE failures (e.g. br-connection-canceled)
- **Phase 2:** Early exit on disconnect during READY wait; stabilization delay (1.0s) before first OTA_DATA

**Observed:** Partial transfer to 247354/323194 bytes with successful resume from `get_status`. Full completion requires device to stay advertising; if the device reboots or stops advertising, scans will fail until it comes back.

---

This plan is based on web research, the existing SmartBall OTA docs, and the failure we observed: `BleakError: Service Discovery has not been performed yet` during the OTA_START → MSG_OTA_READY wait phase.

---

## 1. Root Cause Analysis

### 1.1 Observed Failure
- **When:** During the loop that waits for `MSG_OTA_READY` after sending `CMD_OTA_START`
- **Error:** `BleakError: Service Discovery has not been performed yet`
- **Where:** On `client.write_gatt_char(NUS_RX, build_frame(CMD_OTA_STATUS, b""), response=False)` (keepalive every 3s)

### 1.2 Likely Causes (from research)

| Cause | Source | Relevance |
|-------|--------|-----------|
| **Device disconnects during erase** | Nordic DevZone, BLE OTA guides | Device may briefly drop BLE while erasing; Bleak clears `services` on disconnect |
| **BlueZ D-Bus race** | [bluez#1489](https://github.com/bluez/bluez/issues/1489), [bleak#882](https://github.com/hbldh/bleak/issues/882) | `ServicesResolved` set before services exported; apps see empty services |
| **First connection / GATT cache** | bleak#1171, bleak docs | Cached GATT DB can cause stale or incomplete services; worse on first connect after D-Bus restart |
| **Long idle during erase** | OTA_BLE_Stability_Report.md | Even with chunked erase (4KB + yield), erase can take 15–40s; some stacks drop idle links |

---

## 2. Web Research Summary

### 2.1 Bleak / BlueZ
- **Bleak `disconnected_callback`** – Use to detect when the device drops; exit blocking waits and trigger reconnect ([Bleak docs](https://bleak.readthedocs.io/en/stable/api/client.html), [disconnect_callback example](https://github.com/hbldh/bleak/blob/develop/examples/disconnect_callback.py)).
- **BlueZ race** – `ServicesResolved` can be true before services are on D-Bus; add a short delay after connect before first GATT operation.
- **Device removal** – `bluetoothctl remove <addr>` clears cached GATT DB; can resolve “missing service” issues ([bleak#1171](https://github.com/hbldh/bleak/issues/1171)).
- **`dangerous_use_bleak_cache`** – Use when services are known and unchanged, to avoid re-waiting for discovery ([Bleak Linux backend](https://bleak.readthedocs.io/en/stable/backends/linux.html)).

### 2.2 BLE OTA Best Practices
- **Reconnect + resume** – On disconnect during transfer, rescan, reconnect, query last offset (e.g. `CMD_OTA_STATUS`), resume ([HardFault OTA guide](https://hardfault.in/2025/06/19/how-ble-devices-perform-ota-firmware-updates/)).
- **bleak-retry-connector** – Automatic retries with exponential backoff and error categorization ([bleak-retry-connector](https://github.com/bluetooth-devices/bleak-retry-connector)).
- **BleakClientWithServiceCache** – Reuse cached services for faster reconnects.
- **State machine** – Use a clear OTA state machine instead of scattered try/except.

### 2.3 Nordic nRF52
- **Connection drops** – Common during OTA; Nordic DFU libraries handle reconnect and resume.
- **Bootloader entry** – Some devices disconnect when entering DFU; reconnect after reboot.
- **MTU** – NUS uses MTU; ensure MTU exchange completes before heavy traffic.

---

## 3. Implementation Plan

### Phase 1: Low-Risk Robustness (do first)
1. **Post-connect delay**
   - Add a 1–2 second delay after `BleakClient` connect and before any GATT operation.
   - Helps avoid BlueZ `ServicesResolved` race.

2. **Force service discovery**
   - Access `list(client.services)` right after connect so discovery completes before OTA.
   - Ensures `services` are populated before `write_gatt_char`.

3. **Remove keepalive during READY wait (optional)**
   - The `CMD_OTA_STATUS` keepalive may stress the link during erase.
   - Try removing it from the initial READY loop and rely on notifications (device sends `MSG_OTA_PROGRESS` during chunked erase).

4. **Use `BLEDevice` instead of address**
   - Pass the `BLEDevice` from `BleakScanner.discover()` to `BleakClient(device, ...)` instead of `target.address`.
   - Avoids extra implicit `discover()` on connect.

### Phase 2: Disconnect Handling
5. **Add `disconnected_callback`**
   - Set an `asyncio.Event` when disconnect is detected.
   - In the READY wait loop, check this event (e.g. with `asyncio.wait`) and break on disconnect.

6. **Wrap GATT writes in try/except**
   - Catch `BleakError` (including "Service Discovery has not been performed yet").
   - Treat as “connection lost” and trigger reconnect logic.

7. **Reconnect-and-resume loop**
   - On disconnect or GATT error:
     - Leave current `BleakClient` context.
     - Rescan for SmartBall.
     - Connect with a new `BleakClient`.
     - Send `CMD_OTA_STATUS` and parse `next_expected_offset`.
     - If offset > 0: resume from `start_offset`.
     - If offset == 0: restart from `CMD_OTA_ABORT` / `CMD_OTA_START`.

### Phase 3: Deeper Fixes (if still failing)
8. **Clear BlueZ cache before OTA**
   - Run `bluetoothctl remove <addr>` (or equivalent) before connect.
   - Ensures a fresh GATT discovery.

9. **Try bleak-retry-connector**
   - Use `bleak-retry-connector` for connect with retries and backoff.
   - Reduces flakiness from transient connection failures.

10. **Verify BlueZ version**
    - Check `bluetoothctl -v`; known issues exist in older BlueZ.
    - Upgrade if possible.

11. **Firmware checks**
    - Confirm chunked erase + `s_yield()` (4KB + BLE.poll) is active.
    - Confirm `MSG_OTA_PROGRESS` is sent during erase.
    - Ensure BLE stays up during erase (no long blocking calls).

### Phase 4: Environment
12. **Physical setup**
    - Keep device within 1 m.
    - Reduce interference (Wi‑Fi, other BLE devices).

13. **USB vs battery**
    - Test with device on battery (no USB) to rule out USB/BLE interactions (LFCLK, etc.).
    - `USE_LFSYNT` should already address USB+BLE on XIAO.

---

## 4. Suggested Code Changes (summary)

| File | Change |
|------|--------|
| `ota_ble.py` | Add 1–2s delay after connect; access `list(client.services)` before OTA |
| `ota_ble.py` | Use `BLEDevice` object instead of address string |
| `ota_ble.py` | Add `disconnected_callback` and `asyncio.Event` for disconnect |
| `ota_ble.py` | Wrap keepalive and other GATT writes in try/except for `BleakError` |
| `ota_ble.py` | Implement reconnect loop: on error/disconnect → rescan → connect → `CMD_OTA_STATUS` → resume |
| `ota_ble.py` | Optionally remove or reduce keepalive during READY wait |

---

## 5. References

- [Bleak Disconnect Callback Example](https://github.com/hbldh/bleak/blob/develop/examples/disconnect_callback.py)
- [Bleak Linux Backend Docs](https://bleak.readthedocs.io/en/stable/backends/linux.html)
- [BlueZ ServicesResolved Race (bluez#1489)](https://github.com/bluez/bluez/issues/1489)
- [Bleak Service Discovery (bleak#1171)](https://github.com/hbldh/bleak/issues/1171)
- [How BLE Devices Perform OTA (HardFault)](https://hardfault.in/2025/06/19/how-ble-devices-perform-ota-firmware-updates/)
- [bleak-retry-connector](https://github.com/bluetooth-devices/bleak-retry-connector)
- `OTA_BLE_Stability_Report.md` – SmartBall OTA design
- `BLE_Failure_Investigation_USB_Connected.md` – USB + BLE (USE_LFSYNT)
