#!/bin/bash
# OTA stress: upgrade/downgrade 100 times between v1 and v2
# Delegates to Python driver (handles BlueZ retries)
# Usage: ./ota_stress_100.sh <BLE_ADDR> [CYCLES]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/../.venv/bin/python3"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/var/run/dbus/system_bus_socket"

exec "$VENV_PYTHON" "${SCRIPT_DIR}/ota_stress_100.py" "$@"
