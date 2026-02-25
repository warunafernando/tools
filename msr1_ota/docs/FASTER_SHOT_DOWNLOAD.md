# Faster shot download over Bluetooth

The current shot fetch uses **one BLE connection per chunk** (240 bytes). This is the most stable approach on Linux/BlueZ but is slow (~5 min for 15 KB).

## Larger packet transfer in BLE (what’s available)

Yes. BLE supports larger packets in several ways:

| Mechanism | What it does | Typical limit | Notes |
|-----------|--------------|---------------|--------|
| **ATT MTU** | Max payload per Read/Write/Notify (one ATT operation). | Default 23; **negotiated 247** common; **up to 512** in BLE 4.2+ (Zephyr/nRF support 247–512). | Both central and peripheral must support and negotiate. Our firmware uses 240-byte payload (fits MTU 247). |
| **DLE (Data Length Extension)** | Link-layer PDU size (how much fits in one radio packet). | Up to **251 bytes** (BLE 4.2+). | Separate from MTU. If DLE &lt; MTU, the stack fragments; larger DLE = fewer fragments = higher throughput. |
| **L2CAP** | Can segment/reassemble large SDUs. | SDU up to **64 KB**; each segment still limited by MTU. | Used automatically when a single GATT operation is larger than MTU. |

**Practical for SmartBall:**  
- **247-byte MTU** is widely supported (nRF52840, Zephyr, many phones). So you can use **up to 244 bytes** of payload per GATT notification/write (MTU − 3 for ATT header).  
- **512-byte MTU** is supported in Zephyr/nRF and some centrals; gives **up to 509 bytes** per operation.  
- The **firmware** must be built with a large enough L2CAP/ATT buffer (e.g. `CONFIG_BT_L2CAP_TX_MTU=247` or `512`) and must perform **MTU exchange** after connection. Then increase `BLE_BIN_MAX_PAYLOAD` to match (e.g. 244 or 509).

So yes: larger packet transfer is available in BLE via **larger ATT MTU** (and optionally DLE). The limit is configuration and negotiation, not the protocol.

## Options to speed up

### 1. **USB / Serial (fastest when available)**

If the XIAO is connected over USB, use serial for shot transfer instead of BLE:

- Add a serial command (e.g. `CMD_GET_SHOT` over UART) that streams the shot in bulk.
- Or expose the same binary protocol over the USB CDC ACM port and use a larger “chunk” size (e.g. 512 bytes) for serial.

Serial can be 10–50× faster than BLE for the same data.

### 2. **Larger BLE chunk size (firmware + host)**

Current firmware uses `BLE_BIN_MAX_PAYLOAD = 240` (fits in ATT_MTU 247). To speed up BLE without changing the “one connection per chunk” strategy:

- **Firmware:** If the negotiated ATT MTU is 247 or 512, increase `BLE_BIN_MAX_PAYLOAD` (e.g. 244 for MTU 247, or 509 for MTU 512) in `ble_binary.h` and ensure the binary protocol sends at most that many payload bytes per frame.
- **Host:** In `app.py` and `ble_binary_client.py`, set `CHUNK` / request size to match the new payload size.

Fewer round-trips per shot (e.g. 64 → 31 for 15 KB with 512-byte chunks).

### 3. **MTU exchange (Linux/BlueZ)**

On Linux, Bleak/BlueZ do not always use a larger MTU even after negotiation; many stacks still fragment. So:

- Relying on MTU exchange alone often does **not** give a big gain on Linux.
- Increasing the **firmware** payload size (as in option 2) is what actually reduces round-trips, as long as the link can carry the larger frames.

### 4. **Single connection, multiple chunks (unstable on some setups)**

Using one long-lived connection and many chunks per connection is faster but often triggers “failed to discover services” or “device disconnected” mid-download on Linux/BlueZ. That approach was reverted in favor of one connection per chunk for stability.

---

**Summary:** For stability, keep one connection per chunk over BLE. For speed: prefer **USB/serial** when the device is plugged in; otherwise consider **larger BLE payload** in firmware + host (option 2).

---

## One-connection experiment (10–20 s target)

The app now tries **one long-lived connection** first (with 40 ms delay between chunks) and falls back to **one connection per chunk** if the device disconnects.

- **Firmware:** `BLE_BIN_MAX_PAYLOAD` was increased to **495** (build has `CONFIG_BT_L2CAP_TX_MTU=498`). Flash the new build so the device can send up to 495 bytes per chunk → ~31 chunks for 15 KB instead of 64.
- **Host:** `FETCH_SHOT_CHUNK_SIZE = 495`, and `fetch_shot_one_connection_sync(..., delay_between_chunks_sec=0.04)` is used first.
- **Experiment script:** With the device on and a shot recorded, run:
  ```bash
  cd msr1_ota/web_gui
  BLE_ADDR=XX:XX:XX:XX:XX:XX  python3 experiment_one_connection.py
  ```
  It tests delay 0, 20 ms, 40 ms, 60 ms, 100 ms and reports time and success. Typical target: **10–20 s** for 15 KB with one connection and 40 ms delay.
