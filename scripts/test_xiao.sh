#!/bin/bash
# Build test image, flash via debugger, and start GDB for unit tests
# Run with: ./scripts/test_xiao.sh
# In GDB: break ztest_run_all  then  continue  to run tests
# Test output appears on USB serial - use: screen /dev/ttyACM0 115200 (or minicom)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/debugger_ctl.sh"
cd /home/mini/tools
source .venv/bin/activate
source ncs-workspace/zephyr/zephyr-env.sh
export ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb
export GNUARMEMB_TOOLCHAIN_PATH=/usr

ensure_debugger_free

echo "Building test image (ztest + V1 config)..."
cd ncs-workspace
west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \
  -DEXTRA_CONF_FILE=prj_test.conf \
  -DEXTRA_CONF_FILE=prj_v1.conf \
  -DAPP_LED_SLOT=0

echo ""
echo "Flashing test image via debugger..."
west flash --runner openocd

echo ""
echo "To run unit tests with GDB:"
echo "  sudo west debug --runner openocd -- --gdb /usr/bin/gdb-multiarch"
echo "  In GDB: continue  (tests run automatically)"
echo ""
echo "To see test output: connect serial to XIAO USB (e.g. screen /dev/ttyACM0 115200)"
