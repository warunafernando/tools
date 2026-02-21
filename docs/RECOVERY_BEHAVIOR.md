# SmartBall OTA Recovery Behavior

Per BLE_OTA_upgrade.md §3.2, §7.

## OTA state rules
- Upload always targets **secondary slot**
- New image boots in **test** mode
- New image must call **confirm** only after health checks pass
- If new image does not confirm, MCUboot rolls back automatically on next reboot

## Confirm timing
- T_confirm_window: TBD (e.g. 30s)
- Health checks must pass within window
- If pass: call confirm API
- Else: do not confirm; optionally reboot to trigger rollback

## Rollback triggers
- New image does not confirm within T_confirm_window
- Boot failure counter exceeds N_fail
- Manual revert (if supported)

## Boot failure counter
- Persisted in NVS/settings
- If early boot resets exceed N_fail within window → DFU-safe mode
- DFU-safe mode: BLE + SMP always active, minimal app
