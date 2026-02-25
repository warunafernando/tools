# SmartBall BLE fetch test (known file)

## What it does

1. **Firmware** exposes a **test shot** (id `0xAAAAAAAA`, size 15360 bytes) with deterministic content.  
   `LIST_SHOTS` returns it as the first entry.  
   `GET_SHOT` / `GET_SHOT_CHUNK` for that id return the known bytes (no storage read).

2. **Test script** `smartball_ble_fetch_test.py`:
   - Connects to SmartBall (scan or `BLE_ADDR`).
   - If test shot is present: runs **one-connection** (chunk 495 and 240, several delays) and **per-connection** fetch multiple times, and **verifies** every result against the known file.
   - If test shot is not present: run with `--timing-only` to use the **first real shot** and only report timings (no content verify).

## Run (after flashing FW with test shot)

```bash
cd msr1_ota/web_gui
# Optional: set address to skip scan
export BLE_ADDR=D0:8D:27:9F:56:14
python3 smartball_ble_fetch_test.py
```

## Run timing-only (current FW, any shot)

```bash
python3 smartball_ble_fetch_test.py --timing-only
```

## Flash firmware that includes the test shot

- Build: from `ncs-workspace`: `west build -b xiao_ble_sense nrf/app --sysbuild`
- Flash: copy `build/app/zephyr/zephyr.uf2` to the XIAO (double-tap RST, then paste), or use your debugger to load the built image.
- After flash, `LIST_SHOTS` will list the test shot first (id 0xAAAAAAAA, size 15360); then run the test without `--timing-only` for full verify.

## Observed results (timing-only on device with 240-byte chunks)

- **One connection, chunk=495:** incomplete (device only sends 240).
- **One connection, chunk=240, delay=0.04s:** **PASS** in ~24s for ~15.5 KB.
- **Per-connection (240):** stable but slow (~4–5 min for 15 KB).

So the app uses one-connection with 240-byte chunks and 0.04s delay when 495 is not available, giving ~20–25s for ~15 KB.
