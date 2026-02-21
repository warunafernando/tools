#!/bin/bash
# Build signed SmartBall image for BLE OTA
# Per BLE_OTA_upgrade.md §8
# Usage: ./build_signed.sh [build_dir]
# Prereq: NCS workspace, west, imgtool

set -e
BUILD_DIR="${1:-build}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
KEY_FILE="${KEY_FILE:-$APP_DIR/keys/smartball.pem}"

echo "Building SmartBall (xiao_ble) with MCUboot..."
cd "$APP_DIR"
west build -b xiao_ble -d "$BUILD_DIR" --sysbuild

# Sign with imgtool (from MCUboot)
if [ ! -f "$KEY_FILE" ]; then
  echo "No key at $KEY_FILE - generating..."
  mkdir -p "$(dirname "$KEY_FILE")"
  imgtool keygen -k "$KEY_FILE" -t rsa-2048
fi

# Find app image (exclude mcuboot)
BIN=""
for d in "$BUILD_DIR"/smartball_app "$BUILD_DIR"; do
  [ -f "$d/zephyr/zephyr.bin" ] && BIN="$d/zephyr/zephyr.bin" && break
  [ -f "$d/zephyr/zephyr.hex" ] && BIN="${d}/zephyr/zephyr.bin" && \
    arm-none-eabi-objcopy -I ihex -O binary "$d/zephyr/zephyr.hex" "$BIN" 2>/dev/null && break
done
[ -n "$BIN" ] && [ -f "$BIN" ] || { echo "App image not found"; exit 1; }

SIGNED_BIN="$(dirname "$BIN")/zephyr.signed.bin"
echo "Signing $BIN..."
imgtool sign -k "$KEY_FILE" --align 4 --version 1.0.0 --header-size 32 \
  "$BIN" "$SIGNED_BIN"

echo "Signed image: $SIGNED_BIN"
