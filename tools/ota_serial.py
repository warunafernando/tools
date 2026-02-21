#!/usr/bin/env python3
"""
SmartBall OTA over Serial - dual image, CRC verify, retries
Image format: MAGIC(4) + VERSION(2) + SIZE(4) + CRC32(4) + payload
Requires: pip install pyserial
Usage: python ota_serial.py COM16 firmware.bin [version]
"""
import sys
import struct
import time

try:
    import serial
except ImportError:
    print("Install pyserial: pip install pyserial")
    sys.exit(1)

OTA_MAGIC = 0x53424F54  # SBOT
CMD_OTA_START, CMD_OTA_DATA, CMD_OTA_FINISH = 0x10, 0x11, 0x12
CMD_OTA_ABORT, CMD_OTA_STATUS, CMD_OTA_CONFIRM = 0x13, 0x16, 0x17
CHUNK_SIZE = 480
MAX_RETRIES = 3
# Inter-chunk delay: device needs time to read serial + write flash. At 115200 baud,
# ~491 bytes takes ~43ms to arrive. Too short causes RX overflow -> missing chunks.
CHUNK_DELAY_MS = 0.06  # 60ms between chunks to prevent serial buffer overflow


def build_frame(msg_id, payload):
    pl = payload if payload else b""
    return bytes([msg_id, len(pl) & 0xFF, len(pl) >> 8]) + pl


def _fw_crc32(data):
    """Match firmware CRC-32: init 0, ~ at start/end, poly 0xEDB88320."""
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
    """Log CRC check: verify against known vector."""
    known = b"123456789"
    got = _fw_crc32(known)
    if got == 0xCBF43926:
        print("CRC check: OK (test vector 0xCBF43926)")
        return True
    print(f"CRC check: WARN got 0x{got:08X} expected 0xCBF43926")
    return False


def make_ota_image(bin_data, version=1):
    """Prepend OTA header: MAGIC(4) + VERSION(2) + SIZE(4) + CRC32(4).
    CRC matches firmware algorithm."""
    payload_size = len(bin_data)
    header = struct.pack("<I", OTA_MAGIC) + struct.pack("<H", version)
    header += struct.pack("<I", payload_size)
    header += struct.pack("<I", _fw_crc32(bin_data))
    full = header + bin_data
    return full, _fw_crc32(full)


def main():
    if len(sys.argv) < 3:
        print("Usage: python ota_serial.py <COM> <firmware.bin> [version]")
        sys.exit(1)
    port, path = sys.argv[1], sys.argv[2]
    version = int(sys.argv[3]) if len(sys.argv) > 3 else 1

    with open(path, "rb") as f:
        bin_data = f.read()

    if not _verify_crc_log():
        print("CRC self-check failed; continuing anyway.")
    image, crc_full = make_ota_image(bin_data, version)
    size = len(image)
    print(f"Image: {size} bytes, full CRC32=0x{crc_full:08X}, version={version}")

    ser = serial.Serial(port, 115200, timeout=30)
    ser.reset_input_buffer()
    # If board resets on DTR (common for XIAO): wait for boot. Else use --no-reset and ABORT.
    print("Waiting for device to boot (4s)...")
    time.sleep(4)

    def send_cmd(cmd, payload, retries=MAX_RETRIES):
        frame = build_frame(cmd, payload)
        for _ in range(retries):
            ser.write(frame)
            ser.flush()
            r = ser.read(3)
            if len(r) >= 3:
                rlen = r[1] | (r[2] << 8)
                pay = ser.read(rlen) if rlen else b""
                return r[0], pay
            time.sleep(0.2)
        return None, b""

    send_cmd(CMD_OTA_ABORT, b"")
    time.sleep(0.6)
    send_cmd(CMD_OTA_ABORT, b"")
    time.sleep(0.6)

    # OTA_START: slot=1, version, size, crc32
    payload = struct.pack("<BHI", 1, version, size) + struct.pack("<I", crc_full)
    rc, _ = send_cmd(CMD_OTA_START, payload)
    if rc != 0x90 or (len(_) >= 1 and _[0] != 0):
        print("OTA_START failed:", _[:1] if _ else "no reply")
        ser.close()
        sys.exit(1)
    print("OTA_START ok")

    CHUNK_CRC_RETRIES = 3
    offset = 0
    while offset < size:
        chunk = image[offset : offset + CHUNK_SIZE]
        chunk_crc = _fw_crc32(chunk)
        payload = struct.pack("<I", offset) + chunk + struct.pack("<I", chunk_crc)
        for retry in range(CHUNK_CRC_RETRIES):
            rc, rpay = send_cmd(CMD_OTA_DATA, payload)
            time.sleep(CHUNK_DELAY_MS)
            if rc != 0x90:
                print("OTA_DATA no reply at offset", offset)
                if retry == CHUNK_CRC_RETRIES - 1:
                    send_cmd(CMD_OTA_ABORT, b"")
                    sys.exit(1)
                continue
            if rpay and len(rpay) >= 1 and rpay[0] == 0x05:
                if retry < CHUNK_CRC_RETRIES - 1:
                    continue
                print("OTA_DATA chunk CRC fail at offset", offset)
                send_cmd(CMD_OTA_ABORT, b"")
                sys.exit(1)
            break
        offset += len(chunk)
        if offset % (CHUNK_SIZE * 20) == 0 or offset == size:
            print(f"  {offset}/{size}")

    rc, rpay = send_cmd(CMD_OTA_FINISH, b"")
    if rc != 0x90 or (rpay and rpay[0] != 0):
        err_code = rpay[0] if rpay else 0
        err_names = {0x02: "RSP_OTA_ERR_SIZE (invalid total at START)",
                     0x03: "RSP_OTA_ERR_SIZE_MISMATCH (bytes_recv != total)",
                     0x08: "RSP_OTA_ERR_CRC_MISMATCH"}
        print(f"OTA_FINISH failed: {err_names.get(err_code, f'0x{err_code:02X}')}")
        if rpay and len(rpay) >= 5 and rpay[0] == 0x08:  # CRC mismatch has dev CRC in payload
            dev_crc = rpay[1] | (rpay[2]<<8) | (rpay[3]<<16) | (rpay[4]<<24)
            print(f"  Device computed CRC: 0x{dev_crc:08X} (expected 0x{crc_full:08X})")
        rc2, rpay2 = send_cmd(CMD_OTA_STATUS, b"")
        # STATUS layout: [0]=state, [1-4]=next_expected, [5-8]=bytes_received, [9-12]=total_size,
        # [13-16]=erase_progress, [17]=last_error, [18-19]=slots, [20-23]=expected_crc32
        if rc2 == 0x90 and len(rpay2) >= 24:
            state = rpay2[0]
            next_exp = rpay2[1] | (rpay2[2]<<8) | (rpay2[3]<<16) | (rpay2[4]<<24)
            br = rpay2[5] | (rpay2[6]<<8) | (rpay2[7]<<16) | (rpay2[8]<<24)
            ts = rpay2[9] | (rpay2[10]<<8) | (rpay2[11]<<16) | (rpay2[12]<<24)
            exp_crc = rpay2[20] | (rpay2[21]<<8) | (rpay2[22]<<16) | (rpay2[23]<<24)
            print(f"  Device: state={state} next_expected={next_exp} bytes_recv={br} total={ts} "
                  f"expected_crc=0x{exp_crc:08X}")
            if br < ts:
                print(f"  -> {ts - br} bytes missing (likely serial RX overflow; try slower rate)")
        ser.close()
        sys.exit(1)

    print("OTA complete. Reboot device to apply.")
    ser.close()


if __name__ == "__main__":
    main()
