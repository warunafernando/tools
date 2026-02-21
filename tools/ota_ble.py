#!/usr/bin/env python3
"""
SmartBall OTA over BLE - stabilization plan: immediate START ack, wait READY, sliding window, resume.
- New protocol: OTA_START -> RSP_OTA OK; device sends MSG_OTA_READY when erase done; then OTA_DATA with window 4.
- Compatible with old device: accept RSP_OTA 0x00 after START and proceed without waiting for READY.
Usage: python ota_ble.py firmware.bin [version]
"""
import sys
import struct
import asyncio
import time

try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakError
except ImportError:
    print("Install bleak: pip install bleak")
    sys.exit(1)

NUS_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
OTA_MAGIC = 0x53424F54
CMD_OTA_START, CMD_OTA_DATA, CMD_OTA_FINISH = 0x10, 0x11, 0x12
CMD_OTA_ABORT, CMD_OTA_STATUS, CMD_OTA_CONFIRM = 0x13, 0x16, 0x17
CMD_OTA_REBOOT = 0x18
RSP_OTA = 0x90
MSG_OTA_PROGRESS = 0x91
MSG_OTA_READY = 0x92
RSP_OTA_OK_START = 0x00
RSP_OTA_OK_FINISH = 0x01
RSP_OTA_ERR_BAD_OFFSET = 0x07
CHUNK_SIZE = 128
SLIDING_WINDOW = 4
CHUNK_ACK_TIMEOUT = 10.0
CHUNK_RETRIES = 10
RESP_TIMEOUT = 8.0
READY_TIMEOUT = 90.0  # wait for MSG_OTA_READY after START (background erase)


def build_frame(msg_id, payload):
    pl = payload if payload else b""
    return bytes([msg_id, len(pl) & 0xFF, len(pl) >> 8]) + pl


def _fw_crc32(data):
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            c = (0xEDB88320 ^ (c >> 1)) if (c & 1) else (c >> 1)
        table.append(c & 0xFFFFFFFF)
    crc = (~0) & 0xFFFFFFFF
    for b in data:
        crc = table[(crc ^ b) & 0xFF] ^ (crc >> 8)
        crc &= 0xFFFFFFFF
    return (~crc) & 0xFFFFFFFF


def _verify_crc_log():
    known = b"123456789"
    got = _fw_crc32(known)
    ok = got == 0xCBF43926
    if ok:
        print("CRC check: OK (test vector 0xCBF43926)")
        return True
    print(f"CRC check: WARN got 0x{got:08X} expected 0xCBF43926")
    return False


def make_ota_image(bin_data, version=1):
    header = struct.pack("<I", OTA_MAGIC) + struct.pack("<H", version)
    header += struct.pack("<I", len(bin_data))
    header += struct.pack("<I", _fw_crc32(bin_data))
    full = header + bin_data
    return full, _fw_crc32(full)


POST_CONNECT_DELAY = 1.5  # Allow BlueZ GATT discovery to complete
CONNECT_TIMEOUT = 600.0


def _ts():
    return time.strftime("%H:%M:%S", time.localtime())


class OtaBle:
    def __init__(self):
        self.last_msg = None
        self.msg_event = asyncio.Event()
        self.disconnected = False

    def _on_notify(self, sender, data):
        if len(data) < 1:
            return
        t = data[0]
        if t in (RSP_OTA, MSG_OTA_PROGRESS, MSG_OTA_READY):
            self.last_msg = bytes(data)
            self.msg_event.set()

    async def wait_msg(self, timeout=RESP_TIMEOUT):
        self.last_msg = None
        self.msg_event.clear()
        try:
            await asyncio.wait_for(self.msg_event.wait(), timeout)
            return self.last_msg
        except asyncio.TimeoutError:
            return None

    async def _safe_write(self, client, data):
        """Write with disconnect/error handling. Raises BleakError on failure."""
        if self.disconnected:
            raise BleakError("Device disconnected")
        await client.write_gatt_char(NUS_RX, data, response=False)

    async def run(self, image, size, crc_full, version, start_offset=0):
        """Run OTA; start_offset > 0 for resume."""
        self.disconnected = False
        for scan_attempt in range(3):
            print("Scanning for SmartBall..." + (f" (attempt {scan_attempt+1}/3)" if scan_attempt else ""))
            devices = await BleakScanner.discover(timeout=15.0)
            target = next((d for d in devices if "SmartBall" in (d.name or "")), None)
            if target:
                break
            if scan_attempt < 2:
                print("  Not found, retrying in 3s...")
                await asyncio.sleep(3.0)
        if not target:
            print("SmartBall not found")
            return (False, 0)

        def _disconnected_cb(client):
            self.disconnected = True
            print(f"[{_ts()}] DISCONNECTED (device dropped BLE link)")
            self.msg_event.set()

        print(f"[{_ts()}] Connecting to {target.address}...")
        # Pass BLEDevice object (not address) to avoid implicit discover
        # Retry connect - BLE can fail transiently (br-connection-canceled, etc.)
        last_err = None
        for connect_attempt in range(3):
            try:
                client = BleakClient(
                    target, timeout=CONNECT_TIMEOUT, disconnected_callback=_disconnected_cb
                )
                await client.connect()
                print(f"[{_ts()}] CONNECTED")
                break
            except BleakError as e:
                last_err = e
                if connect_attempt < 2:
                    print(f"  Connect failed ({e}), retrying in 2s...")
                    await asyncio.sleep(2.0)
                else:
                    print(f"Connect failed after 3 attempts: {last_err}")
                    return (False, 0)
        else:
            return (False, 0)

        try:
            # Force GATT discovery to complete (avoids BlueZ ServicesResolved race)
            _ = list(client.services)
            await asyncio.sleep(POST_CONNECT_DELAY)
            # Retry start_notify (Windows BLE can need extra time for GATT discovery)
            for attempt in range(5):
                try:
                    await client.start_notify(NUS_TX, self._on_notify)
                    break
                except BleakError as e:
                    if "not found" in str(e).lower() and attempt < 4:
                        await asyncio.sleep(0.5)
                        continue
                    raise
            await asyncio.sleep(0.3)

            if start_offset == 0:
                try:
                    await self._safe_write(client, build_frame(CMD_OTA_ABORT, b""))
                except BleakError as e:
                    print(f"Connection lost (ABORT): {e}")
                    return (False, 0)
                await asyncio.sleep(0.3)

                payload = struct.pack("<BHI", 1, version, size) + struct.pack("<I", crc_full)
                try:
                    await self._safe_write(client, build_frame(CMD_OTA_START, payload))
                    print(f"[{_ts()}] OTA_START sent, waiting for READY...")
                except BleakError as e:
                    print(f"Connection lost (START): {e}")
                    return (False, 0)
                deadline = asyncio.get_event_loop().time() + READY_TIMEOUT
                ready = False
                # Wait for MSG_OTA_READY - device sends MSG_OTA_PROGRESS during chunked erase
                while asyncio.get_event_loop().time() < deadline and not self.disconnected:
                    msg = await self.wait_msg(timeout=2.0)
                    if msg and len(msg) >= 1:
                        if msg[0] == RSP_OTA and len(msg) >= 4 and msg[3] == RSP_OTA_OK_START:
                            print("OTA_START ack (immediate)")
                        if msg[0] == MSG_OTA_PROGRESS and len(msg) >= 8:
                            off = struct.unpack_from("<I", msg, 3)[0]
                            if off % (64 * 1024) < 4096:
                                print(f"  Erase progress {off}/{size}")
                        if msg[0] == MSG_OTA_READY:
                            print(f"[{_ts()}] MSG_OTA_READY (device ready for data)")
                            ready = True
                            break
                        if msg[0] == RSP_OTA and len(msg) >= 4 and msg[3] == RSP_OTA_OK_START:
                            pass
                        if msg[0] == RSP_OTA and len(msg) >= 4 and msg[3] != RSP_OTA_OK_START:
                            print(f"  OTA_START error: {msg[3]}")
                            break
                    await asyncio.sleep(0.1)
                if not ready:
                    for _ in range(20):
                        msg = await self.wait_msg(timeout=1.0)
                        if msg and len(msg) >= 1 and msg[0] == MSG_OTA_READY:
                            ready = True
                            break
                if self.disconnected:
                    print(f"[{_ts()}] Device disconnected during READY wait; will resume.")
                    return (False, 0)
                if not ready:
                    print("Did not receive MSG_OTA_READY; proceeding anyway (legacy device).")
                # Stabilization delay before first OTA_DATA (per OTA_BLE_Stability_Report)
                await asyncio.sleep(1.0)

            last_acked_offset = start_offset
            offset = start_offset
            while offset < size:
                window_limit = last_acked_offset + SLIDING_WINDOW * CHUNK_SIZE
                if offset >= window_limit:
                    msg = await self.wait_msg(timeout=CHUNK_ACK_TIMEOUT)
                    if msg and len(msg) >= 8 and msg[0] == RSP_OTA:
                        paylen = msg[1] | (msg[2] << 8)
                        if paylen >= 8:
                            last_acked_offset = struct.unpack_from("<I", msg, 3)[0]
                    continue

                chunk = image[offset : offset + CHUNK_SIZE]
                chunk_crc = _fw_crc32(chunk)
                pl = struct.pack("<I", offset) + chunk + struct.pack("<I", chunk_crc)
                chunk_ok = False
                attempt = 0
                while attempt < CHUNK_RETRIES:
                    try:
                        await self._safe_write(client, build_frame(CMD_OTA_DATA, pl))
                    except (OSError, BleakError) as e:
                        print(f"\n[{_ts()}] Connection lost at {offset}/{size}: {e}")
                        return (False, offset)
                    msg = await self.wait_msg(timeout=CHUNK_ACK_TIMEOUT)
                    await asyncio.sleep(0.02)
                    if msg and len(msg) >= 1:
                        if msg[0] == MSG_OTA_PROGRESS or msg[0] == MSG_OTA_READY:
                            continue
                    if msg and len(msg) >= 4 and msg[0] == RSP_OTA:
                        paylen = msg[1] | (msg[2] << 8)
                        if paylen >= 1 and msg[3] == RSP_OTA_ERR_BAD_OFFSET and len(msg) >= 8:
                            resume = struct.unpack_from("<I", msg, 4)[0]
                            print(f"  BAD_OFFSET, resume from {resume}")
                            last_acked_offset = resume
                            offset = resume
                            chunk_ok = True
                            break
                        if paylen >= 8 and msg[0] == RSP_OTA:
                            next_off = struct.unpack_from("<I", msg, 3)[0]
                            if next_off == offset + len(chunk):
                                last_acked_offset = next_off
                                chunk_ok = True
                                break
                    if not chunk_ok:
                        attempt += 1
                    await asyncio.sleep(0.1)
                if not chunk_ok:
                    print(f"\n  Chunk at {offset} failed after {CHUNK_RETRIES} retries")
                    return (False, offset)
                offset += len(chunk)
                if offset % (CHUNK_SIZE * 50) == 0 or offset == size:
                    print(f"  {offset}/{size}")

            await asyncio.sleep(0.3)
            try:
                await self._safe_write(client, build_frame(CMD_OTA_FINISH, b""))
            except (OSError, BleakError) as e:
                print(f"[{_ts()}] Connection lost at OTA_FINISH: {e}")
                return (False, offset)
            msg = await self.wait_msg(timeout=10.0)
            if msg and len(msg) >= 4:
                paylen = msg[1] | (msg[2] << 8)
                if paylen >= 1 and msg[3] == RSP_OTA_OK_FINISH:
                    try:
                        await client.stop_notify(NUS_TX)
                    except BleakError:
                        pass
                    print("OTA complete. Device rebooting.")
                    return (True, offset)
            print("OTA_FINISH failed or timeout")
            try:
                await self._safe_write(client, build_frame(CMD_OTA_ABORT, b""))
            except BleakError:
                pass
            try:
                await client.stop_notify(NUS_TX)
            except BleakError:
                pass
            return (False, offset)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def get_status(self):
        """Connect, get OTA status (next_expected_offset), disconnect. Returns (next_offset, total_size) or (None, None)."""
        devices = await BleakScanner.discover(timeout=12.0)
        target = next((d for d in devices if "SmartBall" in (d.name or "")), None)
        if not target:
            return (None, None)
        try:
            async with BleakClient(target, timeout=15.0) as client:
                _ = list(client.services)
                await asyncio.sleep(POST_CONNECT_DELAY)
                await client.start_notify(NUS_TX, self._on_notify)
                await asyncio.sleep(0.2)
                await client.write_gatt_char(NUS_RX, build_frame(CMD_OTA_STATUS, b""), response=False)
                msg = await self.wait_msg(timeout=5.0)
                try:
                    await client.stop_notify(NUS_TX)
                except BleakError:
                    pass
                if msg and len(msg) >= 27 and msg[0] == RSP_OTA:
                    next_off = struct.unpack_from("<I", msg, 4)[0]
                    total = struct.unpack_from("<I", msg, 12)[0]
                    return (next_off, total)
                if msg and len(msg) >= 14 and msg[0] == RSP_OTA:
                    bytes_recv = struct.unpack_from("<I", msg, 4)[0]
                    total = struct.unpack_from("<I", msg, 8)[0]
                    return (bytes_recv, total)  # legacy: resume from bytes_received
        except Exception:
            pass
        return (None, None)


async def wait_for_device_online(wait_after_reboot_sec=10.0, scan_timeout=12.0, max_wait_sec=60.0):
    print(f"Waiting {wait_after_reboot_sec:.0f}s for device to reboot...")
    await asyncio.sleep(wait_after_reboot_sec)
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max_wait_sec
    while loop.time() < deadline:
        devices = await BleakScanner.discover(timeout=scan_timeout)
        target = next((d for d in devices if "SmartBall" in (d.name or "")), None)
        if target:
            print(f"Device online: {target.address} ({target.name})")
            return target.address
        print("  Scanning for SmartBall...")
    print("Device not seen after reboot (timeout).")
    return None


RESUME_ATTEMPTS = 5
RESUME_DELAY = 5.0


async def run_with_resume(image, size, crc_full, version):
    ota = OtaBle()
    start = 0
    attempts = 0
    while attempts < RESUME_ATTEMPTS:
        result, offset = await ota.run(image, size, crc_full, version, start_offset=start)
        if result:
            addr = await wait_for_device_online()
            return (True, addr)
        if offset == 0 and start == 0:
            print("OTA could not start (device not found or connection failed); retrying...")
        else:
            print(f"OTA interrupted at {offset}/{size}; checking for resume...")
        await asyncio.sleep(RESUME_DELAY)
        next_off, total = await ota.get_status()
        if next_off is not None and total == size and next_off < size:
            print(f"Resuming from offset {next_off}")
            start = next_off
            attempts += 1
            continue
        if next_off is not None and next_off >= size:
            print("Device reports transfer complete; waiting for reboot...")
            addr = await wait_for_device_online()
            return (True, addr)
        print("Could not get OTA status; retrying from start...")
        start = 0
        attempts += 1
    return (False, None)


async def main():
    if len(sys.argv) < 2:
        print("Usage: python ota_ble.py <firmware.bin> [version]")
        sys.exit(1)
    path = sys.argv[1]
    version = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    with open(path, "rb") as f:
        bin_data = f.read()

    if not _verify_crc_log():
        print("CRC self-check failed; continuing anyway.")
    image, crc_full = make_ota_image(bin_data, version)
    size = len(image)
    print(f"Image: {size} bytes, full CRC32=0x{crc_full:08X}, version={version}, chunk={CHUNK_SIZE}B, window={SLIDING_WINDOW}")

    ok, addr = await run_with_resume(image, size, crc_full, version)
    sys.exit(0 if (ok and addr) else 1)


if __name__ == "__main__":
    asyncio.run(main())
