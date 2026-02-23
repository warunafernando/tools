#!/usr/bin/env python3
"""Send CMD_SELFTEST to SmartBall via BLE binary protocol and print result."""
import asyncio
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".venv" / "lib" / "python3.11" / "site-packages"))

# SmartBall Binary Service
SB_BINARY_SVC = "53564231-5342-4c31-8000-000000000001"
SB_RX_CHAR = "53564231-5342-4c31-8000-000000000002"
SB_TX_CHAR = "53564231-5342-4c31-8000-000000000003"
CMD_SELFTEST = 0x04
RSP_SELFTEST = 0x88


async def run_selftest(addr: str):
    from bleak import BleakClient
    result = struct.pack("<BHB", CMD_SELFTEST, 1, 0)  # plen=1 (parser rejects 0)
    rsp = [None]
    def notif(_, data: bytearray):
        rsp[0] = bytes(data)  # accept any response
    async with BleakClient(addr) as client:
        await client.start_notify(SB_TX_CHAR, notif)
        await asyncio.sleep(0.3)
        await client.write_gatt_char(SB_RX_CHAR, result, response=False)
        for _ in range(50):
            await asyncio.sleep(0.1)
            if rsp[0] is not None:
                break
    if rsp[0] is not None and len(rsp[0]) >= 4:
        if rsp[0][0] == RSP_SELFTEST:
            code = rsp[0][3]
            return code  # 0=pass, bit0=IMU, bit1=RAM, bit2=BLE
        # else got other response (ID, STATUS, etc.)
    return -1  # no response


async def main():
    addr = sys.argv[1] if len(sys.argv) > 1 else None
    if not addr:
        from bleak import BleakScanner
        devs = await BleakScanner.discover(timeout=5)
        for d in devs:
            if d.name and "smartball" in d.name.lower():
                addr = d.address
                break
    if not addr:
        print("No SmartBall found. Usage: smartball_selftest.py [BLE_ADDR]")
        sys.exit(1)
    print(f"Connecting to {addr}...")
    code = await run_selftest(addr)
    if code == 0:
        print("SELFTEST PASSED")
    elif code < 0:
        print("SELFTEST: no response (BLE indication issue)")
    else:
        fails = []
        if code & 1: fails.append("IMU")
        if code & 2: fails.append("RAM")
        if code & 4: fails.append("BLE")
        print(f"SELFTEST FAILED: {','.join(fails) or 'code=' + str(code)}")
    sys.exit(0 if code == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
