# SmartBall Pre-Seal Acceptance Checklist

Per BLE_OTA_upgrade.md §10.3.

## Before sealing
- [ ] At least 5 successful OTAs without physical interaction
- [ ] Rollback works (upload bad image, verify rollback)
- [ ] Device still updatable after rollback
- [ ] Stress test: 100 runs pass at good RSSI
- [ ] Battery gate: OTA refused when battery below threshold

## After-seal
- [ ] At least 5 successful OTAs with hardware in final placement
- [ ] Confirm RSSI stability at typical distances
