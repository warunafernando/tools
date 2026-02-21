# BLE OTA Firmware Behavior Analysis

## Observed Failure

- OTA_START ack received
- MSG_OTA_READY never received
- "Connection lost at 0/314290: Not connected" when sending first OTA_DATA

## Root Causes

### 1. Connection drops during erase wait

The host waits up to 90s for MSG_OTA_READY. During that time, traffic is:
- Device → Host: MSG_OTA_PROGRESS every 500ms, then MSG_OTA_READY when done
- Host → Device: nothing (host is idle)

BLE supervision timeout is typically 2–20 seconds. If the device does not send enough traffic, the central can disconnect. Possible causes:
- Device blocking in `flash.erase()` (20–50ms per 4KB) without calling `BLE.poll()`
- Notifications not reaching the host
- Windows BLE stack dropping the link

### 2. CMD_OTA_DATA silently ignored when not ready

In `ota.cpp` line 230:
```c
if (s_state != OTA_READY_FOR_DATA && s_state != OTA_RECEIVING) break;
```
When the device is still in `OTA_PREPARE_ERASE`, OTA_DATA is dropped with no response. The host keeps retrying and sees no ACKs.

### 3. Progress/ready notifications may not reach host

`ota_send_ble()` returns -1 when `!txChar.subscribed()`, so no BLE notifications are sent. Subscription can be lost if the connection drops or CCCD is cleared.

### 4. Single 4KB erase blocks BLE

In `ota_poll()`, each `flash.erase(4096)` blocks ~20–50ms. During that time `BLE.poll()` is not called. That can cause:
- Missed link layer events
- Delayed or failed notifications
- Supervision timeout on slow links

## Firmware Fixes Applied

1. **More frequent progress**: OTA_PROGRESS_INTERVAL_MS 500 → 250 ms
2. **Respond to OTA_DATA when not ready**: In PREPARE_ERASE, send RSP_OTA with BAD_OFFSET or a “busy” hint so the host knows to retry later
3. **Extra BLE.poll before long ops**: Call `s_yield()` before erase when possible
