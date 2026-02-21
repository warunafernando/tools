#!/bin/bash
# Build v1 (green LED) and v2 (red LED) OTA images for stress test
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${SCRIPT_DIR}/../ncs-workspace"
VENV="${SCRIPT_DIR}/../.venv/bin/activate"
source "$VENV"
source "$WS/zephyr/zephyr-env.sh"

cd "$WS"

echo "=== Building v1 (green LED, 1.0.0+1) ==="
west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \
  -DEXTRA_CONF_FILE=prj_v1.conf \
  -DAPP_LED_SLOT=1
mkdir -p "${SCRIPT_DIR}/images"
cp build/app/zephyr/zephyr.signed.bin "${SCRIPT_DIR}/images/app_v1.bin"
echo "  -> images/app_v1.bin"

echo "=== Building v2 (red LED, 1.0.0+2) ==="
west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \
  -DEXTRA_CONF_FILE=prj_v2.conf \
  -DAPP_LED_SLOT=0
cp build/app/zephyr/zephyr.signed.bin "${SCRIPT_DIR}/images/app_v2.bin"
echo "  -> images/app_v2.bin"

echo ""
echo "Done. Flash v1 first, then: ./msr1_ota/ota_stress_100.sh <BLE_ADDR>"
