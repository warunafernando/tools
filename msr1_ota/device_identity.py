#!/usr/bin/env python3
"""
Query SmartBall device identity (serial + part number) via SMP.
Uses custom mcumgr group 65, command 0.
"""
import asyncio
import cbor2
import struct
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
VENV = TOOLS / ".venv" / "bin"
sys.path.insert(0, str(VENV.parent / "lib" / "python3.11" / "site-packages"))

# SMP header: 1 op, 1 flags, 2 length, 1 group, 1 seq, 2 command
SMP_HEADER_FMT = "!BBHBBH"
SMP_HEADER_SIZE = 8
MGMT_OP_READ = 0
GROUP_DEVICE = 65
CMD_IDENTITY = 0


def build_smp_read_req():
    payload = cbor2.dumps({}, canonical=True)
    length = len(payload)
    hdr = struct.pack(
        SMP_HEADER_FMT,
        MGMT_OP_READ,
        0,  # flags
        length,
        GROUP_DEVICE,
        0,  # seq
        CMD_IDENTITY,
    )
    return hdr + payload


def parse_response(data: bytes) -> dict | None:
    if len(data) < SMP_HEADER_SIZE:
        return None
    payload = data[SMP_HEADER_SIZE:]
    try:
        m = cbor2.loads(payload)
        if isinstance(m, dict) and "rc" in m:
            return {
                "serial": m.get("serial"),
                "part": m.get("part"),
                "rc": m.get("rc"),
            }
    except Exception:
        pass
    return None


async def query_serial(port: str, timeout: float = 8.0) -> dict | None:
    """Query device identity over serial. Returns {serial, part} or None."""
    try:
        from smpclient.transport.serial import SMPSerialTransport

        transport = SMPSerialTransport()
        await transport.connect(port, timeout)
        try:
            req = build_smp_read_req()
            resp = await transport.send_and_receive(req)
            return parse_response(resp)
        finally:
            await transport.disconnect()
    except Exception:
        return None


async def query_ble(addr: str, timeout: float = 12.0) -> dict | None:
    """Query device identity over BLE. Returns {serial, part} or None."""
    try:
        from smpclient.transport.ble import SMPBLETransport

        transport = SMPBLETransport()
        await transport.connect(addr, timeout)
        try:
            req = build_smp_read_req()
            resp = await transport.send_and_receive(req)
            return parse_response(resp)
        finally:
            await transport.disconnect()
    except Exception:
        return None


def main():
    if len(sys.argv) < 3:
        print("Usage: device_identity.py serial /dev/ttyACM0")
        print("       device_identity.py ble AA:BB:CC:DD:EE:FF")
        sys.exit(1)
    transport, target = sys.argv[1].lower(), sys.argv[2]
    if transport == "serial":
        result = asyncio.run(query_serial(target))
    elif transport == "ble":
        result = asyncio.run(query_ble(target))
    else:
        print("Transport must be serial or ble")
        sys.exit(1)
    if result and result.get("rc") == 0:
        print(f"SERIAL={result.get('serial', '')}")
        print(f"PART={result.get('part', '')}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
