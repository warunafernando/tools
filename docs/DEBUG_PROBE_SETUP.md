# Raspberry Pi Debug Probe + XIAO nRF52840 Sense

Setup for debugging the XIAO nRF52840 Sense via SWD using the official Raspberry Pi Debug Probe.

## Hardware Wiring

| RPi Debug Probe | XIAO nRF52840 Sense |
|-----------------|---------------------|
| **SC** (Orange) | **SWDCLK** |
| **SD** (Yellow) | **SWDIO** |
| **GND**        | **GND** |

- **Power**: Do NOT power the XIAO via the probe. Power the XIAO separately (USB or external).
- **SWD pins**: Use a Seeed XIAO Expansion Board to access SWD pads, or connect directly to the pads on the back.
- **Probe voltage**: 1.8V-3.3V only. nRF52840 is 3.3V.

## Software Setup

Run the setup script, or follow steps manually:

```bash
/home/mini/tools/scripts/setup_debug_probe.sh
```

### 1. Install OpenOCD
```bash
sudo apt install -y openocd
```

### 2. udev Rules (no sudo for flashing)
```bash
sudo cp /home/mini/tools/udev/99-rpi-debug-probe.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo usermod -aG plugdev $USER
# Log out and back in
```

### 3. Build & Flash
```bash
cd /home/mini/tools/ncs-workspace
west build -b xiao_ble_sense nrf/app
west flash --runner openocd
```

### 4. GDB Debug
```bash
west debug --runner openocd
```

### 5. Mass Erase
```bash
west flash --runner openocd -- --cmd-pre-load "reset halt; nrf5 mass_erase"
```
