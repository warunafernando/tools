#!/bin/bash
# Stop bluetooth-autoconnect, any BLE scan, and restart bluetoothd so smpmgr/Bleak can connect.
# Restarting bluetooth clears org.bluez.Error.InProgress. Run: sudo ./stop_ble_for_mcumgr.sh
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=/var/run/dbus/system_bus_socket}"
systemctl stop bluetooth-autoconnect 2>/dev/null || true
bluetoothctl scan off 2>/dev/null || true
# Restart bluetoothd to fully clear BlueZ state (fixes InProgress)
systemctl restart bluetooth 2>/dev/null || true
sleep 8
exit 0
