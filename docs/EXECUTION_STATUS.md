# BLE_OTA_upgrade — Execution Status

Per §12 Cursor Execution Order.

## Completed
- [x] **Step 1**: Baseline NCS app (BLE advertises)
- [x] **Step 2**: MCUboot A/B (sysbuild.conf, child_image/mcuboot.conf)
- [x] **Step 3**: mcumgr SMP over BLE (prj.conf)
- [x] **Step 4**: ota_ble_mcumgr.sh (upload/test/reset/confirm)
- [x] **Step 5**: Health-gated confirm (main.c)
- [x] **Step 6**: Boot-failure counter + DFU-safe mode (main.c)
- [x] **Step 7**: Signing (build_signed.sh, SIGNING.md)
- [x] **Step 8**: ota_stress.sh
- [x] **Step 9**: Docs: ENV_SETUP, FLASH_BUDGET, SIGNING, CONFIRM_POLICY, SAFE_MODE, TEST_MATRIX, ACCEPTANCE, TROUBLESHOOTING, BLE_TUNING, MSR1_OTA_WORKFLOW, OTA_PROTOCOL

## Build (with NCS installed)
1. Install NCS (docs/ENV_SETUP.md)
2. Copy `firmware/smartball_app` into NCS `app/`
3. `west build -b xiao_ble app/smartball_app --sysbuild`
4. Sign: `./scripts/build_signed.sh` or see docs/SIGNING.md
5. Flash: `west flash`
