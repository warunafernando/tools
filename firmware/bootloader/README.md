# SmartBall OTA Bootloader

For full A/B dual-slot OTA with rollback, a bootloader is required.

## Flow

1. App receives OTA to Slot B (0x80000), verifies CRC, writes pending flag
2. App reboots
3. **Bootloader** reads flag, swaps Slot B → Slot A (or boots from B)
4. Bootloader jumps to app
5. App calls `ota_confirm()` to prevent rollback
6. If app crashes before confirm, next reboot → bootloader rolls back

## Option A: MCUboot (recommended)

Use nRF Connect SDK with MCUboot for production:

- Configure primary/secondary slots
- Enable swap mode with rollback
- Build app with MCUboot as library

## Option B: Custom stub

A minimal bootloader (~4KB) at 0x26000 can:

- Read OTA flag at 0xFE000
- If pending: copy 0x80000 → 0x27000 (slot B → slot A)
- Clear flag, jump to 0x27000
- App linked to run at 0x27000

## Current state

Without a bootloader, OTA **receives and verifies** the image to Slot B but does not apply it on reboot. The pending flag and confirm logic are in place for when a bootloader is added.
