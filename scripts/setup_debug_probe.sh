#!/bin/bash
# Setup environment for Raspberry Pi Debug Probe + XIAO nRF52840 Sense
set -e

echo "=== RPi Debug Probe Setup ==="

# Install OpenOCD
if ! command -v openocd &>/dev/null; then
  echo "Installing OpenOCD..."
  sudo apt update
  sudo apt install -y openocd
else
  echo "OpenOCD already installed: $(openocd --version 2>/dev/null | head -1)"
fi

# Check for cmsis-dap
if openocd -f interface/cmsis-dap.cfg -f target/nrf52.cfg -c "init; shutdown" 2>/dev/null; then
  echo "OpenOCD CMSIS-DAP + nRF52: OK (probe not connected - run with probe attached)"
else
  echo "Note: Run 'openocd -f interface/cmsis-dap.cfg -f target/nrf52.cfg' with probe attached to verify"
fi

# udev rules
RULES="/home/mini/tools/udev/99-rpi-debug-probe.rules"
if [ -f "$RULES" ]; then
  echo "Installing udev rules..."
  sudo cp "$RULES" /etc/udev/rules.d/
  sudo udevadm control --reload-rules
  sudo udevadm trigger
  sudo usermod -aG plugdev "$USER"
  echo "Added $USER to plugdev. Log out and back in for it to take effect."
else
  echo "udev rules not found at $RULES"
fi

echo ""
echo "Done. To flash: west flash --runner openocd"
echo "To debug: west debug --runner openocd"
