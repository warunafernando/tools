# SmartBall Confirm Policy

Per BLE_OTA_upgrade.md §6.

## Threshold values
- **Battery**: ≥ 3700 mV (BATTERY_THRESHOLD_MV)
- **T_confirm_window**: 30 seconds
- **N_fail (boot counter)**: 3

## Timing
1. New image boots in **test** state
2. App runs health checks for up to T_confirm_window
3. If all checks pass: call `boot_write_img_confirmed()`
4. If window expires without confirm: do nothing; MCUboot rolls back on next reboot

## Health checks (minimum)
- BLE stack initialized and advertising
- Battery above threshold (ADC)
- Sensors init OK (IMU responding)
- Boot failure counter < N_fail

## Failure actions
- Health check fail: do not confirm; optional reboot to trigger rollback
- Boot failure overflow: enter DFU-safe mode
