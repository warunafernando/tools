#!/usr/bin/env python3
"""OTA stress test driver - uses subprocess like debug script that succeeded."""
import os
import subprocess
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(SCRIPT_DIR)
IMAGES = os.path.join(SCRIPT_DIR, "images")
SMPMGR = os.path.join(TOOLS_DIR, ".venv", "bin", "smpmgr")
DBUS_ENV = {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/var/run/dbus/system_bus_socket"}

def run_upgrade(addr: str, img_path: str, timeout: int = 120, max_retries: int = 3) -> bool:
    """Run smpmgr upgrade. Retry on 'No Bluetooth adapters found' (BlueZ race)."""
    env = {**os.environ, **DBUS_ENV}
    base = [SMPMGR, "--ble", addr, "--timeout", "90"]
    for attempt in range(max_retries):
        subprocess.run(base + ["image", "erase", "1"], env=env, capture_output=True, timeout=30, cwd=TOOLS_DIR)
        r = subprocess.run(
            base + ["upgrade", "--slot", "1", img_path],
            env=env, capture_output=True, text=True, timeout=timeout, cwd=TOOLS_DIR
        )
        if r.returncode == 0:
            return True
        err = (r.stderr or "") + (r.stdout or "")
        if ("No Bluetooth adapters found" in err or "device disconnected" in err
                or "failed to discover" in err or "SMPTransportDisconnected" in err
                or "NO_FREE_SLOT" in err):
            if attempt < max_retries - 1:
                wait = 15 * (attempt + 1)
                print(f"    Retry in {wait}s ...", flush=True)
                time.sleep(wait)
                continue
        sys.stderr.write((r.stderr or "")[-1500:] + "\n")
        return False
    return False

def main():
    addr = sys.argv[1] if len(sys.argv) > 1 else None
    cycles = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    if not addr:
        print("Usage: ota_stress_100.py <BLE_ADDR> [CYCLES]")
        sys.exit(1)

    img_v1 = os.path.join(IMAGES, "app_v1.bin")
    img_v2 = os.path.join(IMAGES, "app_v2.bin")
    if not os.path.isfile(img_v1) or not os.path.isfile(img_v2):
        print("Build images first: ./msr1_ota/build_ota_images.sh")
        sys.exit(1)

    log_dir = os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log = os.path.join(log_dir, f"stress_{time.strftime('%Y%m%d_%H%M%S')}.log")

    last = "v1"
    pass_cnt = fail_cnt = 0
    print(f"=== OTA stress: {cycles} cycles ===")
    print(f"BLE_ADDR={addr}")
    with open(log, "w") as f:
        f.write(f"Started {time.asctime()}\n")
        for i in range(1, cycles + 1):
            img = img_v2 if last == "v1" else img_v1
            next_ver = "v2" if last == "v1" else "v1"
            print(f"\n[{i}/{cycles}] Upgrading to {next_ver} ...", flush=True)
            f.write(f"[{i}/{cycles}] upgrade to {next_ver}\n")
            if run_upgrade(addr, img):
                pass_cnt += 1
                last = next_ver
                print("  OK")
                time.sleep(25)
            else:
                fail_cnt += 1
                print("  FAIL")
                f.write("FAIL\n")
                sys.exit(1)
    print(f"\n=== Complete: Pass={pass_cnt} Fail={fail_cnt} ===")

if __name__ == "__main__":
    main()
