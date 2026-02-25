"""
SmartBall BLE Binary Protocol client — send commands over SVB1 GATT service.
Used by Web GUI and test runner.
Speed: shorter notify/poll delays (no connection cache — Flask uses asyncio.run per request).
"""
import asyncio
import struct
import sys
import time
from pathlib import Path

# Ensure bleak is available
_venv = Path(__file__).resolve().parents[2] / ".venv" / "lib" / "python3.11" / "site-packages"
sys.path.insert(0, str(_venv))

SB_RX_CHAR = "53564231-5342-4c31-8000-000000000002"
SB_TX_CHAR = "53564231-5342-4c31-8000-000000000003"

CMD_ID, CMD_STATUS, CMD_DIAG, CMD_SELFTEST = 0x01, 0x02, 0x03, 0x04
CMD_CLEAR_ERRORS, CMD_SET, CMD_GET_CFG, CMD_SAVE_CFG, CMD_LOAD_CFG = 0x05, 0x06, 0x07, 0x08, 0x09
CMD_FACTORY_RESET, CMD_START_RECORD, CMD_STOP_RECORD = 0x0A, 0x0B, 0x0C
CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_DEL_SHOT, CMD_FORMAT_STORAGE, CMD_BUS_SCAN = 0x0D, 0x0E, 0x0F, 0x10, 0x11
CMD_GET_SHOT_CHUNK = 0x12
CMD_SPI_READ = 0x13
CMD_SPI_WRITE = 0x14

RSP_ID, RSP_STATUS, RSP_DIAG, RSP_SELFTEST, RSP_BUS_SCAN = 0x81, 0x86, 0x87, 0x88, 0x89
RSP_SHOT, RSP_CFG, RSP_SHOT_LIST, RSP_SPI_DATA = 0x8A, 0x8B, 0x8C, 0x8D

CMD_NAMES = {
    CMD_ID: "ID", CMD_STATUS: "STATUS", CMD_DIAG: "DIAG", CMD_SELFTEST: "SELFTEST",
    CMD_CLEAR_ERRORS: "CLEAR_ERRORS", CMD_SET: "SET", CMD_GET_CFG: "GET_CFG",
    CMD_SAVE_CFG: "SAVE_CFG", CMD_LOAD_CFG: "LOAD_CFG", CMD_FACTORY_RESET: "FACTORY_RESET",
    CMD_START_RECORD: "START_RECORD", CMD_STOP_RECORD: "STOP_RECORD",
    CMD_LIST_SHOTS: "LIST_SHOTS", CMD_GET_SHOT: "GET_SHOT", CMD_GET_SHOT_CHUNK: "GET_SHOT_CHUNK",
    CMD_SPI_READ: "SPI_READ", CMD_SPI_WRITE: "SPI_WRITE",
    CMD_DEL_SHOT: "DEL_SHOT", CMD_FORMAT_STORAGE: "FORMAT_STORAGE", CMD_BUS_SCAN: "BUS_SCAN",
}


def make_frame(cmd: int, plen: int = 1, payload: bytes | None = None) -> bytes:
    if payload is not None:
        plen = len(payload)
    pad = payload if payload else (b"\x00" * plen)
    return struct.pack("<BH", cmd, plen) + pad[:plen]


# Shorter delays for faster round-trip: 50ms after notify, poll every 25ms
_NOTIFY_SETTLE_SEC = 0.05
_POLL_INTERVAL_SEC = 0.025


async def _send_cmd(client, frame: bytes, timeout_sec: float = 3.0) -> bytes | None:
    rsp = [None]
    def notif(_, data: bytearray):
        rsp[0] = bytes(data)
    await client.start_notify(SB_TX_CHAR, notif)
    await asyncio.sleep(_NOTIFY_SETTLE_SEC)
    await client.write_gatt_char(SB_RX_CHAR, frame, response=False)
    polls = int(timeout_sec / _POLL_INTERVAL_SEC)
    try:
        for _ in range(max(1, polls)):
            await asyncio.sleep(_POLL_INTERVAL_SEC)
            if rsp[0] is not None:
                return rsp[0]
        return None
    finally:
        try:
            await client.stop_notify(SB_TX_CHAR)
        except Exception:
            pass


async def send_binary_cmd(addr: str, frame: bytes, timeout_sec: float = 3.0) -> tuple[bytes | None, str | None]:
    """Connect, send frame, return (response_bytes, error_message)."""
    from bleak import BleakClient
    try:
        async with BleakClient(addr) as client:
            rsp = await _send_cmd(client, frame, timeout_sec)
            return (rsp, None)
    except Exception as e:
        return (None, str(e))


def send_binary_cmd_sync(addr: str, frame: bytes, timeout_sec: float = 3.0) -> tuple[bytes | None, str | None]:
    """Synchronous wrapper for Flask."""
    return asyncio.run(send_binary_cmd(addr, frame, timeout_sec))


# Chunk size: firmware BLE_BIN_MAX_PAYLOAD (495 with L2CAP_MTU=498; fallback 240 for older FW)
FETCH_SHOT_CHUNK_SIZE = 495
# One chunk per connection (legacy stable path)
CHUNKS_PER_CONNECTION = 1
_BETWEEN_CONNECTION_SEC = 1.5


def _is_disconnect_error(err: str) -> bool:
    s = (err or "").lower()
    return "disconnect" in s or "failed to discover" in s or "not found" in s or "in progress" in s


async def fetch_shot_one_connection_async(
    addr: str,
    shot_id: int,
    size: int,
    chunk_size: int = FETCH_SHOT_CHUNK_SIZE,
    timeout_per_chunk: float = 5.0,
    delay_between_chunks_sec: float = 0.04,
) -> tuple[bytes | None, str | None]:
    """Fetch full shot in ONE BLE connection; delay_between_chunks_sec can help avoid mid-transfer disconnect."""
    from bleak import BleakClient
    if size <= 0:
        return (None, "invalid size")
    if size <= chunk_size:
        frame = make_frame(CMD_GET_SHOT, payload=struct.pack("<I", shot_id))
        rsp, err = await send_binary_cmd(addr, frame, timeout_per_chunk)
        if err:
            return (None, err)
        if not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT:
            return (None, "no response or not RSP_SHOT")
        plen = struct.unpack_from("<H", rsp, 1)[0]
        return (rsp[3:3 + plen], None)
    try:
        async with BleakClient(addr) as client:
            payload = b""
            offset = 0
            while offset < size:
                frame = make_frame(CMD_GET_SHOT_CHUNK, payload=struct.pack("<IH", shot_id, offset))
                rsp = await _send_cmd(client, frame, timeout_sec=timeout_per_chunk)
                if not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT:
                    return (None, "chunk failed or timeout")
                plen = struct.unpack_from("<H", rsp, 1)[0]
                payload += rsp[3:3 + plen]
                offset += plen
                if plen < chunk_size:
                    break
                if delay_between_chunks_sec > 0:
                    await asyncio.sleep(delay_between_chunks_sec)
            if len(payload) < size:
                return (None, "incomplete fetch")
            return (payload, None)
    except Exception as e:
        return (None, str(e))


def fetch_shot_one_connection_sync(
    addr: str,
    shot_id: int,
    size: int,
    chunk_size: int = FETCH_SHOT_CHUNK_SIZE,
    timeout_per_chunk: float = 5.0,
    delay_between_chunks_sec: float = 0.04,
) -> tuple[bytes | None, str | None]:
    return asyncio.run(
        fetch_shot_one_connection_async(
            addr, shot_id, size, chunk_size, timeout_per_chunk, delay_between_chunks_sec
        )
    )


async def fetch_shot_chunked_async(
    addr: str,
    shot_id: int,
    size: int,
    chunk_size: int = FETCH_SHOT_CHUNK_SIZE,
    timeout_per_chunk: float = 5.0,
    between_segment_callback=None,
) -> tuple[bytes | None, str | None]:
    """Fetch full shot by GET_SHOT_CHUNK. One chunk per connection; optional callback between segments (e.g. force disconnect + wait)."""
    from bleak import BleakClient
    if size <= 0:
        return (None, "invalid size")
    if size <= chunk_size:
        frame = make_frame(CMD_GET_SHOT, payload=struct.pack("<I", shot_id))
        rsp, err = await send_binary_cmd(addr, frame, timeout_per_chunk)
        if err:
            return (None, err)
        if not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT:
            return (None, "no response or not RSP_SHOT")
        plen = struct.unpack_from("<H", rsp, 1)[0]
        return (rsp[3:3 + plen], None)
    total_payload = b""
    offset = 0
    max_retries = 5
    loop = asyncio.get_event_loop()
    while offset < size:
        if offset > 0:
            if between_segment_callback is not None:
                await loop.run_in_executor(None, lambda o=offset: between_segment_callback(o))
            else:
                await asyncio.sleep(_BETWEEN_CONNECTION_SEC)
        chunk_count_this_conn = 0
        attempt = 0
        while attempt < max_retries:
            try:
                async with BleakClient(addr) as client:
                    while offset < size and chunk_count_this_conn < CHUNKS_PER_CONNECTION:
                        frame = make_frame(CMD_GET_SHOT_CHUNK, payload=struct.pack("<IH", shot_id, offset))
                        rsp = await _send_cmd(client, frame, timeout_sec=timeout_per_chunk)
                        if not rsp or len(rsp) < 4 or rsp[0] != RSP_SHOT:
                            return (None, "chunk failed or timeout")
                        plen = struct.unpack_from("<H", rsp, 1)[0]
                        total_payload += rsp[3:3 + plen]
                        offset += plen
                        chunk_count_this_conn += 1
                        if plen < chunk_size:
                            break
                    if offset >= size or len(total_payload) >= size:
                        break
                    break
            except Exception as e:
                err_msg = str(e)
                if not _is_disconnect_error(err_msg):
                    return (None, err_msg)
                attempt += 1
                if attempt >= max_retries:
                    return (None, err_msg + " (retries exhausted)")
                await asyncio.sleep(_BETWEEN_CONNECTION_SEC)
                continue
    if len(total_payload) < size:
        return (None, "incomplete fetch")
    return (total_payload, None)


def fetch_shot_chunked_sync(
    addr: str,
    shot_id: int,
    size: int,
    chunk_size: int = FETCH_SHOT_CHUNK_SIZE,
    timeout_per_chunk: float = 5.0,
    between_segment_callback=None,
) -> tuple[bytes | None, str | None]:
    """Synchronous wrapper for Flask."""
    return asyncio.run(
        fetch_shot_chunked_async(addr, shot_id, size, chunk_size, timeout_per_chunk, between_segment_callback)
    )


def spi_read_sync(addr: str, cs: int, reg: int, length: int, timeout_sec: float = 5.0) -> tuple[bytes | None, str | None]:
    """Read from chip register over BLE. cs: 0=LSM6, 1=ADXL. Returns (data_bytes, error)."""
    if cs > 1 or length <= 0 or length > 240:
        return (None, "cs must be 0 or 1; length 1..240")
    payload = struct.pack("<BBB", cs, reg & 0xFF, length)
    frame = make_frame(CMD_SPI_READ, payload=payload)
    rsp, err = send_binary_cmd_sync(addr, frame, timeout_sec)
    if err:
        return (None, err)
    if not rsp or len(rsp) < 3:
        return (None, "no response")
    if rsp[0] != RSP_SPI_DATA:
        return (None, f"unexpected response type 0x{rsp[0]:02X}")
    plen = struct.unpack_from("<H", rsp, 1)[0]
    data = rsp[3:3 + plen] if len(rsp) >= 3 + plen else rsp[3:]
    return (data, None)


def spi_write_sync(addr: str, cs: int, reg: int, data: bytes, timeout_sec: float = 5.0) -> tuple[bool, str | None]:
    """Write to chip register over BLE. cs: 0=LSM6, 1=ADXL. Returns (ok, error)."""
    if cs > 1 or len(data) > 239:
        return (False, "cs must be 0 or 1; data max 239 bytes")
    payload = struct.pack("<BB", cs, reg & 0xFF) + data
    frame = make_frame(CMD_SPI_WRITE, payload=payload)
    rsp, err = send_binary_cmd_sync(addr, frame, timeout_sec)
    if err:
        return (False, err)
    if not rsp or len(rsp) < 3:
        return (False, "no response")
    if rsp[0] != RSP_STATUS:
        return (False, f"unexpected response type 0x{rsp[0]:02X}")
    return (True, None)


def format_response(rsp: bytes | None) -> str:
    """Format binary response for display."""
    if rsp is None or len(rsp) < 3:
        return "(no response)"
    rtype = rsp[0]
    plen = struct.unpack_from("<H", rsp, 1)[0]
    payload = rsp[3:3 + plen] if len(rsp) >= 3 + plen else rsp[3:]
    lines = []
    if rtype == RSP_ID and len(rsp) >= 16:
        fw = struct.unpack_from("<H", rsp, 3)[0]
        proto, hw = rsp[5], rsp[6]
        uid = rsp[9:17].hex()
        lines.append("--- Device ID ---")
        lines.append(f"  FW version: {fw >> 8}.{fw & 0xFF}")
        lines.append(f"  Protocol: {proto}  HW rev: {hw}")
        lines.append(f"  UID: {uid}")
    elif rtype == RSP_STATUS and len(rsp) >= 38:
        uptime = struct.unpack_from("<I", rsp, 3)[0]
        last_err = struct.unpack_from("<I", rsp, 7)[0]
        err_flags = struct.unpack_from("<I", rsp, 11)[0]
        dev_state = rsp[15]
        samples = struct.unpack_from("<I", rsp, 16)[0]
        sat_int, sat_lsm = rsp[20], rsp[21]
        stor_used = struct.unpack_from("<I", rsp, 22)[0]
        stor_free = struct.unpack_from("<I", rsp, 26)[0]
        temp_s8 = struct.unpack_from("<b", rsp, 32)[0]
        reset_reason = rsp[33]
        build_id = struct.unpack_from("<I", rsp, 34)[0]
        state_name = "recording" if dev_state == 2 else "idle"
        reset_names = {0: "?", 1: "POR", 2: "pin", 3: "soft", 4: "lockup", 5: "watchdog", 6: "other"}
        lines.append("--- Status ---")
        lines.append(f"  State: {state_name}  Uptime: {uptime // 1000}s")
        lines.append(f"  Samples: {samples}  Saturation: internal={sat_int} lsm={sat_lsm}")
        lines.append(f"  Storage: used={stor_used} B  free={stor_free} B")
        lines.append(f"  Temp: {temp_s8 * 0.1:.1f}°C  Reset: {reset_names.get(reset_reason, reset_reason)}")
        if last_err or err_flags:
            lines.append(f"  Last error: {last_err}  Flags: 0x{err_flags:08X}")
        if len(rsp) >= 68:
            ble_conn = rsp[38]
            rssi = struct.unpack_from("<b", rsp, 39)[0]
            rssi_avg = struct.unpack_from("<b", rsp, 40)[0]
            conn_int = struct.unpack_from("<H", rsp, 41)[0]
            mtu = struct.unpack_from("<H", rsp, 43)[0]
            pkt_tx = struct.unpack_from("<I", rsp, 46)[0]
            pkt_rx = struct.unpack_from("<I", rsp, 50)[0]
            lines.append("--- BLE ---")
            lines.append(f"  Connected: {bool(ble_conn)}  RSSI: {rssi} dBm  MTU: {mtu}")
            lines.append(f"  Packets TX/RX: {pkt_tx}/{pkt_rx}  Interval: {conn_int} ms")
    elif rtype == RSP_DIAG and len(rsp) >= 10:
        imu_ready = rsp[3]
        whoami = rsp[4]
        voltage_mv = struct.unpack_from("<H", rsp, 7)[0]
        temp_s8 = struct.unpack_from("<b", rsp, 9)[0]
        lines.append("--- Diagnostics ---")
        lines.append(f"  Internal IMU: {'ready' if imu_ready else 'not ready'}")
        lines.append(f"  WHO_AM_I: 0x{whoami:02X}" + (" (LSM6DS3TR-C)" if whoami == 0x6A else ""))
        lines.append(f"  Voltage: {voltage_mv} mV" + (f" ({voltage_mv/1000:.2f} V)" if voltage_mv > 0 else " (n/a)"))
        lines.append(f"  Temp: {temp_s8 * 0.1:.1f}°C")
        if len(rsp) >= 16:
            lsm6_ok = rsp[10]
            fa = struct.unpack_from("<H", rsp, 11)[0]
            fg = struct.unpack_from("<H", rsp, 13)[0]
            lines.append("--- LSM6DSOX (SPI) debug ---")
            lines.append(f"  Last read OK: {'yes' if lsm6_ok else 'no'}")
            lines.append(f"  Fail accel: {fa}  Fail gyro: {fg}")
    elif rtype == RSP_SELFTEST and len(rsp) >= 4:
        result = rsp[3]
        lines.append("--- Self-test ---")
        lines.append(f"  Result: {'PASS' if result == 0 else 'FAIL'}")
    elif rtype == RSP_CFG and len(rsp) > 4:
        n = rsp[3]
        lines.append("--- Config ---")
        off = 4
        for i in range(min(n, 16)):
            if off + 2 > len(rsp):
                break
            klen, vlen = rsp[off], rsp[off + 1]
            off += 2
            if klen + vlen == 0 or off + klen + vlen > len(rsp):
                break
            key = bytes(rsp[off:off + klen - 1]).decode("utf-8", errors="replace") if klen > 1 else "(empty)"
            off += klen
            val_bytes = rsp[off:off + vlen]
            val_hex = val_bytes.hex()
            off += vlen
            # Decode known keys for human-readable display
            decoded = ""
            if key in ("sample_rate", "rate_int", "rate_lsm") and vlen == 2:
                hz = struct.unpack_from("<H", val_bytes, 0)[0]
                decoded = f" ({hz} Hz)"
            elif key in ("gyro_fs_int", "gyro_fs_lsm") and vlen == 2:
                dps = struct.unpack_from("<H", val_bytes, 0)[0]
                decoded = f" ({dps} dps)"
            elif key in ("accel_fs_int", "accel_fs_lsm") and vlen == 1:
                decoded = f" (±{val_bytes[0]}g)"
            elif key == "event_mode" and vlen == 1:
                mode = "event" if val_bytes[0] else "normal"
                decoded = f" ({mode})"
            elif key == "trigger_g" and vlen == 1:
                decoded = f" ({val_bytes[0]})"
            lines.append(f"  {key}: {val_hex}{decoded}")
    elif rtype == RSP_SHOT_LIST and len(rsp) > 4:
        n = rsp[3]
        lines.append("--- Shot list ---")
        lines.append(f"  Count: {n}")
        for i in range(min(n, 16)):
            off = 4 + i * 8
            if off + 8 <= len(rsp):
                sid = struct.unpack_from("<I", rsp, off)[0]
                sz = struct.unpack_from("<I", rsp, off + 4)[0]
                lines.append(f"  [{i}] id={sid}  size={sz} B")
    elif rtype == RSP_BUS_SCAN and len(rsp) >= 5:
        spi_n = rsp[3]
        off = 4
        spi_type_names = {1: "LSM6DSOX", 2: "ADXL375", 3: "W25Q64"}
        lines.append("--- SPI bus ---")
        for i in range(spi_n):
            if off + 6 > len(rsp):
                break
            stype, cs, id0, id1, id2, flags = rsp[off], rsp[off + 1], rsp[off + 2], rsp[off + 3], rsp[off + 4], rsp[off + 5]
            off += 6
            name = spi_type_names.get(stype, f"Type-{stype}")
            present = "✓" if (flags & 0x01) else "✗"
            if stype == 1:
                lines.append(f"  [{cs}] {name}  WHO_AM_I=0x{id0:02X}  {present}")
            elif stype == 2:
                lines.append(f"  [{cs}] {name}  DEVID=0x{id0:02X}  {present}")
            elif stype == 3:
                lines.append(f"  [{cs}] {name}  JEDEC={id0:02X}{id1:02X}{id2:02X}  {present}")
            else:
                lines.append(f"  [{cs}] {name}  id={id0:02X}{id1:02X}{id2:02X}  {present}")
        i2c_n = rsp[off] if off < len(rsp) else 0
        off += 1
        lines.append("--- I2C bus ---")
        for i in range(i2c_n):
            if off + 2 > len(rsp):
                break
            addr, flags = rsp[off], rsp[off + 1]
            off += 2
            present = "✓" if (flags & 0x01) else "✗"
            dev_name = "LSM6DS3TR-C" if addr == 0x6A else f"0x{addr:02X}"
            lines.append(f"  0x{addr:02X} ({dev_name})  {present}")
    elif rtype == RSP_SPI_DATA and len(rsp) >= 3:
        data_len = struct.unpack_from("<H", rsp, 1)[0]
        data = rsp[3:3 + data_len] if len(rsp) >= 3 + data_len else rsp[3:]
        lines.append("--- SPI read ---")
        lines.append(f"  {data_len} byte(s): {data.hex()}")
        if data_len <= 16:
            lines.append("  " + " ".join(f"{b:02X}" for b in data))
    if not lines:
        lines.append(f"Type: 0x{rtype:02X}  Payload: {plen} bytes")
    lines.append("")
    lines.append(f"Raw: {rsp.hex()[:180]}{'...' if len(rsp) > 90 else ''}")
    return "\n".join(lines)
