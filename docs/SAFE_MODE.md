# SmartBall DFU-Safe Mode

Per BLE_OTA_upgrade.md §7.

## Trigger
- Boot failure counter ≥ N_fail (3) within short window
- Persisted in settings (boot/cnt)

## Behavior
- BLE advertising always on
- SMP service active (mcumgr OTA available)
- Minimal processing (no heavy sensor/processing that could crash)
- LED or status indication optional

## Requirements
- OTA must remain reachable after any failure
- No physical interaction (no buttons)
