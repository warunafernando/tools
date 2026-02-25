#!/usr/bin/env python3
"""Debug script to test Read Version BLE flow. Run from msr1_ota/web_gui."""
import os
import sys
from pathlib import Path

# Add parent to path so we can import app logic
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.chdir(Path(__file__).resolve().parent)

# Import after path is set
import subprocess
import time

TOOLS = Path(__file__).resolve().parents[2]
VENV = TOOLS / ".venv" / "bin"
DBUS = "unix:path=/var/run/dbus/system_bus_socket"


def env():
    e = os.environ.copy()
    e["DBUS_SESSION_BUS_ADDRESS"] = DBUS
    e["PATH"] = f"{VENV}:{e.get('PATH', '')}"
    return e


def run(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env())
    return r.returncode, r.stdout, r.stderr


def main():
    addr = sys.argv[1] if len(sys.argv) > 1 else "D0:8D:27:9F:56:14"
    print(f"Testing Read Version for {addr}")
    print("=" * 50)

    # 1. Check bluetooth-autoconnect
    code, out, err = run(["systemctl", "is-active", "bluetooth-autoconnect.service"])
    autoconnect = out.strip() == "active"
    print(f"1. bluetooth-autoconnect: {'active' if autoconnect else 'inactive'}")

    # 2. Full recovery: stop autoconnect, restart bluetooth (clears Notify acquired)
    print("2. Running full BLE release (stop_ble_for_mcumgr.sh)...")
    script = Path(__file__).resolve().parent / "stop_ble_for_mcumgr.sh"
    if script.is_file():
        subprocess.run(["sudo", "-n", str(script)], capture_output=True, timeout=25, env=env())
    time.sleep(5)  # Extra wait for adapter
    subprocess.run(["bluetoothctl", "disconnect", addr], capture_output=True, timeout=5, env=env())
    time.sleep(5)
    print("   Done.")

    # 3. Run smpclient read (same as _read_version_via_smp)
    print("3. Running smpclient image state-read...")
    try:
        from smpclient import SMPClient
        from smpclient.transport.ble import SMPBLETransport
        from smpclient.requests.image_management import ImageStatesRead
        from smpclient.generics import success
        import asyncio

        async def do_read():
            client = SMPClient(SMPBLETransport(), addr)
            await client.connect(25.0)
            r = await client.request(ImageStatesRead(), 25.0)
            await client.disconnect()
            return r

        r = asyncio.run(do_read())
        if success(r) and hasattr(r, "images"):
            for img in sorted(r.images, key=lambda x: x.slot):
                slot = "A" if img.slot == 0 else "B"
                ver = getattr(img, "version", "?")
                print(f"   Slot {slot}: v{ver}")
            print("   SUCCESS")
        else:
            print(f"   FAIL: {r}")
    except Exception as e:
        print(f"   FAIL: {e}")

    # 4. Restart bluetooth-autoconnect
    print("4. Restarting bluetooth-autoconnect...")
    subprocess.run(
        ["sudo", "-n", "systemctl", "start", "bluetooth-autoconnect.service"],
        capture_output=True, timeout=5, env=env()
    )
    print("Done.")


if __name__ == "__main__":
    main()
