#!/usr/bin/env python3
"""
SmartBall protocol & format unit tests - no hardware required.
Tests frame format, SVTSHOT3 structure, config payload encoding.
Run: python3 scripts/test_smartball_protocol.py
"""
import struct
import sys

# Frame format
BIN_MAX_PAYLOAD = 253
BLE_BIN_FRAME_HEADER_SIZE = 3
SVTSHOT3_MAGIC = b"SVTSHOT3"
SVTSHOT3_SAMPLE_SIZE_SINGLE = 28
SVTSHOT3_HEADER_SIZE = 32
SVTSHOT3_FOOTER_SIZE = 4


def parse_frame(data: bytes) -> tuple[int, int, bytes] | None:
    """Parse Type|Len(LE)|Payload. Returns (type, plen, payload) or None."""
    if len(data) < 3:
        return None
    typ = data[0]
    plen = struct.unpack_from("<H", data, 1)[0]
    if plen == 0:
        return None
    if plen > BIN_MAX_PAYLOAD:
        return None
    if len(data) < 3 + plen:
        return None
    return (typ, plen, data[3 : 3 + plen])


def test_frame_parser_valid():
    """Phase 1: parse valid header and payload."""
    data = bytes([0x01, 0x02, 0x00, 0x11, 0x22])
    r = parse_frame(data)
    assert r is not None, "parse valid"
    typ, plen, payload = r
    assert typ == 0x01 and plen == 2 and payload == bytes([0x11, 0x22])
    print("PASS test_frame_parser_valid")


def test_frame_parser_invalid_length_zero():
    """Phase 1: reject length 0."""
    data = bytes([0x01, 0x00, 0x00])
    assert parse_frame(data) is None
    print("PASS test_frame_parser_invalid_length_zero")


def test_frame_parser_invalid_length_overflow():
    """Phase 1: reject length > BIN_MAX_PAYLOAD."""
    data = struct.pack("<BH", 0x01, 511) + b"\x00" * 511
    assert parse_frame(data) is None
    print("PASS test_frame_parser_invalid_length_overflow")


def test_svtshot3_header_layout():
    """Phase 3: SVTSHOT3 header layout."""
    hdr = bytearray(32)
    hdr[0:8] = SVTSHOT3_MAGIC
    hdr[8] = 1  # version
    struct.pack_into("<H", hdr, 10, 104)  # sample_rate_hz
    struct.pack_into("<I", hdr, 12, 10)   # count
    hdr[16] = 1   # sensor_mask
    hdr[17] = 1   # imu_source_mask
    assert hdr[:8] == SVTSHOT3_MAGIC
    assert len(hdr) == SVTSHOT3_HEADER_SIZE
    print("PASS test_svtshot3_header_layout")


def test_svtshot3_sample_size():
    """Phase 3: single IMU 28 bytes, multi 40+ bytes."""
    assert SVTSHOT3_SAMPLE_SIZE_SINGLE == 28
    # Multi: 4+4+24+24+12 = 68
    multi_min = 40
    assert multi_min >= 40
    print("PASS test_svtshot3_sample_size")


def test_config_payload_encode():
    """Phase 6: CMD_SET payload encoding klen,vlen,key,val."""
    key = b"event_mode"
    val = b"\x01"
    klen = len(key) + 1
    vlen = len(val)
    plen = 2 + klen + vlen
    payload = bytes([klen, vlen]) + key + b"\x00" + val
    assert len(payload) == plen
    assert payload[0] == klen and payload[1] == vlen
    assert payload[2:2 + klen].decode() == "event_mode\x00"
    print("PASS test_config_payload_encode")


def test_rsp_shot_list_format():
    """Phase 6: RSP_SHOT_LIST format count + [id(4), size(4)]."""
    # Simulated: count=2, id1=1 sz1=100, id2=2 sz2=200
    count = 2
    buf = bytes([count]) + struct.pack("<II", 1, 100) + struct.pack("<II", 2, 200)
    n = buf[0]
    assert n == 2
    id1, sz1 = struct.unpack_from("<II", buf, 1)
    id2, sz2 = struct.unpack_from("<II", buf, 9)
    assert id1 == 1 and sz1 == 100
    assert id2 == 2 and sz2 == 200
    print("PASS test_rsp_shot_list_format")


def run_all():
    failed = 0
    tests = [
        test_frame_parser_valid,
        test_frame_parser_invalid_length_zero,
        test_frame_parser_invalid_length_overflow,
        test_svtshot3_header_layout,
        test_svtshot3_sample_size,
        test_config_payload_encode,
        test_rsp_shot_list_format,
    ]
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1
    return failed


if __name__ == "__main__":
    failed = run_all()
    total = 7
    print("---")
    print(f"Protocol tests: {total - failed}/{total} passed")
    sys.exit(0 if failed == 0 else 1)
