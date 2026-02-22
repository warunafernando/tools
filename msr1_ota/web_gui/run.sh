#!/bin/bash
# Start SmartBall OTA Web GUI
cd "$(dirname "$0")"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/var/run/dbus/system_bus_socket"
export PATH="$(cd ../.. && pwd)/.venv/bin:$PATH"
exec python3 app.py
