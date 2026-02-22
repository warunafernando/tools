#!/bin/bash
# Enable Bluetooth for OTA scan. Run with: sudo ./enable_bluetooth.sh
# For passwordless use: add to sudoers: mini ALL=(ALL) NOPASSWD: /home/mini/tools/msr1_ota/web_gui/enable_bluetooth.sh
set -e
rfkill unblock bluetooth 2>/dev/null || true
systemctl start bluetooth 2>/dev/null || true
sleep 1.5
hciconfig hci0 up 2>/dev/null || true
sleep 0.5
exit 0
