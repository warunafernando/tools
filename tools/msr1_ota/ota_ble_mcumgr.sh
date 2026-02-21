#!/bin/bash
# SmartBall OTA via mcumgr SMP over BLE
# Per BLE_OTA_upgrade.md §9.1
# Usage: ./ota_ble_mcumgr.sh <signed.bin> [device_name] [--confirm]
# Prereq: mcumgr, BlueZ, device running NCS app with SMP

set -e
BIN="${1:?Usage: $0 <signed.bin> [device_name] [--confirm]}"
DEVICE_NAME="SmartBall"
DO_CONFIRM=false
shift
while [ $# -gt 0 ]; do
  case "$1" in
    --confirm) DO_CONFIRM=true ;;
    *)         DEVICE_NAME="$1" ;;
  esac
  shift
done

LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/ota_$(date +%Y%m%d_%H%M%S).log"

CONN="--conntype ble --connstring peer_name=$DEVICE_NAME"

log() { echo "[$(date -Iseconds)] $*"; }
run() { mcumgr $CONN "$@" || return $?; }

exec > >(tee -a "$LOG") 2>&1
log "OTA start: $BIN device=$DEVICE_NAME"

# Retry helper
retry_cmd() {
  local tries=3 delay=2
  while [ $tries -gt 0 ]; do
    if mcumgr $CONN "$@"; then return 0; fi
    tries=$((tries-1))
    [ $tries -gt 0 ] && { log "Retry in ${delay}s..."; sleep $delay; }
  done
  return 1
}

# 1-2: Connect + upload
log "Uploading image..."
retry_cmd image upload "$BIN" || { log "Upload failed"; exit 1; }

# 3-4: image list, capture hash
HASH=$(mcumgr $CONN image list 2>/dev/null | grep -oP 'hash=\K[0-9a-f]+' | head -1)
[ -z "$HASH" ] && HASH=$(mcumgr $CONN image list 2>/dev/null | grep -oE '[0-9a-f]{32}' | head -1)
log "Image hash: $HASH"

# 5: image test
log "Testing image..."
retry_cmd image test "$HASH" || { log "image test failed"; exit 1; }

# 6: reset
log "Resetting device..."
retry_cmd reset

# 7-8: Wait for reboot, then confirm if requested
log "Waiting 15s for device reboot..."
sleep 15

if $DO_CONFIRM; then
  log "Confirming image..."
  retry_cmd image confirm "$HASH" || log "Confirm failed (device may confirm itself)"
fi

log "OTA complete."
mcumgr $CONN image list 2>/dev/null || true
