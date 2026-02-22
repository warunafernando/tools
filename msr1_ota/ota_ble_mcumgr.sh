#!/bin/bash
# BLE OTA via mcumgr SMP — SmartBall
# Usage: ./ota_ble_mcumgr.sh [BLE_ADDR]
#   If BLE_ADDR omitted, scans for "SmartBall" (requires device in range).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/../ncs-workspace/build"
VENV="${SCRIPT_DIR}/../.venv/bin/activate"

# Bleak needs system D-Bus to see BlueZ adapter (avoids "No Bluetooth adapters found")
DBUS_ADDR="unix:path=/var/run/dbus/system_bus_socket"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

source "$VENV"

# Ensure smpmgr runs with system D-Bus (sandbox/CI may not inherit export)
smp() { env DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" smpmgr "$@"; }

# SMP transport: --ble <addr>
# smpmgr needs BLE address. Get via: bluetoothctl scan on; bluetoothctl devices
# Default: upgrade only (avoids BlueZ adapter race when running state-read then upgrade)
SKIP_CHECK=true
if [ "${1:-}" = "--with-check" ]; then
  SKIP_CHECK=false
  shift
fi
ADDR="${1:-}"

if [ -z "$ADDR" ]; then
  echo "Usage: $0 [--with-check] <BLE_ADDR> [IMAGE]"
  echo "Example: $0 AA:BB:CC:DD:EE:FF"
  echo "  --with-check  run image state-read first (adds ~10s delay between check and upgrade)"
  echo ""
  echo "To find SmartBall: bluetoothctl scan on  (wait 5s)  bluetoothctl devices"
  exit 1
fi

IMAGE="${2:-}"
if [ -z "$IMAGE" ]; then
  # Sysbuild: app_update.bin is the signed OTA image for mcumgr
  IMAGE="$BUILD_DIR/app/zephyr/zephyr.signed.bin"
fi
if [ ! -f "$IMAGE" ]; then
  echo "No signed image found. Build first:"
  echo "  cd ncs-workspace && west build -b xiao_ble_sense nrf/app"
  exit 1
fi

if [ "$SKIP_CHECK" = false ]; then
  echo "=== SMP image state-read (verify SMP reachable) ==="
  smp --ble "$ADDR" --timeout 20 image state-read
  echo ""
  echo "=== Upload + test + reset ==="
  # BlueZ needs time to fully release adapter after first smpmgr disconnect
  sleep 8
else
  echo "=== Upload + test + reset (skipping state-read) ==="
fi
# Erase slot 1 first to avoid NO_FREE_SLOT when both slots have images
smp --ble "$ADDR" --timeout 30 image erase 1 2>/dev/null || true
smp --ble "$ADDR" --timeout 60 upgrade --slot 1 "$IMAGE"
