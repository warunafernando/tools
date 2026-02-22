#!/bin/bash
# Build v1 (single blink) and v2 (double blink) - pattern distinguishes when LED color same
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WS="${SCRIPT_DIR}/../ncs-workspace"
VENV="${SCRIPT_DIR}/../.venv/bin/activate"
source "$VENV"
source "$WS/zephyr/zephyr-env.sh"
# Use gnuarmemb if Zephyr SDK not available
export ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb
export GNUARMEMB_TOOLCHAIN_PATH=/usr

cd "$WS"

echo "=== Building v1 (single-blink pattern, 1.0.0+1) ==="
west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \
  -DEXTRA_CONF_FILE=prj_v1.conf \
  -DAPP_LED_SLOT=0
mkdir -p "${SCRIPT_DIR}/images"
cp build/app/zephyr/zephyr.signed.bin "${SCRIPT_DIR}/images/app_v1.bin"
echo "  -> images/app_v1.bin"

echo "=== Building v2 (double-blink pattern, 1.0.0+2) ==="
west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \
  -DEXTRA_CONF_FILE=prj_v2.conf \
  -DAPP_LED_SLOT=0
cp build/app/zephyr/zephyr.signed.bin "${SCRIPT_DIR}/images/app_v2.bin"
echo "  -> images/app_v2.bin"

echo ""
echo "Done. Flash v1 first, then: ./msr1_ota/ota_stress_100.sh <BLE_ADDR>"
