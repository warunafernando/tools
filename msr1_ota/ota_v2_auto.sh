#!/bin/bash
# BLE OTA v2 image — scan for SmartBall, then upgrade
# Run from a normal terminal (not sandboxed) so Bluetooth/D-Bus works.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OTA_SCRIPT="${SCRIPT_DIR}/ota_ble_mcumgr.sh"
V2_IMAGE="${SCRIPT_DIR}/images/app_v2.bin"

# Bleak needs system D-Bus
export DBUS_SESSION_BUS_ADDRESS="unix:path=/var/run/dbus/system_bus_socket"

if [ ! -f "$V2_IMAGE" ]; then
  echo "v2 image not found. Build first: ./msr1_ota/build_ota_images.sh"
  exit 1
fi

if [ -z "${1:-}" ]; then
  echo "Scanning for SmartBall (10s)..."
  bluetoothctl scan on &
  sleep 10
  bluetoothctl scan off 2>/dev/null || true
  echo ""
  echo "Devices:"
  bluetoothctl devices
  echo ""
  echo "Usage: $0 <BLE_ADDR>"
  echo "Example: $0 F9:C6:99:8C:38:30"
  echo "Use the address of the SmartBall device above."
  exit 1
fi
ADDR="$1"

echo "Upgrading to v2 (red LED) via BLE OTA..."
"$OTA_SCRIPT" "$ADDR" "$V2_IMAGE"
