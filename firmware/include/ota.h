/**
 * OTA Update - dual slot, CRC verify, fallback, Serial+BLE
 * Stabilization: immediate START ack, background erase, sliding window, resume.
 * Image header: MAGIC(4) + VERSION(2) + SIZE(4) + CRC32(4) = 14 bytes
 */
#ifndef OTA_H
#define OTA_H

#include <stdint.h>
#include <stdbool.h>

#define OTA_MAGIC          0x53424F54  // "SBOT" SmartBall OTA
#define OTA_HEADER_SIZE    14
#define OTA_CHUNK_MAX      480
#define OTA_DATA_PAGE      256        /* flash write page for yield */
#define OTA_SLIDING_WINDOW 4          /* host may send up to 4 chunks ahead */
#define OTA_STAGING_SIZE   (496 * 1024)  /* Slot B: 0x80000..0xFE000 = ~496KB */
#define OTA_SLOT_A_ADDR    0x00026000  // primary
#define OTA_SLOT_B_ADDR    0x00080000  // staging
#define OTA_ERASE_SECTOR   4096       // 4KB erase chunk
#define OTA_PROGRESS_INTERVAL_MS 250  // send progress every 250ms (keeps BLE link alive)

typedef enum {
    OTA_IDLE,
    OTA_PREPARE_ERASE,
    OTA_READY_FOR_DATA,
    OTA_RECEIVING,
    OTA_VERIFYING,
    OTA_PENDING_REBOOT,
    OTA_TEST_BOOT,
    OTA_ERROR
} ota_state_t;

typedef enum {
    OTA_ERR_NONE = 0,
    OTA_ERR_SIZE,
    OTA_ERR_SIZE_MISMATCH,
    OTA_ERR_CHUNK,
    OTA_ERR_BAD_MAGIC,
    OTA_ERR_CHUNK_CRC,
    OTA_ERR_BAD_OFFSET,
    OTA_ERR_CRC_MISMATCH
} ota_error_t;

typedef struct {
    uint8_t  slot;
    uint16_t version;
    uint32_t total_size;
    uint32_t expected_crc32;
    uint32_t bytes_received;
    uint32_t crc32_accum;
    uint32_t next_expected_offset;   /* for ordered accept + resume */
    uint32_t erase_progress_bytes;   /* for status / progress */
    ota_error_t last_ota_error;
    uint8_t  active_slot;   /* 0=A, 1=B */
    uint8_t  pending_slot;  /* 0=none, 1=B */
} ota_ctx_t;

typedef int (*ota_send_fn)(uint8_t type, const uint8_t *payload, uint16_t len);
typedef void (*ota_yield_fn)(void);

void ota_init(ota_send_fn send_fn);
void ota_set_yield(ota_yield_fn yield_fn);
void ota_feed(const uint8_t *data, uint16_t len);
/** Call from main loop; runs background erase and progress. */
void ota_poll(void);
ota_state_t ota_get_state(void);
void ota_reset(void);
/** Get session context for STATUS / resume (next_expected_offset etc.). */
const ota_ctx_t *ota_get_ctx(void);

void ota_confirm(void);
bool ota_is_pending_confirm(void);
void ota_clear_pending_confirm(void);
/** Call when pending confirm timeout (30s) expires -> rollback. */
void ota_rollback_pending(void);

#define OTA_LOG_ENTRIES 64
#define OTA_LOG_ENTRY_SIZE 4  /* event(1) + param(3) or small payload */
void ota_log_event(uint8_t event, uint32_t param);
/** Fill buffer with log entries (oldest first); returns count. */
uint8_t ota_get_log(uint8_t *buf, uint8_t max_entries);

#endif /* OTA_H */
