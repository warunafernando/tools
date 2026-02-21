"""Post-build: convert firmware.elf to firmware.bin for OTA"""
Import("env")

env.AddPostAction(
    "$BUILD_DIR/firmware.elf",
    env.VerboseAction(
        '"$OBJCOPY" -O binary "$BUILD_DIR/firmware.elf" "$BUILD_DIR/firmware.bin"',
        "Building firmware.bin"))
