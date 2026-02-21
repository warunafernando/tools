#!/bin/bash
# BLE OTA stress test - N runs, log capture, summary
# Per BLE_OTA_upgrade.md §9.2
# Usage: ./ota_stress.sh <signed.bin> [N]
# Prereq: ota_ble_mcumgr.sh, mcumgr

set -e
BIN="${1:?Usage: $0 <signed.bin> [N]}"
N="${2:-10}"
LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR"
CSV="$LOG_DIR/stress_$(date +%Y%m%d_%H%M%S).csv"

echo "run,result,elapsed_sec" > "$CSV"
PASS=0
FAIL=0

for i in $(seq 1 "$N"); do
  START=$(date +%s)
  if ./ota_ble_mcumgr.sh "$BIN" >> "$LOG_DIR/run_${i}.log" 2>&1; then
    RESULT="PASS"
    ((PASS++)) || true
  else
    RESULT="FAIL"
    ((FAIL++)) || true
  fi
  ELAPSED=$(($(date +%s) - START))
  echo "$i,$RESULT,$ELAPSED" >> "$CSV"
  echo "Run $i/$N: $RESULT (${ELAPSED}s)"
  sleep 5  # Allow device to stabilize between runs
done

echo ""
echo "Summary: $PASS pass, $FAIL fail (total $N)"
echo "CSV: $CSV"
