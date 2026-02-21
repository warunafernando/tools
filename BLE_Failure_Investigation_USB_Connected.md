# BLE Failure Investigation – SmartBall with USB Connected

## Summary

When SmartBall is connected via USB (for power/serial testing), **BLE scan does not find the device** ("SmartBall not found"). This document explains why and how to fix it.

---

## Root Cause: Low-Frequency Clock (LFCLK) Conflict

### Problem

On the XIAO nRF52840 Sense (Seeed Studio), BLE advertising can **fail when USB is connected** due to the default low-frequency clock configuration.

- **Default:** PlatformIO/nRF52 uses the **32 kHz crystal oscillator (LFXO)** for the SoftDevice clock.
- **Behavior:** When USB is active, the crystal oscillator configuration can conflict with USB timing or power states, causing:
  - BLE stack to not start or hang during init
  - Advertising to never begin
  - Device invisible to BLE scans

### Evidence

1. **Nordic DevZone** ([#103064](https://devzone.nordicsemi.com/f/nordic-q-a/103064/xiao-nrf52840-ble---usb-and-ble-issues)):
   - "Please try changing the low-frequency clock source from the default 32 kHz crystal oscillator to the **internal 32 kHz RC oscillator**."
   - Some XIAO nRF52840 boards may not have the crystal properly supported when USB is in use.

2. **PlatformIO issue** ([platform-nordicnrf52 #189](https://github.com/platformio/platform-nordicnrf52/issues/189)):
   - Boards without proper 32 kHz crystal support need `-DUSE_LFSYNT` build flag.
   - "The delay() function uses millis() which uses the counter driven by RTC1" – RTC1 depends on LFCLK.
   - Adding `build_flags = -DUSE_LFSYNT` switches to internal RC oscillator.

3. **Stress test results:**
   - 99/100 OTA runs succeeded via **Serial** (USB connected).
   - 0/100 succeeded via **BLE** (same setup: device on USB).
   - BLE throughput/scan tests: "SmartBall not found" – device does not appear in scans when on USB.

---

## Fix: Use Internal RC Oscillator

Add the build flag to use the internal 32 kHz RC oscillator instead of the crystal:

```ini
build_flags =
    -DUSE_LFSYNT
    # ... other flags
```

### Effects

- **Pros:** BLE should advertise and work when USB is connected.
- **Cons:** Internal RC is less accurate than crystal (~500 ppm vs ~50 ppm). Nordic recommends `NRF_SDH_CLOCK_LF_ACCURACY = 500 PPM` for reliable BLE with RC. The SoftDevice handles calibration; this is acceptable for most use cases.

---

## Other Possible Factors (Secondary)

1. **Windows BLE stack:** Windows 11 BLE stack can be finicky; retries and longer scan time help.
2. **Serial Monitor holding port:** If another app (Serial Monitor, Arduino IDE, PlatformIO Monitor) has the COM port open, Serial OTA fails. BLE discovery is independent of Serial, but both use the same USB connection for power.
3. **Scan timing:** First scan after boot can miss the device; multiple 15 s scans with retries improve discovery.

---

## How to Test

1. **Add `USE_LFSYNT`** to `platformio.ini` for the `ota_ble` (and related) environments.
2. **Flash new firmware** via Serial OTA (device on USB):
   ```bash
   python tools/ota_serial.py COM16 tools/fw_v1.bin 1
   ```
3. **Run BLE scan** (device still on USB):
   ```bash
   python tools/ble_find.py --timeout 15
   ```
4. **Run throughput test:**
   ```bash
   python tools/throughput_test.py --ble --duration 3
   ```

If SmartBall appears in scans and BLE OTA/throughput work with USB connected, the LFCLK fix is confirmed.

---

## References

- [Nordic DevZone: XIAO nRF52840 BLE and USB Issues](https://devzone.nordicsemi.com/f/nordic-q-a/103064/xiao-nrf52840-ble---usb-and-ble-issues)
- [PlatformIO: Default LFCLK Build Flag (USE_LFSYNT)](https://github.com/platformio/platform-nordicnrf52/issues/189)
- [Nordic: Internal RC oscillator configuration](https://devzone.nordicsemi.com/f/nordic-q-a/59380/how-to-enable-the-internal-32-768-khz-rc-oscillator)
