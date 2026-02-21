# SmartBall Flash Budget

Per BLE_OTA_upgrade.md §4.

## nRF52840 Layout (1MB internal flash)

| Region | Address | Size | Notes |
|--------|---------|------|-------|
| Bootloader (MCUboot) | 0x00000000 | ~48KB | Swap mode |
| Slot 0 (Primary) | 0x00010000 | ~432KB | Active image |
| Slot 1 (Secondary) | 0x0007C000 | ~432KB | OTA staging |
| Settings/NVS | 0x000FF000 | ~4KB | MCUboot state |

*Exact values TBD after MCUboot + sysbuild.*

## Current (Step 1 baseline)
- App only, no bootloader
- Size TBD after first NCS build

## Decision rule
- Image must fit in half of slot allocation with margin
- If too large: reduce features, move assets, or recovery-minimal image
