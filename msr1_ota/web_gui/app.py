#!/usr/bin/env python3
"""
SmartBall OTA Web GUI — Scan, upgrade (Serial/BLE/Debugger), read version, activate
"""
import os
import sys
import subprocess
import glob
import json
import time
import asyncio
from io import StringIO
from pathlib import Path
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
TOOLS_DIR = Path(__file__).resolve().parents[2]
VENV = TOOLS_DIR / ".venv" / "bin"
SMPMGR = VENV / "smpmgr"
IMAGES_DIR = Path(__file__).resolve().parent.parent / "images"
WS = TOOLS_DIR / "ncs-workspace"
DBUS = "unix:path=/var/run/dbus/system_bus_socket"

BT_OFF_MSG = (
    "Bluetooth adapter is off. Run: sudo ./enable_bluetooth.sh\n"
    "Or for auto-enable on scan: sudo cp sudoers_ble /etc/sudoers.d/ota-ble && sudo chmod 440 /etc/sudoers.d/ota-ble"
)
BT_OFF_HINTS = ("network is down", "no default controller", "org.bluez", "connection refused", "invalid device")

# Server-side BLE connection: after scan+connect, address is stored for Read/Upgrade/Activate
_connected_ble_addr = None


def _stop_ble_scan():
    """Stop bluetooth-autoconnect and any BLE scan so smpmgr/Bleak can start its own.
    Fixes org.bluez.Error.InProgress (Operation already in progress)."""
    import time
    script = Path(__file__).resolve().parent / "stop_ble_for_mcumgr.sh"
    try:
        if script.is_file():
            subprocess.run(["sudo", "-n", str(script)], capture_output=True, timeout=20, env=_env())
        else:
            subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True, timeout=3, env=_env())
            time.sleep(2)
    except Exception:
        pass


def _prepare_ble_gentle(addr):
    """Release BLE without restarting bluetoothd (avoids 'No Bluetooth adapters found').
    Stop autoconnect, disconnect device, scan off, wait."""
    try:
        subprocess.run(["sudo", "-n", "systemctl", "stop", "bluetooth-autoconnect.service"], capture_output=True, timeout=5, env=_env())
    except Exception:
        pass
    subprocess.run(["bluetoothctl", "scan", "off"], capture_output=True, timeout=3, env=_env())
    subprocess.run(["bluetoothctl", "disconnect", addr], capture_output=True, timeout=5, env=_env())
    time.sleep(4)


def _prepare_ble_before_smpmgr(addr):
    """After _stop_ble_scan: disconnect device and wait so smpmgr gets a clean connection."""
    subprocess.run(
        ["bluetoothctl", "disconnect", addr],
        capture_output=True,
        timeout=5,
        env=_env(),
    )
    time.sleep(3)


def _restart_ble_autoconnect():
    """Restart bluetooth-autoconnect after BLE mcumgr operations."""
    try:
        subprocess.run(["sudo", "-n", "systemctl", "start", "bluetooth-autoconnect.service"], capture_output=True, timeout=5)
    except Exception:
        pass


def _env():
    env = os.environ.copy()
    env["DBUS_SESSION_BUS_ADDRESS"] = DBUS
    env["PATH"] = f"{VENV}:{env.get('PATH', '')}"
    return env


def _run(cmd, timeout=90, cwd=None):
    r = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd or str(TOOLS_DIR),
        env=_env(),
    )
    return r.returncode, r.stdout, r.stderr


@app.route("/")
def index():
    return render_template("index.html")


def _is_bluetooth_up():
    """Return True if hci0 is UP RUNNING."""
    try:
        r = subprocess.run(
            ["hciconfig", "hci0"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return "UP RUNNING" in (r.stdout or "")
    except Exception:
        return False


def _ensure_bluetooth_on():
    """Unblock, start bluetoothd, and bring hci0 up. Skip if already up."""
    import time
    if _is_bluetooth_up():
        return
    script = Path(__file__).resolve().parent / "enable_bluetooth.sh"
    try:
        subprocess.run(["rfkill", "unblock", "bluetooth"], capture_output=True, timeout=3)
        if script.is_file():
            subprocess.run(["sudo", "-n", str(script)], capture_output=True, timeout=10)
        else:
            subprocess.run(["bluetoothctl", "--", "power", "on"], capture_output=True, timeout=5, env=_env())
        time.sleep(0.5)
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass


@app.route("/api/scan/ble", methods=["POST"])
def scan_ble():
    """Scan for SmartBall. Fast path: cached devices; else bluetoothctl scan 5s (BLE) or hcitool 10s."""
    import subprocess
    devices = []
    code = 0
    err = None
    try:
        _ensure_bluetooth_on()
        # 1. Try cached devices first (fast, ~1-2s)
        try:
            code2, out2, err2 = _run(["bluetoothctl", "devices"], timeout=3)
            if err2 and any(h in (err2 or "").lower() for h in ("no default", "org.bluez", "connection refused")):
                err = BT_OFF_MSG
                return jsonify({"devices": [], "error": err})
            for line in (out2 or "").splitlines():
                parts = line.split(None, 2)
                if len(parts) >= 2 and parts[0] == "Device":
                    addr, name = parts[1], (parts[2] if len(parts) > 2 else "")
                    if "smartball" in name.lower():
                        devices.append({"address": addr, "name": name})
        except subprocess.TimeoutExpired:
            pass
        # 2. If not cached, run short scan: bluetoothctl scan 5s (BLE, ~7s total vs hcitool 10s)
        if not devices:
            try:
                r = subprocess.run(
                    ["bluetoothctl", "scan", "on"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=_env(),
                )
                if r.returncode != 0 and any(h in (r.stderr or "").lower() for h in ("no default", "org.bluez", "connection refused")):
                    err = BT_OFF_MSG
                    return jsonify({"devices": [], "error": err})
                time.sleep(5)
                # scan off = stop discovery only; does NOT power off the adapter
                subprocess.run(
                    ["bluetoothctl", "scan", "off"],
                    capture_output=True,
                    timeout=2,
                    env=_env(),
                )
                code2, out2, _ = _run(["bluetoothctl", "devices"], timeout=3)
                for line in (out2 or "").splitlines():
                    parts = line.split(None, 2)
                    if len(parts) >= 2 and parts[0] == "Device":
                        addr, name = parts[1], (parts[2] if len(parts) > 2 else "")
                        if "smartball" in name.lower():
                            devices.append({"address": addr, "name": name})
            except (subprocess.TimeoutExpired, Exception):
                pass
        # 3. Fallback: hcitool scan (classic, ~10s)
        if not devices:
            code, out, err = _run(["hcitool", "-i", "hci0", "scan"], timeout=12)
            for line in (out or "").splitlines():
                if "\t" in line and "Scanning" not in line:
                    parts = line.strip().split("\t", 1)
                    if len(parts) >= 2:
                        addr, name = parts[0].strip(), (parts[1] or "").strip()
                        if "smartball" in name.lower():
                            devices.append({"address": addr, "name": name})
    except subprocess.TimeoutExpired:
        err = "BLE scan timed out"
    except (FileNotFoundError, Exception) as e:
        err = str(e)
    # Detect Bluetooth off
    if err and any(h in str(err).lower() for h in BT_OFF_HINTS):
        err = BT_OFF_MSG
    elif not devices and not err and not _is_bluetooth_up():
        err = BT_OFF_MSG
    # If SmartBall found: connect (verify with smpmgr) and store address for subsequent operations
    # Must disconnect first if SmartBall is already connected (bluetooth-autoconnect, etc.) or Bleak gets InProgress.
    global _connected_ble_addr
    connected = False
    connect_err = None
    if devices and not err:
        addr = devices[0]["address"]
        _stop_ble_scan()
        # Explicitly disconnect so smpmgr/Bleak can connect (fixes "connect failed" when device visible in BT)
        subprocess.run(
            ["bluetoothctl", "disconnect", addr],
            capture_output=True,
            timeout=5,
            env=_env(),
        )
        time.sleep(3)  # BlueZ needs time to release; avoids org.bluez.Error.InProgress
        code_c, out_c, err_c = _run([str(SMPMGR), "--ble", addr, "--timeout", "25", "image", "state-read"])
        if code_c != 0 and "InProgress" in (err_c or "") + (out_c or ""):
            time.sleep(5)
            code_c, out_c, err_c = _run([str(SMPMGR), "--ble", addr, "--timeout", "25", "image", "state-read"])
        _restart_ble_autoconnect()
        if code_c != 0:
            connect_err = (err_c or "").strip() or (out_c or "").strip() or "Connection failed"
        if code_c == 0:
            _connected_ble_addr = addr
            connected = True
    return jsonify({
        "devices": devices,
        "error": err,
        "connected": connected,
        "address": _connected_ble_addr,
        "bt_enabled": _is_bluetooth_up(),
        "connect_error": connect_err if devices and not connected else None,
    })


def _list_serial_port_candidates():
    """Return list of candidate serial port paths (ttyACM*, ttyUSB*, by-id)."""
    ports = []
    for pattern in ["/dev/ttyACM*", "/dev/ttyUSB*"]:
        for p in glob.glob(pattern):
            if os.path.exists(p) and not os.path.isdir(p):
                ports.append(p)
    by_id = "/dev/serial/by-id"
    if os.path.isdir(by_id):
        for name in os.listdir(by_id):
            path = os.path.join(by_id, name)
            if os.path.islink(path):
                real = os.path.realpath(path)
                if os.path.exists(real) and real not in ports:
                    ports.append(real)
    return sorted(set(ports))


@app.route("/api/scan/debugger", methods=["POST"])
def scan_debugger():
    """Detect debug probe and check if board/target is connected (pyocd list)."""
    result = {"probes": [], "board_connected": False, "detail": None, "error": None}
    try:
        code, out, err = _run(
            [str(VENV / "pyocd"), "list"],
            timeout=10,
            cwd=str(WS),
        )
        if code != 0:
            result["error"] = (err or out or "pyocd list failed").strip()
            return jsonify(result)
        lines = (out or "").strip().splitlines()
        if not lines:
            result["detail"] = "No probe found. Connect debugger (e.g. Raspberry Pi Debug Probe)."
            return jsonify(result)
        for line in lines:
            if "---" in line or "Target" in line:
                continue
            parts = [p for p in line.split() if p]
            if len(parts) >= 4:
                probe_name = " ".join(parts[1:-2])
                target = parts[-1]
                result["probes"].append({"info": line.strip(), "probe": probe_name, "target": target})
                if target not in ("n/a", "-"):
                    result["board_connected"] = True
        if not result["probes"] and "CMSIS-DAP" in (out or ""):
            result["probes"] = [{"info": (out or "").strip(), "target": "n/a"}]
        if result["probes"] and not result["board_connected"]:
            result["detail"] = "Probe found but target n/a — check SWD wiring (DIO, CLK, GND)."
    except subprocess.TimeoutExpired:
        result["error"] = "pyocd list timed out"
    except FileNotFoundError:
        result["error"] = "pyocd not found (install: pip install pyocd)"
    return jsonify(result)


def _open_and_read_device_ids(port: str, timeout: float = 6.0) -> tuple[str | None, str | None]:
    """Open port and read device identity (serial + part). Returns (serial, part) or (None, None)."""
    try:
        import asyncio
        sys.path.insert(0, str(TOOLS_DIR / "msr1_ota"))
        from device_identity import query_serial
        ident = asyncio.run(query_serial(port, timeout=timeout))
        if ident and ident.get("rc") == 0:
            return (ident.get("serial"), ident.get("part"))
    except Exception:
        pass
    return (None, None)


@app.route("/api/scan/serial", methods=["POST"])
def scan_serial():
    """
    List serial ports. For each port, try to open and read device IDs (serial + part).
    A port is verified only when we successfully read serial and part from the device.
    """
    candidates = _list_serial_port_candidates()
    if not candidates:
        hint = None
        try:
            code, out, _ = _run(["lsusb"], timeout=5)
            if code == 0 and "2fe3" in (out or "") and "0100" in (out or ""):
                hint = "Nordic USB (2fe3:0100) seen but no serial port. Replug USB or flash firmware first."
        except Exception:
            pass
        return jsonify({
            "ports": [], "confirmed_port": None, "confirmed_reply": None,
            "serial_number": None, "part_number": None, "verified": False, "hint": hint,
        })
    confirmed_port = None
    serial_number = None
    part_number = None
    all_ports = []
    for p in candidates:
        all_ports.append({"path": p})
        serial, part = _open_and_read_device_ids(p, timeout=6.0)
        if serial and part:
            confirmed_port = p
            serial_number = serial
            part_number = part
            break
    confirmed_reply = None
    if not confirmed_port:
        for p in candidates:
            code, out, _ = _run(
                [str(SMPMGR), "--port", p, "--timeout", "8", "image", "state-read"],
                timeout=12,
            )
            if code == 0 and out and ("slot" in out.lower() or "active" in out.lower() or "version" in out.lower()):
                confirmed_port = p
                confirmed_reply = (out or "").strip()
                break
    return jsonify({
        "ports": all_ports,
        "confirmed_port": confirmed_port,
        "confirmed_reply": confirmed_reply,
        "serial_number": serial_number,
        "part_number": part_number,
        "verified": serial_number is not None and part_number is not None,
        "hint": None if confirmed_port else "No SmartBall found. Try opening and reading IDs on each port.",
    })


@app.route("/api/verify/port", methods=["POST"])
def verify_port():
    """
    Verify the given port by opening it and reading device IDs (serial + part).
    Port is correct only when we successfully read serial and part.
    """
    data = request.get_json() or {}
    port = data.get("port") or "/dev/ttyACM0"
    serial_number, part_number = _open_and_read_device_ids(port, timeout=8.0)
    verified = serial_number is not None and part_number is not None
    error = None
    if not verified:
        code, out, _ = _run(
            [str(SMPMGR), "--port", port, "--timeout", "8", "image", "state-read"],
            timeout=12,
        )
        if code != 0 or not out:
            error = "Could not open or read from port. Check connection and firmware."
        elif "slot" in (out or "").lower() or "active" in (out or "").lower():
            error = "Device responded but no device IDs (serial/part). Flash firmware with device_mgmt."
        else:
            error = "No SmartBall response on this port."
    return jsonify({
        "port": port,
        "serial_number": serial_number,
        "part_number": part_number,
        "verified": verified,
        "error": error,
    })


@app.route("/api/ensure-bt", methods=["GET"])
def ensure_bt():
    """Start Bluetooth if off. Returns when BT is up (or failed)."""
    _ensure_bluetooth_on()
    time.sleep(1)
    return jsonify({"bt_enabled": _is_bluetooth_up()})


@app.route("/api/connection", methods=["GET"])
def get_connection():
    """Return BLE adapter status and SmartBall connection status.
    If BT adapter is off, connected is always False (we cannot be connected)."""
    bt_up = _is_bluetooth_up()
    connected = bt_up and _connected_ble_addr is not None
    return jsonify({
        "bt_enabled": bt_up,
        "connected": connected,
        "address": _connected_ble_addr if connected else None,
    })


@app.route("/api/check-cached", methods=["GET"])
def check_cached():
    """Check cached BT devices only (no scan). If SmartBall is in cache, try to connect.
    Use on page load so SmartBall is detected when already visible in system BT."""
    global _connected_ble_addr
    bt_up = _is_bluetooth_up()
    if _connected_ble_addr and bt_up:
        return jsonify({"bt_enabled": True, "connected": True, "address": _connected_ble_addr})
    devices = []
    try:
        _ensure_bluetooth_on()
        code2, out2, err2 = _run(["bluetoothctl", "devices"], timeout=3)
        if err2 and any(h in (err2 or "").lower() for h in ("no default", "org.bluez", "connection refused")):
            return jsonify({"bt_enabled": False, "connected": False, "address": None})
        for line in (out2 or "").splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 2 and parts[0] == "Device":
                addr, name = parts[1], (parts[2] if len(parts) > 2 else "")
                if "smartball" in name.lower():
                    devices.append({"address": addr, "name": name})
    except Exception:
        pass
    if not devices:
        return jsonify({"bt_enabled": _is_bluetooth_up(), "connected": False, "address": None})
    addr = devices[0]["address"]
    # Use short timeout (8s) on page load so UI appears quickly when SmartBall is off/unreachable
    code_c, out_c, err_c = _run([str(SMPMGR), "--ble", addr, "--timeout", "8", "image", "state-read"], timeout=12)
    if code_c != 0 and _ble_needs_recovery(err_c, out_c):
        _stop_ble_scan()
        subprocess.run(["bluetoothctl", "disconnect", addr], capture_output=True, timeout=5, env=_env())
        time.sleep(2)
        code_c, out_c, err_c = _run([str(SMPMGR), "--ble", addr, "--timeout", "8", "image", "state-read"], timeout=12)
        _restart_ble_autoconnect()
    if code_c == 0:
        _connected_ble_addr = addr
    return jsonify({
        "bt_enabled": _is_bluetooth_up(),
        "connected": _connected_ble_addr is not None,
        "address": _connected_ble_addr,
    })


@app.route("/api/disconnect", methods=["POST"])
def disconnect():
    """Clear BLE connection so user can scan again."""
    global _connected_ble_addr
    _connected_ble_addr = None
    return jsonify({"ok": True})


@app.route("/api/images", methods=["GET"])
def list_images():
    """List v1/v2 images."""
    imgs = []
    for p in [IMAGES_DIR / "app_v1.bin", IMAGES_DIR / "app_v2.bin"]:
        if p.exists():
            imgs.append({
                "path": str(p),
                "name": p.name,
                "size": p.stat().st_size,
                "label": "v1 (single blink)" if "v1" in p.name else "v2 (double blink)",
            })
    return jsonify({"images": imgs})


def _activate_slot_via_smp(transport: str, addr: str | None, port: str, slot: str) -> tuple[int, str, str]:
    """Activate slot A (0) or B (1). A=confirm running. B=mark for test + reboot (user must confirm after reconnect)."""
    slot_num = 1 if slot.upper() == "B" else 0
    try:
        from smpclient import SMPClient
        from smpclient.transport.ble import SMPBLETransport
        from smpclient.transport.serial import SMPSerialTransport
        from smpclient.requests.image_management import ImageStatesRead, ImageStatesWrite
        from smpclient.requests.os_management import ResetWrite
        from smpclient.generics import success, error as smp_error
    except ImportError:
        return 1, "", "smpclient not available"
    transport_lower = (transport or "ble").lower()
    if transport_lower == "ble" and addr:
        client = SMPClient(SMPBLETransport(), addr)
    elif transport_lower == "serial":
        client = SMPClient(SMPSerialTransport(), port)
    else:
        return 1, "", "BLE requires address"

    async def run():
        await client.connect(25.0)
        if slot_num == 0:
            r2 = await client.request(ImageStatesWrite(confirm=True), 25.0)
            await client.disconnect()
            if smp_error(r2):
                return 1, "", str(r2)
            return 0, "Slot A (running) confirmed.", ""
        r = await client.request(ImageStatesRead(), 25.0)
        if smp_error(r):
            return 1, "", str(r)
        if not success(r) or not hasattr(r, "images"):
            return 1, "", "Invalid state-read response"
        img = next((x for x in r.images if x.slot == 1), None)
        if not img:
            return 1, "", "No image in slot B"
        hash_bytes = getattr(img, "hash", None)
        if hash_bytes is None or (isinstance(hash_bytes, bytes) and len(hash_bytes) == 0):
            return 1, "", "Slot B has no hash"
        r2 = await client.request(ImageStatesWrite(hash=hash_bytes, confirm=False), 25.0)
        if smp_error(r2):
            return 1, "", str(r2)
        r3 = await client.request(ResetWrite(), 25.0)
        await client.disconnect()
        if smp_error(r3):
            return 1, "", str(r3)
        return 0, (
            "Slot B marked for boot. Device is rebooting.\n"
            "After it reconnects, select Slot A and click Activate to confirm."
        ), ""

    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = StringIO(), StringIO()
        return asyncio.run(run())
    except Exception as e:
        return 1, "", str(e)
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def _read_version_via_smp(transport: str, addr: str | None, port: str) -> tuple[int, str, str]:
    """Read image states via smpclient and return formatted output. Returns (code, stdout, stderr)."""
    try:
        from smpclient import SMPClient
        from smpclient.transport.ble import SMPBLETransport
        from smpclient.transport.serial import SMPSerialTransport
        from smpclient.requests.image_management import ImageStatesRead
        from smpclient.generics import success, error as smp_error
    except ImportError:
        return 1, "", "smpclient not available"
    t = (transport or "ble").lower()
    if t == "ble" and addr:
        client = SMPClient(SMPBLETransport(), addr)
    elif t == "serial":
        client = SMPClient(SMPSerialTransport(), port)
    else:
        return 1, "", "BLE requires address"

    async def run():
        await client.connect(25.0)
        r = await client.request(ImageStatesRead(), 25.0)
        await client.disconnect()
        if smp_error(r):
            return 1, "", str(r)
        if not success(r) or not hasattr(r, "images"):
            return 1, "", "Invalid response"
        lines = []
        for img in sorted(r.images, key=lambda x: x.slot):
            slot_name = "A" if img.slot == 0 else "B"
            flags = []
            if getattr(img, "active", None):
                flags.append("active")
            if getattr(img, "confirmed", None):
                flags.append("confirmed")
            if getattr(img, "pending", None):
                flags.append("pending")
            if getattr(img, "permanent", None):
                flags.append("permanent")
            ver = getattr(img, "version", "?")
            flags_str = ", ".join(flags) if flags else "-"
            lines.append(f"Slot {slot_name} ({img.slot}): v{ver} — {flags_str}")
        return 0, "\n".join(lines), ""

    old_out, old_err = sys.stdout, sys.stderr
    try:
        sys.stdout, sys.stderr = StringIO(), StringIO()
        return asyncio.run(run())
    except Exception as e:
        return 1, "", str(e)
    finally:
        sys.stdout, sys.stderr = old_out, old_err


def _ble_needs_recovery(err, out):
    """True if smpmgr failed due to connection issues (InProgress, disconnected, etc)."""
    s = (err or "") + (out or "")
    s = s.lower()
    return (
        "inprogress" in s
        or "disconnected" in s
        or "failed to discover services" in s
        or "bleakerror" in s
        or "no bluetooth adapters found" in s
        or "smpbladaptererror" in s
    )


@app.route("/api/version/read", methods=["POST"])
def read_version():
    """Read image states via smpclient. Returns formatted slot summary."""
    data = request.get_json() or {}
    addr = data.get("address") or data.get("addr") or _connected_ble_addr
    transport = data.get("transport", "ble")
    if not addr and transport == "ble":
        return jsonify({"error": "Not connected. Scan for SmartBall first."}), 400
    port = data.get("port", "/dev/ttyACM0")
    code, out, err = _read_version_via_smp(transport, addr, port)
    if transport == "ble" and code != 0 and _ble_needs_recovery(err, out):
        _stop_ble_scan()
        _prepare_ble_before_smpmgr(addr)
        code, out, err = _read_version_via_smp(transport, addr, port)
        _restart_ble_autoconnect()
    return jsonify({"ok": code == 0, "stdout": out, "stderr": err, "error": None if code == 0 else (err or out)})


@app.route("/api/version/activate", methods=["POST"])
def activate_version():
    """Activate slot A (0) or B (1). Slot B requires reading hash from device first."""
    data = request.get_json() or {}
    addr = data.get("address") or data.get("addr") or _connected_ble_addr
    transport = data.get("transport", "ble")
    slot = data.get("slot", "A")  # A=primary/0, B=secondary/1
    if not addr and transport == "ble":
        return jsonify({"error": "Not connected. Scan for SmartBall first."}), 400
    port = data.get("port", "/dev/ttyACM0")

    if slot.upper() == "B":
        code, out, err = _activate_slot_via_smp(transport, addr, port, slot)
        if transport == "ble" and code != 0 and _ble_needs_recovery(err, out):
            _stop_ble_scan()
            _prepare_ble_before_smpmgr(addr)
            code, out, err = _activate_slot_via_smp(transport, addr, port, slot)
            _restart_ble_autoconnect()
    else:
        if transport == "serial":
            cmd = [str(SMPMGR), "--port", port, "--timeout", "20", "image", "state-write", "--confirm"]
        else:
            cmd = [str(SMPMGR), "--ble", addr, "--timeout", "25", "image", "state-write", "--confirm"]
        code, out, err = _run(cmd)
        if transport == "ble" and code != 0 and _ble_needs_recovery(err, out):
            _stop_ble_scan()
            _prepare_ble_before_smpmgr(addr)
            code, out, err = _run(cmd)
            _restart_ble_autoconnect()
    return jsonify({"ok": code == 0, "stdout": out, "stderr": err, "error": None if code == 0 else (err or out)})


@app.route("/api/upgrade", methods=["POST"])
def upgrade():
    """OTA upgrade via Serial, BLE, or Debugger."""
    try:
        return _upgrade_impl()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "stdout": "", "stderr": ""}), 500


def _upgrade_impl():
    """OTA upgrade implementation."""
    data = request.get_json() or {}
    image = data.get("image")
    transport = data.get("transport")
    addr = data.get("address") or data.get("addr")
    port = (data.get("port") or "/dev/ttyACM0").strip() or "/dev/ttyACM0"
    if not image:
        return jsonify({"error": "Valid image file required"}), 400
    # Resolve image path: allow absolute or relative to msr1_ota
    image_path = Path(image)
    if not image_path.is_absolute():
        image_path = (TOOLS_DIR / "msr1_ota" / image).resolve()
    if not image_path.is_file():
        return jsonify({"error": f"Image file not found: {image}"}), 400
    image = str(image_path)
    addr = addr or _connected_ble_addr
    if transport == "ble":
        if not addr:
            return jsonify({"error": "Not connected. Scan for SmartBall first."}), 400
        base = [str(SMPMGR), "--ble", addr, "--timeout", "90"]
    elif transport == "serial":
        base = [str(SMPMGR), "--port", port, "--timeout", "90"]
    else:
        base = None
    if base is not None:
        # Release BLE so smpmgr gets clean connection. Use gentle prep (no bluetooth restart)
        # to avoid "No Bluetooth adapters found" after systemctl restart bluetooth.
        if transport == "ble":
            _prepare_ble_gentle(addr)
        # Erase slot 1 first to free it (avoids NO_FREE_SLOT when both slots full)
        _run(base + ["image", "erase", "1"], timeout=120)
        cmd = base + ["upgrade", "--slot", "1", image]
    elif transport == "debugger":
        # Build selected version into workspace, then flash
        v = "v1" if "v1" in image else "v2"
        build_script = f"""set -e
source {VENV}/activate
source {WS}/zephyr/zephyr-env.sh
cd {WS}
west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \\
  -DEXTRA_CONF_FILE=prj_v1.conf -DAPP_LED_SLOT=1
""" if v == "v1" else f"""set -e
source {VENV}/activate
source {WS}/zephyr/zephyr-env.sh
cd {WS}
west build -b xiao_ble_sense nrf/app --sysbuild --pristine -- \\
  -DEXTRA_CONF_FILE=prj_v2.conf -DAPP_LED_SLOT=0
"""
        r = subprocess.run(
            ["bash", "-c", build_script],
            capture_output=True,
            text=True,
            timeout=180,
            env=_env(),
        )
        if r.returncode != 0:
            return jsonify({"ok": False, "error": r.stderr or r.stdout})
        flash_script = TOOLS_DIR / "scripts" / "flash_xiao.sh"
        r = subprocess.run(
            ["bash", str(flash_script)],
            cwd=str(TOOLS_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            env=_env(),
        )
        return jsonify({"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr, "error": None if r.returncode == 0 else (r.stderr or r.stdout)})
    else:
        return jsonify({"error": "transport must be serial, ble, or debugger"}), 400
    code, out, err = _run(cmd)
    # Retry: if NO_FREE_SLOT, erase slot 1 again and retry upgrade
    if code != 0 and base is not None and "NO_FREE_SLOT" in (err or out or ""):
        _run(base + ["image", "erase", "1"], timeout=120)
        code, out, err = _run(cmd)
    if transport == "ble" and code != 0 and _ble_needs_recovery(err, out):
        _prepare_ble_gentle(addr)
        code, out, err = _run(cmd)
    if transport == "ble":
        _restart_ble_autoconnect()
    err_msg = None if code == 0 else (err or out)
    if code != 0 and "NO_FREE_SLOT" in (err_msg or ""):
        err_msg = (err_msg or "") + "\n\nTo fix: flash firmware once via Debugger. prj.conf has CONFIG_MCUMGR_GRP_IMG_ALLOW_ERASE_PENDING."
    return jsonify({"ok": code == 0, "stdout": out, "stderr": err, "error": err_msg})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
