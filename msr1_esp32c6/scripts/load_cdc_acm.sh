#!/bin/bash
# Load CDC-ACM driver so XIAO ESP32-C6 (Espressif USB JTAG/serial) appears as /dev/ttyACM0.
# Run once: sudo ./scripts/load_cdc_acm.sh
# Then unplug and replug the board if it was already connected.
set -e
if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo $0"
    exit 1
fi
modprobe cdc_acm
echo "cdc_acm loaded. If the board was already connected, unplug and replug it."
ls -la /dev/ttyACM* /dev/ttyUSB* 2>/dev/null || echo "No tty yet - replug the XIAO ESP32-C6."
