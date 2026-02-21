# SmartBall BLE OTA Troubleshooting

Per BLE_OTA_upgrade.md §11.

## mcumgr errors
| Error | Likely cause | Fix |
|-------|--------------|-----|
| Connection timeout | Device not advertising, name mismatch | Check device name, scan with bluetoothctl |
| Upload fails at same % | MTU/ pacing | Reduce chunk size, increase delays |
| image test fails | Slot full, invalid image | Abort, retry; verify signed image |

## BlueZ quirks
- **MTU**: Ensure CONFIG_BT_L2CAP_TX_MTU matches
- **Bonding**: Unpair if connection fails: `bluetoothctl remove <addr>`
- **Cache**: Restart BlueZ: `sudo systemctl restart bluetooth`

## btmon
```bash
sudo btmon
# Run OTA in another terminal; inspect GATT/ATT traffic
```

## Reset BT on MS-R1
```bash
sudo systemctl restart bluetooth
sudo hciconfig hci0 down && sudo hciconfig hci0 up
```

## Symptoms → cause
| Symptom | Cause |
|---------|-------|
| Fails at same % | Pacing, MTU |
| Random disconnects | Power, RSSI |
| Boots but never confirms | Health checks failing |
| Repeated rollbacks | Image bug, confirm logic |
