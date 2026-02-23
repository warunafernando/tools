#!/bin/bash
# Run BLE OTA 5 times - use from a normal terminal (not sandboxed) for reliable BlueZ access
# Usage: ./ota_ble_5x.sh [BLE_ADDR]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/../ncs-workspace/build"
VENV="${SCRIPT_DIR}/../.venv/bin/activate"
DBUS_ADDR="unix:path=/var/run/dbus/system_bus_socket"
export DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR"

source "$VENV"
smp() { env DBUS_SESSION_BUS_ADDRESS="$DBUS_ADDR" smpmgr "$@"; }

ADDR="${1:-}"
[ -z "$ADDR" ] && { echo "Usage: $0 <BLE_ADDR>"; echo "Example: $0 D0:8D:27:9F:56:14"; exit 1; }

IMAGE="${BUILD_DIR}/app/zephyr/zephyr.signed.bin"
[ ! -f "$IMAGE" ] && { echo "Build first: west build -b xiao_ble_sense nrf/app --sysbuild"; exit 1; }

echo "=== BLE OTA 5x: $ADDR ==="
for i in 1 2 3 4 5; do
  echo ""
  echo "--- OTA $i/5 ---"
  smp --ble "$ADDR" --timeout 30 image erase 1 2>/dev/null || true
  sleep 2
  if smp --ble "$ADDR" --timeout 90 upgrade --slot 1 "$IMAGE"; then
    echo "  OK"
  else
    echo "  FAIL at run $i"
    exit 1
  fi
  [ $i -lt 5 ] && { echo "  Waiting 35s for reboot..."; sleep 35; }
done
echo ""
echo "=== All 5 OTA runs completed ==="
