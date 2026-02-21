# SmartBall OTA Protocol

Per BLE_OTA_upgrade.md.

## Transport
- mcumgr SMP over BLE
- GATT UUID: Zephyr SMP (standard)

## Commands
- `image upload` - upload to secondary slot
- `image list` - list slots
- `image test <hash>` - mark for test boot
- `image confirm <hash>` - confirm (after health check)
- `reset` - reboot

## Workflow
1. Upload → secondary slot
2. Test → reboot into new image (test state)
3. Device runs health checks
4. If pass: app calls boot_write_img_confirmed()
5. If fail: no confirm → MCUboot rollback on next reboot
