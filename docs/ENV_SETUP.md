# SmartBall BLE OTA — Environment Setup

Per BLE_OTA_upgrade.md. Target: MS-R1 (Linux) + Seeed XIAO nRF52840 Sense.

## 1. NCS (Nordic Connect SDK) Setup

### Prerequisites
```bash
# Python 3.8+, pip, venv
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Build deps
sudo apt install -y git cmake ninja-build gperf ccache dfu-util \
  device-tree-compiler wget libssl-dev libncurses5
```

### Install NCS
```bash
# Create workspace
mkdir -p ~/ncs-workspace && cd ~/ncs-workspace

# Bootstrap west
pip install west
west init -m https://github.com/nrfconnect/sdk-nrf --mr v2.6.0
cd nrf
west update

# Install Python deps
pip install -r zephyr/scripts/requirements.txt
pip install -r nrf/scripts/requirements.txt
pip install -r bootloader/mcuboot/scripts/requirements.txt
```

### Add SmartBall app
```bash
# Copy or symlink smartball_app into NCS workspace
cp -r /path/to/tools/firmware/smartball_app ~/ncs-workspace/nrf/app/

# Build with sysbuild (MCUboot + app)
cd ~/ncs-workspace/nrf
west build -b xiao_ble app/smartball_app --sysbuild

# Sign (see docs/SIGNING.md)
imgtool sign -k app/smartball_app/keys/smartball.pem ...

# Flash
west flash
```

## 2. MS-R1 Linux (Host) Prerequisites

```bash
# BlueZ
sudo apt install -y bluez bluetooth
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# mcumgr (for SMP OTA - step 3+)
go install github.com/apache/mynewt-mcumgr-cli/mcumgr@latest
# Or: download from https://github.com/apache/mynewt-mcumgr-cli/releases
export PATH=$PATH:$(go env GOPATH)/bin

# Debugging
sudo apt install -y bluetoothctl
```

## 3. Verify BLE Adapter
```bash
bluetoothctl
power on
scan on
# Should see "SmartBall" when device is running
```

## 4. Board Notes
- **Board ID**: `xiao_ble` (Seeed XIAO nRF52840 Sense)
- **Flash**: UF2 bootloader (double-tap RST) or nRF Connect / J-Link
- **USB**: For development; sealed device has BLE-only upgrade path
