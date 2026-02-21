# SmartBall NCS App

Zephyr/NCS application for Seeed XIAO nRF52840 Sense.

Board: `xiao_ble`

## Build (from NCS workspace)

```bash
# From nrf workspace root (after west init + update)
west build -b xiao_ble firmware/smartball_app
# Or if copied to app/: west build -b xiao_ble app/smartball_app
```

## Flash

```bash
west flash
# Or for UF2: double-tap RST on XIAO, then west flash -r uf2
```

## Step 1 (current)
- BLE advertises as "SmartBall"
- Connectable, minimal GATT

## Planned (BLE_OTA_upgrade.md)
- MCUboot A/B + rollback
- mcumgr SMP over BLE
- Health-gated confirm
- DFU-safe mode
