#!/usr/bin/env python3
"""
OTA stress test: run OTA 100 times alternating A/B images. Uses ota_auto (BLE first, Serial fallback).
Logs: run, success/fail, upgrade time (s), BLE or Serial method.
Usage: python ota_ble_stress_test.py [--runs 100] [--reboot-wait 10] [--serial-port COM16]
"""
import sys
import time
import subprocess
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
FW_V1 = SCRIPT_DIR / "fw_v1.bin"
FW_V2 = SCRIPT_DIR / "fw_v2.bin"
DEFAULT_RUNS = 100
REBOOT_WAIT = 10.0
LOG_FILE = SCRIPT_DIR / "ota_stress_log.txt"


def log(msg, file_handle):
    print(msg)
    if file_handle:
        file_handle.write(msg + "\n")
        file_handle.flush()


def run_single_ota(fw_path, version, serial_port=None):
    """Run ota_auto; returns (ok, elapsed, method) where method is 'BLE' or 'Serial'."""
    cmd = [sys.executable, str(SCRIPT_DIR / "ota_auto.py"), str(fw_path), str(version)]
    if serial_port:
        cmd.extend(["--serial-port", serial_port])
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(SCRIPT_DIR), capture_output=True, text=True, timeout=600)
    elapsed = time.perf_counter() - t0
    out = (proc.stdout or "") + (proc.stderr or "")
    method = "Serial" if ("Serial OTA" in out or "Falling back" in out) else "BLE"
    return proc.returncode == 0, elapsed, method


def main():
    ap = argparse.ArgumentParser(description="OTA stress test (BLE first, Serial fallback)")
    ap.add_argument("--runs", type=int, default=DEFAULT_RUNS, help="Number of OTA runs")
    ap.add_argument("--reboot-wait", type=float, default=REBOOT_WAIT, help="Seconds to wait after OTA before next run")
    ap.add_argument("--serial-port", default=None, help="COM port for Serial fallback (e.g. COM16)")
    ap.add_argument("--log", action="store_true", default=True)
    ap.add_argument("--no-log", action="store_false", dest="log")
    args = ap.parse_args()

    log_handle = open(LOG_FILE, "w", encoding="utf-8") if args.log else None
    failed = []
    try:
        if not FW_V1.exists() or not FW_V2.exists():
            log(f"Missing firmware: {FW_V1.name} / {FW_V2.name}", log_handle)
            sys.exit(1)

        log("OTA Stress Test: BLE first, Serial fallback.", log_handle)
        runs_config = [(FW_V1, 1), (FW_V2, 2)]
        results = []
        total_start = time.perf_counter()

        for run in range(args.runs):
            fw_path, version = runs_config[run % 2]
            t0 = time.perf_counter()
            try:
                ok, elapsed, method = run_single_ota(fw_path, version, args.serial_port)
            except Exception as e:
                ok = False
                elapsed = time.perf_counter() - t0
                method = "?"
                log(f"  Run {run + 1} exception: {e}", log_handle)
            results.append((run + 1, ok, elapsed, method))
            status = "OK" if ok else "FAIL"
            log(f"Run {run + 1}/{args.runs} [v{version}] {method} {status}  {elapsed:.1f}s", log_handle)
            if run < args.runs - 1:
                if ok:
                    time.sleep(args.reboot_wait)
                else:
                    time.sleep(2.0)

        total_elapsed = time.perf_counter() - total_start
        success = [r for r in results if r[1]]
        failed = [r for r in results if not r[1]]
        times = [r[2] for r in success]
        ble_ok = len([r for r in success if len(r) > 3 and r[3] == "BLE"])
        serial_ok = len([r for r in success if len(r) > 3 and r[3] == "Serial"])

        report_lines = [
            "", "=" * 60, "OTA STRESS TEST REPORT", "=" * 60,
            f"Total runs:     {args.runs}", f"Success:        {len(success)}", f"Failure:        {len(failed)}",
            f"BLE success:    {ble_ok}", f"Serial success: {serial_ok}",
            (f"Failed runs:    {[r[0] for r in failed]}" if failed else ""),
            (f"Upgrade time (successful): min={min(times):.1f}s  avg={sum(times)/len(times):.1f}s  max={max(times):.1f}s" if times else ""),
            f"Total time:     {total_elapsed:.1f}s", "=" * 60,
        ]
        for line in report_lines:
            if line:
                log(line, log_handle)
    finally:
        if log_handle:
            log_handle.close()
    sys.exit(0 if len(failed) == 0 else 1)


if __name__ == "__main__":
    main()
