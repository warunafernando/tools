# MS-R1 OTA Workflow

Per BLE_OTA_upgrade.md §9.1.

## Full workflow
1. Discover device (by name "SmartBall")
2. Connect (mcumgr BLE)
3. `image upload <signed.bin>`
4. `image list` → capture hash
5. `image test <hash>`
6. `reset`
7. Wait for reboot (~15s)
8. Reconnect, poll state/telemetry
9. If healthy: `image confirm <hash>`
10. Log all output

## Script
```bash
./ota_ble_mcumgr.sh signed.bin SmartBall --confirm
```

## Logs
- `tools/msr1_ota/logs/ota_YYYYMMDD_HHMMSS.log`
