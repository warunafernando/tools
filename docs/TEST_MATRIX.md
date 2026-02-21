# SmartBall OTA Test Matrix

Per BLE_OTA_upgrade.md §9.2, §10.

## Pass criteria
- 100 consecutive OTAs at RSSI > -65 dBm
- 20 runs at RSSI ~ -75 dBm (adaptive pacing)
- Rollback test: 10/10 forced-failure triggers rollback
- Interrupt/resume: 10/10 succeed

## Bench tests
| Test | Runs | Pass |
|------|------|------|
| Basic OTA (upload/test/reset/confirm) | 10 | |
| Rollback (bad image) | 10 | |
| Interrupt mid-upload, resume | 10 | |
| Battery gate (low battery) | 1 | |

## Stress run
```bash
./ota_stress.sh signed.bin 100
```

## Output
- `logs/stress_YYYYMMDD_HHMMSS.csv`: run,result,elapsed_sec
- Per-run logs in `logs/`
