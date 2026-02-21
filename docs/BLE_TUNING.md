# SmartBall BLE Tuning for OTA

Per BLE_OTA_upgrade.md §5.2.

## Connection parameters
- MTU: 247 (CONFIG_BT_L2CAP_TX_MTU)
- Data length: 251 (CONFIG_BT_CTLR_DATA_LENGTH_MAX)
- ACL TX: 251 (CONFIG_BT_BUF_ACL_TX_SIZE)

## Rationale
- Larger MTU improves throughput for image upload
- Flash operations must not block BLE thread (offload to workqueue, chunked writes)
- mcumgr transport uses BLE GATT; larger packets reduce round-trips
