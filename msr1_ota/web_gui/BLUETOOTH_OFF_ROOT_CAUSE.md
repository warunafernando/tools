# Why Bluetooth Keeps Turning Off – Root Cause

## Summary

**Bluetooth is not being turned off by our OTA scripts.** The `bluetoothd` daemon (BlueZ) is **crashing with a segmentation fault (SEGV)**.

## Evidence

```
bluetooth.service: Main process exited, code=killed, status=11/SEGV
bluetooth.service: Failed with result 'signal'.
```

From `journalctl -u bluetooth.service`:
- bluetoothd starts and registers audio endpoints (A2DP, aptx, sbc, ldac)
- ~15–20 seconds later it crashes with SEGV
- Happens repeatedly (e.g. 02:33:52, 02:34:25, 02:51:23)

## What Our Scripts Do

| Action                 | Effect                            | Turns BT off? |
|------------------------|-----------------------------------|---------------|
| `bluetoothctl scan off`| Stops discovery only              | No            |
| `bluetoothctl scan on` | Starts discovery                  | No            |
| `rfkill unblock`       | Unblocks if soft-blocked          | No            |
| `systemctl start bluetooth` | Starts bluetoothd            | No            |
| `hciconfig hci0 up`    | Brings hci0 up                    | No            |

**None of our code powers off Bluetooth.**

## Likely Cause

BlueZ 5.66 `bluetoothd` is crashing, likely due to:

1. Bug in audio profile code (VCP, MCP, BAP plugins log “D-Bus experimental not enabled”)
2. Interaction with `bluetooth-autoconnect` or other D-Bus clients
3. Kernel/driver or hardware issue (dmesg shows “ACL packet for unknown connection handle 3837”)

## Workarounds

### 1. Restart Bluetooth Before Scan

Our web GUI calls `enable_bluetooth.sh`, which runs `systemctl start bluetooth`. That restarts the daemon. After ~15–20 seconds it may crash again, so run the scan soon after.

### 2. Auto-restart on Crash

Create an override so Bluetooth restarts when it crashes:

```bash
sudo mkdir -p /etc/systemd/system/bluetooth.service.d
sudo tee /etc/systemd/system/bluetooth.service.d/restart.conf << 'EOF'
[Service]
Restart=on-failure
RestartSec=5
EOF
sudo systemctl daemon-reload
```

### 3. Try Minimal BlueZ Config

Disable experimental plugins to see if the crash stops:

```bash
sudo mkdir -p /etc/bluetooth
echo -e "[General]\nEnable=Source,Sink,Media,Socket" | sudo tee -a /etc/bluetooth/main.conf
```

### 4. Update BlueZ

If possible, update to a newer BlueZ version in case the crash is fixed upstream.

## Quick Check Commands

```bash
# Status
systemctl status bluetooth

# Restart
sudo systemctl start bluetooth

# Recent logs
journalctl -u bluetooth -n 30
```
