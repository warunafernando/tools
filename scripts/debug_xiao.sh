#!/bin/bash
# Debug XIAO via RPi Debug Probe - line-by-line GDB
# Prereqs: probe connected, XIAO powered, wiring SC->SWDCLK, SD->SWDIO, GND->GND
# Kills any stray OpenOCD/GDB first; closes debugger on exit (Ctrl+D or 'quit' in GDB).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/debugger_ctl.sh"

cd /home/mini/tools/ncs-workspace
export PATH="/home/mini/tools/.venv/bin:$PATH"
export ZEPHYR_TOOLCHAIN_VARIANT=gnuarmemb
export GNUARMEMB_TOOLCHAIN_PATH=/usr

ensure_debugger_free
trap cleanup_on_exit EXIT

echo "Building debug image (no optimizations)..."
west build -b xiao_ble_sense nrf/app -- -DEXTRA_CONF_FILE=prj_debug.conf

echo ""
echo "Flashing and starting GDB (use sudo if udev not set up)..."
echo "  Useful breakpoints: break main  break bt_enable  break bt_thread_fn  break z_arm_hard_fault"
echo "  Commands: continue  step  next  bt  info locals"
echo "  Quit GDB with 'quit' or Ctrl+D to close debugger and release probe."
echo ""
sudo west debug --runner openocd -- --gdb /usr/bin/gdb-multiarch
