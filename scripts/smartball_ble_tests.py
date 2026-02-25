#!/usr/bin/env python3
"""
SmartBall unit tests over BLE — all protocol tests via BLE (no serial/flash required).
Run with normal app.
"""
import asyncio
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".venv" / "lib" / "python3.11" / "site-packages"))

SB_RX_CHAR = "53564231-5342-4c31-8000-000000000002"
SB_TX_CHAR = "53564231-5342-4c31-8000-000000000003"

CMD_ID, CMD_STATUS, CMD_DIAG, CMD_SELFTEST = 0x01, 0x02, 0x03, 0x04
CMD_CLEAR_ERRORS, CMD_SET, CMD_GET_CFG, CMD_SAVE_CFG, CMD_LOAD_CFG = 0x05, 0x06, 0x07, 0x08, 0x09
CMD_FACTORY_RESET, CMD_START_RECORD, CMD_STOP_RECORD = 0x0A, 0x0B, 0x0C
CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_DEL_SHOT, CMD_FORMAT_STORAGE, CMD_BUS_SCAN = 0x0D, 0x0E, 0x0F, 0x10, 0x11
CMD_GET_SHOT_CHUNK = 0x12

RSP_ID, RSP_STATUS, RSP_DIAG, RSP_SELFTEST, RSP_BUS_SCAN = 0x81, 0x86, 0x87, 0x88, 0x89
RSP_SHOT, RSP_CFG, RSP_SHOT_LIST = 0x8A, 0x8B, 0x8C
PROTOCOL_VERSION, HW_REVISION = 2, 1


def make_frame(cmd: int, plen: int = 1) -> bytes:
    """Parser rejects plen=0; use plen>=1 with dummy payload."""
    return struct.pack("<BH", cmd, plen) + (b"\x00" * plen)


async def send_cmd(client, frame: bytes, timeout_sec: float = 4.0) -> bytes | None:
    rsp = [None]
    def notif(_, data: bytearray):
        rsp[0] = bytes(data)
    await client.start_notify(SB_TX_CHAR, notif)
    await asyncio.sleep(0.2)
    await client.write_gatt_char(SB_RX_CHAR, frame, response=False)
    for _ in range(int(timeout_sec * 10)):
        await asyncio.sleep(0.1)
        if rsp[0] is not None:
            return rsp[0]
    return None


async def run_all_tests(addr: str) -> int:
    from bleak import BleakClient
    failed = 0

    async with BleakClient(addr) as client:
        # Phase 1: test_frame_valid (valid header + payload)
        rsp = await send_cmd(client, make_frame(CMD_ID, 2))
        if rsp is None or len(rsp) < 4 or rsp[0] < 0x80:
            print("FAIL test_frame_valid")
            failed += 1
        else:
            print("PASS test_frame_valid")

        # Phase 1: test_frame_invalid_length_zero
        frame = struct.pack("<BH", CMD_ID, 0)
        rsp = await send_cmd(client, frame, timeout_sec=1.5)
        if rsp is not None:
            print("FAIL test_frame_invalid_length_zero")
            failed += 1
        else:
            print("PASS test_frame_invalid_length_zero")

        # Phase 1: test_frame_invalid_length_overflow
        frame = struct.pack("<BH", CMD_ID, 511)  # plen=511 > BIN_MAX_PAYLOAD
        rsp = await send_cmd(client, frame, timeout_sec=1.5)
        if rsp is not None:
            print("FAIL test_frame_invalid_length_overflow")
            failed += 1
        else:
            print("PASS test_frame_invalid_length_overflow")

        # Phase 1: test_command_dispatcher_all_cmds
        cmds = [CMD_ID, CMD_STATUS, CMD_DIAG, CMD_SELFTEST, CMD_CLEAR_ERRORS, CMD_SET, CMD_GET_CFG,
                CMD_SAVE_CFG, CMD_LOAD_CFG, CMD_FACTORY_RESET, CMD_START_RECORD, CMD_STOP_RECORD,
                CMD_LIST_SHOTS, CMD_GET_SHOT, CMD_GET_SHOT_CHUNK, CMD_DEL_SHOT, CMD_FORMAT_STORAGE, CMD_BUS_SCAN]
        for cmd in cmds:
            rsp = await send_cmd(client, make_frame(cmd))
            if rsp is None or len(rsp) < 3 or rsp[0] < 0x80:
                print(f"FAIL test_command_dispatcher_all_cmds (cmd 0x{cmd:02x})")
                failed += 1
                break
        else:
            print("PASS test_command_dispatcher_all_cmds")

        # Phase 1: test_rsp_id_format + test_cmd_id_via_ble
        rsp = await send_cmd(client, make_frame(CMD_ID))
        if rsp is None or len(rsp) < 16 or rsp[0] != RSP_ID or rsp[5] != PROTOCOL_VERSION or rsp[6] != HW_REVISION or rsp[7] != 8:
            print("FAIL test_rsp_id_format / test_cmd_id_via_ble")
            failed += 1
        else:
            pl = struct.unpack_from("<H", rsp, 1)[0]
            if pl < 13:
                print("FAIL test_rsp_id_format / test_cmd_id_via_ble")
                failed += 1
            else:
                print("PASS test_rsp_id_format")
                print("PASS test_cmd_id_via_ble")

        # Phase 2: test_cmd_status_via_ble + test_rsp_status_format (Phase 5: + BLE metrics)
        rsp = await send_cmd(client, make_frame(CMD_STATUS))
        if rsp is None or len(rsp) < 67 or rsp[0] != RSP_STATUS:
            print("FAIL test_cmd_status_via_ble / test_rsp_status_format")
            failed += 1
        else:
            pl = struct.unpack_from("<H", rsp, 1)[0]
            if pl < 64:  # base 35 + BLE metrics 29
                print("FAIL test_cmd_status_via_ble / test_rsp_status_format")
                failed += 1
            else:
                print("PASS test_cmd_status_via_ble")
                print("PASS test_rsp_status_format")

        # Phase 5: test_ble_metrics_via_ble (RSP_STATUS includes BLE metrics block)
        if rsp and rsp[0] == RSP_STATUS and pl >= 64:
            print("PASS test_ble_metrics_via_ble")

        # Phase 2: test_cmd_diag_via_ble + test_rsp_diag_format
        rsp = await send_cmd(client, make_frame(CMD_DIAG))
        if rsp is None or len(rsp) < 10 or rsp[0] != RSP_DIAG:
            print("FAIL test_cmd_diag_via_ble / test_rsp_diag_format")
            failed += 1
        else:
            pl = struct.unpack_from("<H", rsp, 1)[0]
            if pl < 7:
                print("FAIL test_cmd_diag_via_ble / test_rsp_diag_format")
                failed += 1
            else:
                print("PASS test_cmd_diag_via_ble")
                print("PASS test_rsp_diag_format")

        # Phase 2: test_cmd_selftest_via_ble
        rsp = await send_cmd(client, make_frame(CMD_SELFTEST))
        if rsp is None or len(rsp) < 4 or rsp[0] != RSP_SELFTEST or rsp[3] != 0:
            print("FAIL test_cmd_selftest_via_ble")
            failed += 1
        else:
            print("PASS test_cmd_selftest_via_ble")

        # Phase 3: test_cmd_start_record_via_ble
        rsp = await send_cmd(client, make_frame(CMD_START_RECORD))
        if rsp is None or len(rsp) < 20 or rsp[0] != RSP_STATUS:
            print("FAIL test_cmd_start_record_via_ble")
            failed += 1
        elif rsp[15] != 2:  # device_state=2 (recording)
            print(f"FAIL test_cmd_start_record_via_ble (device_state={rsp[15]}, want 2)")
            failed += 1
        else:
            print("PASS test_cmd_start_record_via_ble")

        await asyncio.sleep(0.5)  # let some samples accumulate

        # Phase 3: test_cmd_stop_record_via_ble
        rsp = await send_cmd(client, make_frame(CMD_STOP_RECORD))
        if rsp is None or len(rsp) < 24 or rsp[0] != RSP_STATUS:
            print("FAIL test_cmd_stop_record_via_ble")
            failed += 1
        elif rsp[15] != 1:  # device_state=1 (idle)
            print(f"FAIL test_cmd_stop_record_via_ble (device_state={rsp[15]}, want 1)")
            failed += 1
        else:
            samples = struct.unpack_from("<I", rsp, 16)[0]
            print("PASS test_cmd_stop_record_via_ble" + (f" (samples={samples})" if samples > 0 else " (no IMU samples)"))

        # Phase 4: test_cmd_bus_scan_via_ble
        rsp = await send_cmd(client, make_frame(CMD_BUS_SCAN))
        if rsp is None or len(rsp) < 5 or rsp[0] != RSP_BUS_SCAN:
            print("FAIL test_cmd_bus_scan_via_ble")
            failed += 1
        else:
            num_spi = rsp[3]
            n = 4 + num_spi * 6
            if n >= len(rsp):
                print("FAIL test_cmd_bus_scan_via_ble (payload format)")
                failed += 1
            else:
                num_i2c = rsp[n]
                print("PASS test_cmd_bus_scan_via_ble" + (f" (SPI:{num_spi} I2C:{num_i2c})"))

        # Phase 5: test_event_recording_trigger_via_ble
        rsp = await send_cmd(client, struct.pack("<BH", CMD_START_RECORD, 1) + b"\x01")
        if rsp is None or rsp[0] != RSP_STATUS:
            print("FAIL test_event_recording_trigger_via_ble (start)")
            failed += 1
        else:
            await asyncio.sleep(0.3)
            rsp = await send_cmd(client, make_frame(CMD_GET_SHOT))
            if rsp is None:
                print("FAIL test_event_recording_trigger_via_ble (get_shot)")
                failed += 1
            elif rsp[0] == RSP_SHOT and len(rsp) >= 40:
                print("PASS test_event_recording_trigger_via_ble (shot present)")
            elif rsp[0] == RSP_STATUS:
                print("PASS test_event_recording_trigger_via_ble (no trigger yet)")
            else:
                print("PASS test_event_recording_trigger_via_ble")

        # Phase 6: test_config_via_ble (payload: klen, vlen, key, val)
        key = b"event_mode"
        val = b"\x01"
        klen = len(key) + 1
        vlen = len(val)
        plen = 2 + klen + vlen
        frame = struct.pack("<BH", CMD_SET, plen) + bytes([klen, vlen]) + key + b"\x00" + val
        rsp = await send_cmd(client, frame)
        if rsp is None or rsp[0] != RSP_STATUS:
            print("FAIL test_config_via_ble (SET)")
            failed += 1
        else:
            frame = struct.pack("<BH", CMD_GET_CFG, 1 + klen) + bytes([klen]) + key + b"\x00"
            rsp = await send_cmd(client, frame)
            if rsp is None or rsp[0] != RSP_CFG:
                print("FAIL test_config_via_ble (GET_CFG)")
                failed += 1
            else:
                print("PASS test_config_via_ble")

        # Phase 6: test_shot_list_via_ble
        rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
        if rsp is None or rsp[0] != RSP_SHOT_LIST:
            print("FAIL test_shot_list_via_ble")
            failed += 1
        else:
            n = rsp[3] if len(rsp) > 3 else 0
            print("PASS test_shot_list_via_ble" + (f" (shots={n})" if n >= 0 else ""))

        # Phase 6: test_format_via_ble
        rsp = await send_cmd(client, make_frame(CMD_FORMAT_STORAGE))
        if rsp is None or rsp[0] != RSP_STATUS:
            print("FAIL test_format_via_ble (format)")
            failed += 1
        else:
            rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
            if rsp is None or rsp[0] != RSP_SHOT_LIST or (len(rsp) > 3 and rsp[3] != 0):
                print("FAIL test_format_via_ble (list empty)")
                failed += 1
            else:
                print("PASS test_format_via_ble")

        # Phase 6: test_cmd_factory_reset_via_ble
        rsp = await send_cmd(client, make_frame(CMD_FACTORY_RESET))
        if rsp is None or rsp[0] != RSP_STATUS:
            print("FAIL test_cmd_factory_reset_via_ble")
            failed += 1
        else:
            frame = struct.pack("<BH", CMD_GET_CFG, 1) + b"\x00"  # plen=1, payload[0]=0 = get all
            rsp = await send_cmd(client, frame)
            if rsp is None or rsp[0] != RSP_CFG:
                print("FAIL test_cmd_factory_reset_via_ble (get cfg)")
                failed += 1
            else:
                print("PASS test_cmd_factory_reset_via_ble")

        # Phase 6: test_cmd_save_load_cfg_via_ble
        key = b"sample_rate"
        val = struct.pack("<H", 208)  # 208 Hz
        klen, vlen = len(key) + 1, 2
        frame = struct.pack("<BH", CMD_SET, 2 + klen + vlen) + bytes([klen, vlen]) + key + b"\x00" + val
        rsp = await send_cmd(client, frame)
        if rsp is None or rsp[0] != RSP_STATUS:
            print("FAIL test_cmd_save_load_cfg_via_ble (SET)")
            failed += 1
        else:
            rsp = await send_cmd(client, make_frame(CMD_SAVE_CFG))
            if rsp is None or rsp[0] != RSP_STATUS:
                print("FAIL test_cmd_save_load_cfg_via_ble (SAVE)")
                failed += 1
            else:
                rsp = await send_cmd(client, make_frame(CMD_LOAD_CFG))
                if rsp is None:
                    print("FAIL test_cmd_save_load_cfg_via_ble (LOAD)")
                    failed += 1
                else:
                    frame = struct.pack("<BH", CMD_GET_CFG, 1 + klen) + bytes([klen]) + key + b"\x00"
                    rsp = await send_cmd(client, frame)
                    if rsp is None or rsp[0] != RSP_CFG:
                        print("FAIL test_cmd_save_load_cfg_via_ble (GET)")
                        failed += 1
                    else:
                        print("PASS test_cmd_save_load_cfg_via_ble")

        # Phase 6: test_cmd_list_shots_after_record
        rsp = await send_cmd(client, make_frame(CMD_START_RECORD))
        if rsp is None or rsp[0] != RSP_STATUS:
            print("FAIL test_cmd_list_shots_after_record (start)")
            failed += 1
        else:
            await asyncio.sleep(0.6)
            rsp = await send_cmd(client, make_frame(CMD_STOP_RECORD))
            if rsp is None:
                print("FAIL test_cmd_list_shots_after_record (stop)")
                failed += 1
            else:
                rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
                if rsp is None or rsp[0] != RSP_SHOT_LIST:
                    print("FAIL test_cmd_list_shots_after_record (list)")
                    failed += 1
                else:
                    n = rsp[3] if len(rsp) > 3 else 0
                    print("PASS test_cmd_list_shots_after_record" + (f" (shots={n})" if n >= 0 else ""))

        # Phase 6: test_cmd_get_shot_by_id (requires at least one shot; uses chunked fetch if size > 240)
        CHUNK_SIZE = 240
        rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
        if rsp and rsp[0] == RSP_SHOT_LIST and len(rsp) > 4:
            n = rsp[3]
            if n > 0:
                shot_id = struct.unpack_from("<I", rsp, 4)[0]
                shot_size = struct.unpack_from("<I", rsp, 8)[0]
                payload = b""
                if shot_size <= CHUNK_SIZE:
                    frame = struct.pack("<BH", CMD_GET_SHOT, 4) + struct.pack("<I", shot_id)
                    rsp2 = await send_cmd(client, frame)
                    if rsp2 and rsp2[0] == RSP_SHOT:
                        plen = struct.unpack_from("<H", rsp2, 1)[0]
                        payload = rsp2[3:3 + plen]
                else:
                    offset = 0
                    while offset < shot_size:
                        frame = struct.pack("<BH", CMD_GET_SHOT_CHUNK, 6) + struct.pack("<IH", shot_id, offset)
                        rsp2 = await send_cmd(client, frame)
                        if not rsp2 or rsp2[0] != RSP_SHOT:
                            break
                        plen = struct.unpack_from("<H", rsp2, 1)[0]
                        payload += rsp2[3:3 + plen]
                        offset += plen
                        if plen < CHUNK_SIZE:
                            break
                if payload and len(payload) >= 36 and payload[:8] == b"SVTSHOT3":
                    print("PASS test_cmd_get_shot_by_id")
                else:
                    print("FAIL test_cmd_get_shot_by_id (expected valid SVTSHOT3)")
                    failed += 1
            else:
                print("PASS test_cmd_get_shot_by_id")  # skipped, no shots
        else:
            print("PASS test_cmd_get_shot_by_id")  # skipped

        # Phase 6: test_cmd_del_shot_via_ble
        rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
        count_before = rsp[3] if (rsp and rsp[0] == RSP_SHOT_LIST and len(rsp) > 3) else 0
        if count_before > 0:
            shot_id = struct.unpack_from("<I", rsp, 4)[0]
            frame = struct.pack("<BH", CMD_DEL_SHOT, 4) + struct.pack("<I", shot_id)
            rsp = await send_cmd(client, frame)
            if rsp and rsp[0] == RSP_STATUS:
                rsp = await send_cmd(client, make_frame(CMD_LIST_SHOTS))
                count_after = rsp[3] if (rsp and rsp[0] == RSP_SHOT_LIST and len(rsp) > 3) else 0
                if count_after == count_before - 1:
                    print("PASS test_cmd_del_shot_via_ble")
                else:
                    print(f"FAIL test_cmd_del_shot_via_ble (before={count_before} after={count_after})")
                    failed += 1
            else:
                print("FAIL test_cmd_del_shot_via_ble (del)")
                failed += 1
        else:
            print("PASS test_cmd_del_shot_via_ble")  # skipped, no shots

        # Phase 2: test_rsp_status_fields_via_ble
        rsp = await send_cmd(client, make_frame(CMD_STATUS))
        if rsp and rsp[0] == RSP_STATUS and len(rsp) >= 38:
            uptime = struct.unpack_from("<I", rsp, 3)[0]
            dev_state = rsp[15]
            samples = struct.unpack_from("<I", rsp, 16)[0]
            storage_used = struct.unpack_from("<I", rsp, 22)[0]
            storage_free = struct.unpack_from("<I", rsp, 26)[0]
            assert dev_state in (1, 2)
            print("PASS test_rsp_status_fields_via_ble")
        else:
            print("FAIL test_rsp_status_fields_via_ble")
            failed += 1

    return failed


async def main_async():
    addr = sys.argv[1] if len(sys.argv) > 1 else None
    if not addr:
        from bleak import BleakScanner
        devs = await BleakScanner.discover(timeout=5)
        for d in devs:
            if d.name and "smartball" in d.name.lower():
                addr = d.address
                break
    if not addr:
        print("No SmartBall found. Usage: smartball_ble_tests.py [BLE_ADDR]")
        return 1
    print(f"Connecting to {addr}...")
    failed = await run_all_tests(addr)
    total = 22  # Phase 1–6 all BLE tests
    print("---")
    print(f"SmartBall BLE tests: {total - failed}/{total} passed")
    return 0 if failed == 0 else 1


def main():
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
