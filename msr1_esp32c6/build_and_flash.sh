#!/bin/bash
# Build and flash SmartBall ESP32-C6. Requires ESP-IDF (see README.md).
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

for idf in "$HOME/esp/esp-idf/export.sh" "/opt/esp/idf/export.sh" "$IDF_PATH/export.sh"; do
    if [ -f "$idf" ]; then
        echo "Sourcing $idf"
        . "$idf"
        break
    fi
done
if ! type idf.py >/dev/null 2>&1; then
    echo "ESP-IDF not found. Install it and run: . \$IDF_PATH/export.sh"
    echo "Then: idf.py set-target esp32c6 && idf.py build && idf.py -p /dev/ttyACM0 flash"
    exit 1
fi

if [ ! -f "build/flash.bin" ] && [ ! -f "build/smartball_esp32c6.elf" ]; then
    idf.py set-target esp32c6
fi
idf.py build

# Auto-detect ESP32 serial port (XIAO ESP32-C6 uses CDC-ACM → ttyACM*)
detect_port() {
    [ -c /dev/ttyACM0 ] && echo /dev/ttyACM0 && return
    [ -c /dev/ttyUSB0 ] && echo /dev/ttyUSB0 && return
    for p in /dev/ttyACM* /dev/ttyUSB*; do
        [ -c "$p" ] && echo "$p" && return
    done
    echo ""
}
PORT="${1}"
if [ -z "$PORT" ]; then
    PORT=$(detect_port)
    if [ -z "$PORT" ]; then
        echo "No serial port found. XIAO ESP32-C6 needs the CDC-ACM driver."
        echo "Run once: sudo modprobe cdc_acm"
        echo "Then unplug and replug the board, and run this script again."
        exit 1
    fi
fi
echo "Flashing to $PORT (override: $0 /dev/ttyACM0)"
idf.py -p "$PORT" flash
