# SmartBall Unit Test Results

**Date:** 2026-02-23  
**Target:** XIAO nRF52840 BLE Sense  
**Test interfaces:** BLE only (debugger USB + BLE)

---

## 1. BLE Unit Tests (Primary — All Tests Over BLE)

Script: `scripts/smartball_ble_tests.py`  
Run with **normal app** (no prj_test.conf). No flash or serial capture required.

| Test | Result |
|------|--------|
| test_frame_valid | PASS |
| test_frame_invalid_length_zero | PASS |
| test_frame_invalid_length_overflow | PASS |
| test_command_dispatcher_all_cmds | PASS |
| test_rsp_id_format | PASS |
| test_cmd_id_via_ble | PASS |
| test_cmd_status_via_ble | PASS |
| test_rsp_status_format | PASS |
| test_cmd_diag_via_ble | PASS |
| test_rsp_diag_format | PASS |
| test_cmd_selftest_via_ble | PASS |
| test_cmd_start_record_via_ble | PASS |
| test_cmd_stop_record_via_ble | PASS |
| test_cmd_bus_scan_via_ble | PASS |

**Status:** 11 test cases (includes Phase 4 CMD_BUS_SCAN)

### Sample output

```
Connecting to D0:8D:27:9F:56:14...
PASS test_frame_valid
PASS test_frame_invalid_length_zero
PASS test_frame_invalid_length_overflow
PASS test_command_dispatcher_all_cmds
PASS test_rsp_id_format
PASS test_cmd_id_via_ble
PASS test_cmd_status_via_ble
PASS test_rsp_status_format
PASS test_cmd_diag_via_ble
PASS test_rsp_diag_format
PASS test_cmd_selftest_via_ble
PASS test_cmd_start_record_via_ble
PASS test_cmd_stop_record_via_ble (samples=3)
---
SmartBall BLE tests: 10/10 passed
```

---

## 2. BLE Selftest (Standalone)

Script: `scripts/smartball_selftest.py`  
Quick CMD_SELFTEST over BLE; result printed to stdout.

```
Connecting to D0:8D:27:9F:56:14...
SELFTEST PASSED
```

---

## 3. On-Device Ztest (Optional — Requires Flash + Serial)

Built with `-DEXTRA_CONF_FILE=prj_v1.conf -DEXTRA_CONF_FILE=prj_test.conf`, flashed via OpenOCD.  
Output from `/dev/ttyACM1` at 115200 baud. Covers Phase 1 protocol + Phase 2 IMU tests.  
Use BLE tests as primary; Ztest for debug when needed.

---

## 4. Mapping to Implementation Plan

### Phase 1 (1.4)

| Doc Test | BLE Test | Result |
|----------|----------|--------|
| test_frame_parser_valid_header | test_frame_valid | PASS |
| test_frame_parser_invalid_length_zero | test_frame_invalid_length_zero | PASS |
| test_frame_parser_invalid_length_overflow | test_frame_invalid_length_overflow | PASS |
| test_command_dispatcher_all_cmds | test_command_dispatcher_all_cmds | PASS |
| test_rsp_id_format | test_rsp_id_format | PASS |
| test_cmd_id_via_ble | test_cmd_id_via_ble | PASS |

### Phase 2 (2.4)

| Doc Test | BLE Test | Result |
|----------|----------|--------|
| test_cmd_status_via_ble | test_cmd_status_via_ble | PASS |
| test_rsp_status_format | test_rsp_status_format | PASS |
| test_cmd_diag_via_ble | test_cmd_diag_via_ble | PASS |
| test_rsp_diag_format | test_rsp_diag_format | PASS |
| test_cmd_selftest_via_ble | test_cmd_selftest_via_ble | PASS |

### Phase 3 (3.4)

| Doc Test | BLE Test | Result |
|----------|----------|--------|
| test_cmd_start_record_via_ble | test_cmd_start_record_via_ble | PASS |
| test_cmd_stop_record_via_ble | test_cmd_stop_record_via_ble | PASS |

### Phase 4 (4.6)

| Doc Test | BLE Test | Result |
|----------|----------|--------|
| test_cmd_bus_scan_via_ble | test_cmd_bus_scan_via_ble | PASS |

---

## 5. Commands Used

```bash
# Build and flash normal app (for BLE tests)
cd ncs-workspace/nrf
west build -b xiao_ble_sense app --sysbuild -- \
  -DEXTRA_CONF_FILE=prj_v1.conf -DAPP_LED_SLOT=0
west flash -d build --runner openocd

# Run all unit tests over BLE (primary)
python3 scripts/smartball_ble_tests.py [BLE_ADDR]

# Quick selftest
python3 scripts/smartball_selftest.py [BLE_ADDR]
```
