#!/bin/bash
# Flash XIAO nRF52840 Sense via UF2 bootloader
# 1. Double-tap RST on the XIAO to enter bootloader
# 2. Run this script - it waits for the drive and copies
# 3. Do NOT unplug or double-tap again until copy completes

UF2="/home/mini/tools/ncs-workspace/build/zephyr/zephyr.uf2"
[ ! -f "$UF2" ] && { echo "Missing $UF2 - run build first"; exit 1; }

echo "=== XIAO UF2 Flash ==="
echo "1. Double-tap RST on the XIAO (two quick presses)"
echo "2. Wait for drive to appear (XIAO-SENSE or XIAO-BLE)"
echo ""

# Poll for mount
for i in $(seq 1 30); do
  # Check block devices that look like XIAO (often sda when only USB storage)
  for dev in /dev/sd[a-z]1 /dev/sd[a-z]; do
    [ -b "$dev" ] || continue
    MOUNT=$(findmnt -n -o TARGET "$dev" 2>/dev/null | head -1)
    [ -n "$MOUNT" ] && [ -d "$MOUNT" ] && [ -w "$MOUNT" ] && break 2
  done
  # Fallback: check common media dirs
  for m in /media/mini/* /media/"$USER"/* /run/media/mini/* /run/media/"$USER"/*; do
    [ -d "$m" ] && [ -w "$m" ] && MOUNT="$m" && break 2
  done
  [ -n "$MOUNT" ] && break
  echo "  Waiting for XIAO bootloader... ($i/30)"
  sleep 2
done

if [ -z "$MOUNT" ]; then
  echo "XIAO drive not found. Try:"
  echo "  - Double-tap RST again"
  echo "  - Check USB cable"
  echo "  - lsblk to see if sda appears"
  exit 1
fi

echo "Found: $MOUNT"
echo "Copying UF2 (do not unplug)..."
cp "$UF2" "$MOUNT/" && sync && echo "Done. XIAO will reboot."