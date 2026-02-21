#!/usr/bin/env python3
"""
Debug why second smpmgr upgrade fails with "No Bluetooth adapters found".
Probes BlueZ/D-Bus adapter state before and after first upgrade.
"""
import asyncio
import os
import sys

# Ensure we use system D-Bus like smpmgr
os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", "unix:path=/var/run/dbus/system_bus_socket")

def check_bluez_adapters():
    """Check if Bleak can see BlueZ adapters (same path as smpmgr)."""
    try:
        from bleak.backends.bluezdbus.manager import get_global_bluez_manager
        async def probe():
            mgr = await get_global_bluez_manager()
            adapters = getattr(mgr, "_adapters", set())
            try:
                default = mgr.get_default_adapter()
                return True, list(adapters), default
            except Exception as e:
                return False, list(adapters), str(e)
        return asyncio.run(probe())
    except Exception as e:
        return None, [], str(e)

def main():
    addr = sys.argv[1] if len(sys.argv) > 1 else "F9:C6:99:8C:38:30"
    img = sys.argv[2] if len(sys.argv) > 2 else "images/app_v2.bin"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    img_path = os.path.join(script_dir, img)
    if not os.path.isfile(img_path):
        print(f"Image not found: {img_path}")
        sys.exit(1)

    print("=== Before any smpmgr ===")
    ok, adapters, extra = check_bluez_adapters()
    print(f"  Adapters visible: {ok}, adapters={adapters}, extra={extra}")

    print("\n=== Running first upgrade ===")
    import subprocess
    r1 = subprocess.run(
        ["smpmgr", "--ble", addr, "--timeout", "90", "upgrade", img_path],
        env={**os.environ, "DBUS_SESSION_BUS_ADDRESS": "unix:path=/var/run/dbus/system_bus_socket"},
        capture_output=True, text=True, timeout=120
    )
    print(f"  Exit: {r1.returncode}")
    if r1.stderr:
        print(f"  stderr: {r1.stderr[:500]}")

    print("\n=== Immediately after first upgrade (same process) ===")
    ok, adapters, extra = check_bluez_adapters()
    print(f"  Adapters visible: {ok}, adapters={adapters}, extra={extra}")

    print("\n=== Sleep 15s (device reboot), then check from FRESH subprocess (like 2nd smpmgr) ===")
    import time
    time.sleep(15)

    # Check from a fresh Python subprocess - same as 2nd smpmgr
    check_script = """
import asyncio, os
os.environ["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=/var/run/dbus/system_bus_socket"
from bleak.backends.bluezdbus.manager import get_global_bluez_manager
async def p():
    m = await get_global_bluez_manager()
    a = getattr(m, "_adapters", set())
    try:
        d = m.get_default_adapter()
        print("OK", list(a), d)
    except Exception as e:
        print("FAIL", list(a), e)
asyncio.run(p())
"""
    r = subprocess.run(
        [sys.executable, "-c", check_script],
        env={**os.environ, "DBUS_SESSION_BUS_ADDRESS": "unix:path=/var/run/dbus/system_bus_socket"},
        capture_output=True, text=True, timeout=10, cwd=script_dir
    )
    print(f"  Fresh subprocess result: stdout={r.stdout!r} stderr={r.stderr!r}")

    print("\n=== Run second upgrade (this is where it fails) ===")
    r2 = subprocess.run(
        ["smpmgr", "--ble", addr, "--timeout", "90", "upgrade", os.path.join(script_dir, "images/app_v1.bin")],
        env={**os.environ, "DBUS_SESSION_BUS_ADDRESS": "unix:path=/var/run/dbus/system_bus_socket"},
        capture_output=True, text=True, timeout=120
    )
    print(f"  Exit: {r2.returncode}")
    if r2.stderr:
        print(f"  stderr: {r2.stderr[:800]}")

if __name__ == "__main__":
    main()
