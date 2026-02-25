"""
Test shot chunked fetch logic (segment-based, resume). No real BLE device required.
Run from msr1_ota/web_gui: python test_shot_fetch.py
"""
import asyncio
import struct
import sys
from pathlib import Path

# Run from web_gui so ble_binary_client is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Build fake payload: SVTSHOT3 header + minimal data
def make_fake_shot_payload(num_samples: int = 10, sample_size: int = 28) -> bytes:
    header = (
        b"SVTSHOT3"
        + b"\x01\x00"
        + struct.pack("<H", 100)
        + struct.pack("<I", num_samples)
        + bytes([0, 0, 0, 0, 0, 0])
    )
    body = b""
    for i in range(num_samples):
        body += struct.pack("<I", i * 10)
        body += (b"\x00" * (sample_size - 4))
    footer = b"\x00\x00\x00\x00"
    return header + body + footer


async def test_segment_fetch():
    from unittest.mock import AsyncMock, MagicMock, patch
    from ble_binary_client import (
        fetch_shot_chunked_async,
        FETCH_SHOT_CHUNK_SIZE,
        CHUNKS_PER_CONNECTION,
        RSP_SHOT,
        CMD_GET_SHOT_CHUNK,
    )
    CHUNK = FETCH_SHOT_CHUNK_SIZE
    # Use enough data to require multiple connections (CHUNKS_PER_CONNECTION = 1)
    full = make_fake_shot_payload(80, 28)
    size = len(full)
    shot_id = 1
    addr = "AA:BB:CC:DD:EE:FF"

    # Simulate device: for each (shot_id, offset) return the correct chunk
    def build_chunk_response(offset: int) -> bytes:
        chunk = full[offset : offset + CHUNK]
        plen = len(chunk)
        return struct.pack("<BH", RSP_SHOT, plen) + chunk

    conn_count = [0]
    chunk_requests = []

    class MockClient:
        def __init__(self, addr):
            self.addr = addr

        async def __aenter__(self):
            conn_count[0] += 1
            return self

        async def __aexit__(self, *a):
            return None

        async def start_notify(self, char, cb):
            pass

        async def stop_notify(self, char):
            pass

        async def write_gatt_char(self, char, data, response=False):
            pass

    async def mock_send_cmd(client, frame, timeout_sec=5.0):
        if len(frame) < 3:
            return None
        cmd = frame[0]
        if cmd != CMD_GET_SHOT_CHUNK:
            return None
        if len(frame) < 3 + 6:
            return None
        sid = struct.unpack_from("<I", frame, 3)[0]
        off = struct.unpack_from("<H", frame, 7)[0]
        chunk_requests.append((sid, off))
        return build_chunk_response(off)

    with patch("bleak.BleakClient", MockClient), patch(
        "ble_binary_client._send_cmd", side_effect=mock_send_cmd
    ), patch("asyncio.sleep", AsyncMock()):
        payload, err = await fetch_shot_chunked_async(addr, shot_id, size, chunk_size=CHUNK, timeout_per_chunk=2.0)
        assert err is None, err
        assert payload == full, f"payload len {len(payload)} vs full {len(full)}"
        assert payload[:8] == b"SVTSHOT3"

    # Should have used multiple connections (segments)
    assert conn_count[0] >= 2, f"expected multiple connections, got {conn_count[0]}"
    # Should have requested chunks in order
    for i, (sid, off) in enumerate(chunk_requests):
        expected_off = i * CHUNK
        assert off == expected_off, f"chunk {i}: offset {off} != {expected_off}"
    print("test_segment_fetch OK: multi-connection segment fetch and full payload verified.")


def run_tests():
    asyncio.run(test_segment_fetch())
    print("All tests passed.")


if __name__ == "__main__":
    run_tests()
