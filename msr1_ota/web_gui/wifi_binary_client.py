"""
SmartBall WiFi (ESP32-C6) binary protocol client.
Same frame format as BLE; POST to http://<device_ip>/api/cmd.
Use when device runs msr1_esp32c6 firmware (STA: host at device IP).
"""
import struct
from pathlib import Path

# Reuse protocol constants and make_frame from BLE client
sys_path = Path(__file__).resolve().parent
if str(sys_path) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(sys_path))
from ble_binary_client import (
    make_frame,
    format_response,
    CMD_ID,
    CMD_STATUS,
    CMD_DIAG,
    CMD_SELFTEST,
    CMD_GET_CFG,
    CMD_BUS_SCAN,
    CMD_LIST_SHOTS,
    CMD_GET_SHOT_CHUNK,
    RSP_ID,
    RSP_STATUS,
    RSP_DIAG,
    RSP_SELFTEST,
    RSP_CFG,
    RSP_BUS_SCAN,
    RSP_SHOT,
    RSP_SHOT_LIST,
)

DEFAULT_DEVICE_URL = "http://192.168.4.1"
TIMEOUT = 10.0

try:
    import requests
except ImportError:
    requests = None


def send_binary_cmd(device_url: str, frame: bytes, timeout: float = TIMEOUT) -> tuple[bytes | None, str | None]:
    """POST binary frame to device, return (response_bytes, error_message)."""
    if not requests:
        return (None, "requests not installed (pip install requests)")
    url = f"{device_url.rstrip('/')}/api/cmd"
    try:
        r = requests.post(url, data=frame, timeout=timeout)
        r.raise_for_status()
        return (r.content, None)
    except requests.RequestException as e:
        return (None, str(e))


def get_id(device_url: str = DEFAULT_DEVICE_URL) -> tuple[dict | None, str | None]:
    """Return (dict with fw_ver, proto, hw_rev, uid), or (None, error)."""
    rsp, err = send_binary_cmd(device_url, make_frame(CMD_ID, payload=b"\x00"))
    if err or not rsp or len(rsp) < 16:
        return (None, err or "no response")
    if rsp[0] != RSP_ID:
        return (None, f"unexpected type 0x{rsp[0]:02x}")
    fw = struct.unpack_from("<H", rsp, 3)[0]
    proto, hw = rsp[5], rsp[6]
    uid_len = rsp[7]
    uid = rsp[9:9 + min(uid_len, 8)].hex() if uid_len else ""
    return ({"fw_ver": f"{fw >> 8}.{fw & 0xFF}", "proto": proto, "hw_rev": hw, "uid": uid}, None)


def get_status(device_url: str = DEFAULT_DEVICE_URL) -> tuple[bytes | None, str | None]:
    """Return (raw RSP_STATUS bytes, None) or (None, error). Use format_response(rsp) for display."""
    rsp, err = send_binary_cmd(device_url, make_frame(CMD_STATUS, payload=b"\x00"))
    if err:
        return (None, err)
    if not rsp or len(rsp) < 4 or rsp[0] != RSP_STATUS:
        return (None, f"unexpected type 0x{rsp[0]:02x}" if rsp else "no response")
    return (rsp, None)


def get_diag(device_url: str = DEFAULT_DEVICE_URL) -> tuple[bytes | None, str | None]:
    """Return (raw RSP_DIAG bytes, None) or (None, error). Use format_response(rsp) for display."""
    rsp, err = send_binary_cmd(device_url, make_frame(CMD_DIAG, payload=b"\x00"))
    if err:
        return (None, err)
    if not rsp or len(rsp) < 4 or rsp[0] != RSP_DIAG:
        return (None, f"unexpected type 0x{rsp[0]:02x}" if rsp else "no response")
    return (rsp, None)


def get_selftest(device_url: str = DEFAULT_DEVICE_URL) -> tuple[bool | None, str | None]:
    """Return (True=pass, False=fail) or (None, error)."""
    rsp, err = send_binary_cmd(device_url, make_frame(CMD_SELFTEST, payload=b"\x00"))
    if err or not rsp or len(rsp) < 4:
        return (None, err or "no response")
    if rsp[0] != RSP_SELFTEST:
        return (None, f"unexpected type 0x{rsp[0]:02x}")
    return (rsp[3] == 0, None)


def get_bus_scan(device_url: str = DEFAULT_DEVICE_URL) -> tuple[bytes | None, str | None]:
    """Return (raw RSP_BUS_SCAN bytes, None) or (None, error). Use format_response(rsp) for display."""
    rsp, err = send_binary_cmd(device_url, make_frame(CMD_BUS_SCAN, payload=b"\x00"))
    if err:
        return (None, err)
    if not rsp or len(rsp) < 4 or rsp[0] != RSP_BUS_SCAN:
        return (None, f"unexpected type 0x{rsp[0]:02x}" if rsp else "no response")
    return (rsp, None)


def get_config(device_url: str = DEFAULT_DEVICE_URL) -> tuple[bytes | None, str | None]:
    """Return (raw RSP_CFG bytes, None) or (None, error). Use format_response(rsp) for display."""
    rsp, err = send_binary_cmd(device_url, make_frame(CMD_GET_CFG, payload=b"\x00"))
    if err:
        return (None, err)
    if not rsp or len(rsp) < 4 or rsp[0] != RSP_CFG:
        return (None, f"unexpected type 0x{rsp[0]:02x}" if rsp else "no response")
    return (rsp, None)


def get_shot_list(device_url: str = DEFAULT_DEVICE_URL) -> tuple[list[tuple[int, int]] | None, str | None]:
    """Return [(shot_id, size), ...] or (None, error)."""
    frame = make_frame(CMD_LIST_SHOTS, payload=b"\x00")
    rsp, err = send_binary_cmd(device_url, frame)
    if err or not rsp or len(rsp) < 4:
        return (None, err or "no response")
    if rsp[0] != RSP_SHOT_LIST:
        return (None, f"unexpected type 0x{rsp[0]:02x}")
    n = rsp[3]
    out = []
    for i in range(min(n, 32)):
        o = 4 + i * 8
        if o + 8 > len(rsp):
            break
        sid = struct.unpack_from("<I", rsp, o)[0]
        sz = struct.unpack_from("<I", rsp, o + 4)[0]
        out.append((sid, sz))
    return (out, None)


def fetch_shot_chunked_sync(
    device_url: str,
    shot_id: int,
    size: int,
    chunk_size: int = 495,
    timeout_per_chunk: float = 10.0,
) -> tuple[bytes | None, str | None]:
    """Fetch full shot via GET_SHOT_CHUNK over WiFi. Returns (payload, error)."""
    total = b""
    offset = 0
    while offset < size:
        frame = make_frame(CMD_GET_SHOT_CHUNK, payload=struct.pack("<IH", shot_id, offset))
        rsp, err = send_binary_cmd(device_url, frame, timeout=timeout_per_chunk)
        if err:
            return (None, err)
        if not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT:
            return (None, f"chunk at offset {offset}: bad response")
        plen = struct.unpack_from("<H", rsp, 1)[0]
        total += rsp[3 : 3 + plen]
        offset += plen
        if plen == 0:
            break
    if len(total) < size:
        return (None, f"incomplete: got {len(total)}/{size} bytes")
    return (total, None)


def fetch_shot_sync(device_url: str, shot_id: int, size: int) -> tuple[bytes | None, str | None]:
    """Convenience: fetch full shot (chunked)."""
    return fetch_shot_chunked_sync(device_url, shot_id, size)
