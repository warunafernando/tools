# SmartBall OTA Stabilization -- Fully Autonomous Cursor Execution Document

This document instructs Cursor (AI coding agent) to fully stabilize
SmartBall BLE OTA on XIAO nRF52840 Sense without human intervention.

Cursor must implement ALL sections in order. Do not ask clarification
questions. If ambiguity exists, choose safest engineering default.

------------------------------------------------------------------------

# GLOBAL OBJECTIVE

Make BLE OTA 100% reliable with:

-   Immediate OTA_START acknowledgement
-   Background sector erase (non-blocking)
-   Keepalive during long operations
-   Sliding window OTA_DATA flow control
-   Resume-after-disconnect support
-   A/B test boot with confirm + rollback
-   Structured logging + diagnostics
-   Automated stress validation harness

No manual reset should be required after implementation.

------------------------------------------------------------------------

# PART 1 -- DEVICE FIRMWARE IMPLEMENTATION

## 1. OTA State Machine (Replace Existing)

Define states:

IDLE PREPARE_ERASE READY_FOR_DATA RECEIVING VERIFYING PENDING_REBOOT
TEST_BOOT ERROR

Implement strict transitions only.

------------------------------------------------------------------------

## 2. Immediate OTA_START ACK

On CMD_OTA_START:

1.  Validate header quickly
2.  Allocate OTA session structure
3.  Set state = PREPARE_ERASE
4.  Immediately send RSP_OTA_OK(sub=START)
5.  Return without performing erase

Erase must run in background task.

------------------------------------------------------------------------

## 3. Background Erase Engine

Implement incremental sector erase:

-   Erase 4KB at a time
-   After each sector:
    -   Call BLE.poll()
    -   Yield scheduler
    -   Send MSG_OTA_PROGRESS(offset)

Timeout requirement: Progress notification every 250--1000 ms.

When finished: Set state = READY_FOR_DATA Send MSG_OTA_READY

------------------------------------------------------------------------

## 4. OTA_DATA Handling

Rules:

-   Maintain next_expected_offset
-   Reject out-of-order chunks (send BAD_OFFSET)
-   Accept duplicate offset (re-ACK)

Flash write:

-   Write in page-size chunks (\<=256 bytes)
-   Yield between pages
-   After each page, update next_expected_offset

Flow control:

Implement sliding window = 4 chunks Host must never exceed this window.

------------------------------------------------------------------------

## 5. OTA_FINISH

Steps:

1.  Verify total size matches
2.  Compute CRC32 of entire image
3.  Compare to expected
4.  If OK:
    -   Mark pending test boot
    -   Send RSP_OTA_OK(FINISH)
    -   Reboot
5.  If fail:
    -   Send RSP_OTA_ERR(CRC_MISMATCH)
    -   Return to IDLE

------------------------------------------------------------------------

## 6. Bootloader A/B Policy

On boot:

If pending_test_boot:

-   Boot new slot
-   Start confirm timer (30 seconds)

If CMD_OTA_CONFIRM received: - Commit slot permanently

If watchdog reset or timeout before confirm: - Roll back automatically

------------------------------------------------------------------------

## 7. Health + Status Extensions

Extend RSP_STATUS:

Add:

-   ota_state
-   next_expected_offset
-   erase_progress_bytes
-   last_ota_error
-   active_slot
-   pending_slot

Ensure RSP_STATUS callable anytime without blocking.

------------------------------------------------------------------------

## 8. Connection Optimization (OTA Mode Only)

When entering OTA mode:

Request BLE parameters:

-   Connection interval 7.5--15 ms
-   Slave latency 0
-   Supervision timeout \>= 10 s

Restore normal parameters after OTA completes.

------------------------------------------------------------------------

# PART 2 -- HOST TOOL IMPLEMENTATION

Implement a robust OTA controller.

## 1. Golden Flow

1.  Connect
2.  Send CMD_OTA_ABORT (cleanup)
3.  Send CMD_OTA_START
4.  Wait for READY_FOR_DATA
5.  Stream OTA_DATA with sliding window
6.  Send CMD_OTA_FINISH
7.  Wait for reboot
8.  Reconnect
9.  Query STATUS
10. Send CMD_OTA_CONFIRM

------------------------------------------------------------------------

## 2. Resume After Disconnect

If disconnect occurs:

1.  Reconnect
2.  Query CMD_OTA_STATUS
3.  Get next_expected_offset
4.  Resume sending from that offset

Never restart from 0 unless device reports no session.

------------------------------------------------------------------------

## 3. Timeout Policy

Chunk ACK timeout: 3 seconds Retry up to 5 times per chunk After 5
failures: - reconnect and resume

------------------------------------------------------------------------

# PART 3 -- DIAGNOSTICS + LOGGING

Implement device ring buffer log (64 entries):

Events:

OTA_START ERASE_BEGIN ERASE_PROGRESS READY DATA_ACCEPT CRC_PASS CRC_FAIL
REBOOT CONFIRM ROLLBACK

Expose via CMD_GET_LOG

Host must log every state transition.

------------------------------------------------------------------------

# PART 4 -- STRESS TEST HARNESS

Implement automated test script:

Run 100 OTA updates sequentially.

For each:

-   Random disconnect injection at random offset
-   Resume
-   Verify success
-   Measure:
    -   total time
    -   retry count
    -   reconnect count

Acceptance criteria:

> = 98% success No manual power reset required No stuck state after
> failure

------------------------------------------------------------------------

# PART 5 -- SAFETY RULES

-   OTA allowed only when DISARMED
-   Battery above threshold
-   Prevent entering RECORDING during OTA
-   All errors must reset state cleanly

------------------------------------------------------------------------

# COMPLETION CRITERIA

Cursor must not stop until:

-   OTA passes 100-run stress test
-   Resume works after forced disconnect
-   Rollback works when firmware intentionally corrupted
-   STATUS reports correct slot + OTA state

No human intervention allowed during validation.

------------------------------------------------------------------------

# END OF DOCUMENT
