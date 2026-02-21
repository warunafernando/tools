# SmartBall Image Signing

Per BLE_OTA_upgrade.md §8.

## Key management
- Keys stored in `firmware/keys/` (git-ignored)
- Default: `firmware/keys/smartball.pem` (RSA-2048)
- Generate: `imgtool keygen -k firmware/keys/smartball.pem -t rsa-2048`
- **Never commit private keys**

## MCUboot config
- `CONFIG_BOOT_SIGNATURE_TYPE_RSA=y` (or EC256)
- `CONFIG_BOOT_SIGNATURE_KEY_FILE="path/to/key.pem"`
- Set in `child_image/mcuboot.conf`

## Build steps
```bash
# Build with sysbuild (MCUboot + app)
west build -b xiao_ble -d build --sysbuild firmware/smartball_app

# Sign (if not done in build)
imgtool sign -k firmware/keys/smartball.pem --align 4 --version 1.0.0 \
  build/smartball_app/zephyr/zephyr.bin build/zephyr.signed.bin
```

## Verification
- MCUboot rejects unsigned images
- Only images signed with the configured key are accepted
