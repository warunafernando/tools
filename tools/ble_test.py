#!/usr/bin/env python3
"""
SmartBall BLE Protocol v2 Test Script
Connect to SmartBall via NUS and send CMD_GET_ID, CMD_GET_STATUS
Requires: pip install bleak
"""

import asyncio
import struct
import sys

try:
    from bleak import BleakClient
except ImportError:
    print("Install bleak: pip install bleak")
    sys.exit(1)

# NUS UUIDs
NUS_SERVICE = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # Notify - we receive
NUS_RX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # Write - we send

# Message IDs
CMD_GET_ID = 0x80
CMD_GET_STATUS = 0x85
RSP_ID = 0x81
RSP_STATUS = 0x86


def build_frame(msg_id: int, payload: bytes = b"") -> bytes:
    """Build frame: Type(1) + Length(2 LE) + Payload"""
    length = len(payload)
    return bytes([msg_id, length & 0xFF, length >> 8]) + payload


def parse_frame(data: bytes):
    """Parse frame, return (type, payload) or None"""
    if len(data) < 3:
        return None
    msg_type = data[0]
    length = data[1] | (data[2] << 8)
    if len(data) < 3 + length:
        return None
    payload = data[3 : 3 + length]
    return (msg_type, payload)


def parse_rsp_id(payload: bytes):
    """Parse RSP_ID payload"""
    if len(payload) < 4:
        return None
    fw_ver = struct.unpack_from("<H", payload, 0)[0]
    proto_ver = payload[2]
    hw_rev = payload[3]
    uid_len = payload[4] if len(payload) > 4 else 0
    uid = payload[5 : 5 + uid_len].hex() if uid_len else ""
    return {"fw_version": fw_ver, "protocol": proto_ver, "hw_revision": hw_rev, "uid": uid}


def parse_rsp_status(payload: bytes):
    """Parse RSP_STATUS payload (48 bytes)"""
    if len(payload) < 34:
        return None
    d = struct.unpack_from(
        "<IBBBBBBIHHIIhHbH",
        payload,
        0,
    )
    return {
        "uptime_ms": d[0],
        "last_error": d[1],
        "error_flags": d[2],
        "device_state": d[3],
        "imu_source": d[4],
        "samples_recorded": d[7],
        "gyro_saturation": d[8],
        "storage_used": d[10],
        "storage_free": d[11],
    }


async def main():
    # Scan for SmartBall
    from bleak import BleakScanner

    print("Scanning for SmartBall...")
    devices = await BleakScanner.discover(timeout=8.0)
    target = None
    for d in devices:
        if "SmartBall" in (d.name or ""):
            target = d
            break

    # Fallback: try unnamed devices - XIAO may advertise without name in some configs
    if not target:
        unnamed = [d for d in devices if not (d.name or "").strip()][:5]
        print(f"SmartBall not found by name. Checking {len(unnamed)} unnamed device(s)...")
        for d in unnamed:
            try:
                async with BleakClient(d.address, timeout=2.0) as client:
                    for s in client.services:
                        if s.uuid and NUS_SERVICE.lower() in str(s.uuid).lower():
                            target = d
                            print(f"Found NUS service on {d.address}")
                            break
                    if target:
                        break
            except Exception:
                pass

    if not target:
        print("SmartBall not found.")
        print("Nearby devices:")
        for d in devices[:12]:
            print(f"  - {d.name or '(no name)'} {d.address}")
        return

    print(f"Connecting to {target.name or target.address} @ {target.address}")

    responses = []

    def notification_handler(characteristic, data):
        responses.append(data)

    async with BleakClient(target.address) as client:
        await client.start_notify(NUS_TX, notification_handler)

        # Request ID
        responses.clear()
        await client.write_gatt_char(NUS_RX, build_frame(CMD_GET_ID), response=True)
        await asyncio.sleep(0.5)
        for r in responses:
            parsed = parse_frame(r)
            if parsed and parsed[0] == RSP_ID:
                info = parse_rsp_id(parsed[1])
                if info:
                    print(f"\nRSP_ID: fw={info['fw_version']} proto={info['protocol']} hw={info['hw_revision']} uid=0x{info['uid']}")

        # Request Status
        responses.clear()
        await client.write_gatt_char(NUS_RX, build_frame(CMD_GET_STATUS), response=True)
        await asyncio.sleep(0.5)
        for r in responses:
            parsed = parse_frame(r)
            if parsed and parsed[0] == RSP_STATUS:
                info = parse_rsp_status(parsed[1])
                if info:
                    print(f"RSP_STATUS: uptime={info['uptime_ms']}ms state={info['device_state']} samples={info['samples_recorded']}")

        await client.stop_notify(NUS_TX)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
