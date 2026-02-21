/**
 * OTA - dual slot, immediate START ack, background erase, sliding window, resume
 */
#include "ota.h"
#include "protocol.h"
#include <Arduino.h>
#include <mbed.h>
#include <cstring>

#define OTA_FLAG_ADDR  0x000FE000
#define OTA_FLAG_MAGIC 0x4F544146  // "OTAF"

#pragma pack(push, 1)
struct ota_flag {
    uint32_t magic;
    uint8_t  pending;
    uint8_t  confirmed;
    uint8_t  slot;
    uint8_t  _res;
    uint32_t size;
    uint32_t crc32;
};
#pragma pack(pop)

static uint32_t crc32_table[256];
static bool crc32_table_init = false;

static void crc32_init_table(void) {
    if (crc32_table_init) return;
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t c = i;
        for (int k = 0; k < 8; k++)
            c = (c & 1) ? (0xEDB88320 ^ (c >> 1)) : (c >> 1);
        crc32_table[i] = c;
    }
    crc32_table_init = true;
}

static uint32_t crc32_update(uint32_t crc, const uint8_t *data, uint32_t len) {
    crc = ~crc;
    while (len--) crc = crc32_table[(crc ^ *data++) & 0xFF] ^ (crc >> 8);
    return ~crc;
}

static ota_ctx_t ctx;
static ota_send_fn s_send = NULL;
static ota_yield_fn s_yield = NULL;
static ota_state_t s_state = OTA_IDLE;

/* Background erase state */
static uint32_t s_erase_addr = 0;
static uint32_t s_erase_total = 0;
static uint32_t s_last_progress_ms = 0;
static bool s_erase_started = false;

/* Ring buffer log */
static uint8_t s_log_ring[OTA_LOG_ENTRIES * OTA_LOG_ENTRY_SIZE];
static uint8_t s_log_head = 0;
static uint8_t s_log_count = 0;

void ota_log_event(uint8_t event, uint32_t param) {
    uint8_t *p = s_log_ring + (s_log_head * OTA_LOG_ENTRY_SIZE);
    p[0] = event;
    p[1] = (uint8_t)(param);
    p[2] = (uint8_t)(param >> 8);
    p[3] = (uint8_t)(param >> 16);
    s_log_head = (s_log_head + 1) % OTA_LOG_ENTRIES;
    if (s_log_count < OTA_LOG_ENTRIES) s_log_count++;
}

uint8_t ota_get_log(uint8_t *buf, uint8_t max_entries) {
    uint8_t n = (max_entries <= s_log_count) ? max_entries : s_log_count;
    uint8_t start = (s_log_head + OTA_LOG_ENTRIES - s_log_count) % OTA_LOG_ENTRIES;
    for (uint8_t i = 0; i < n; i++) {
        uint8_t *src = s_log_ring + ((start + i) % OTA_LOG_ENTRIES) * OTA_LOG_ENTRY_SIZE;
        memcpy(buf + i * OTA_LOG_ENTRY_SIZE, src, OTA_LOG_ENTRY_SIZE);
    }
    return n;
}

extern "C" void NVIC_SystemReset(void);

void ota_init(ota_send_fn send_fn) {
    s_send = send_fn;
    crc32_init_table();
    ota_reset();
}

void ota_set_yield(ota_yield_fn yield_fn) {
    s_yield = yield_fn;
}

void ota_reset(void) {
    s_state = OTA_IDLE;
    memset(&ctx, 0, sizeof(ctx));
    ctx.last_ota_error = OTA_ERR_NONE;
    s_erase_addr = 0;
    s_erase_total = 0;
    s_erase_started = false;
}

static void ota_write_flag(const struct ota_flag *f) {
    mbed::FlashIAP flash;
    if (flash.init() != 0) return;
    flash.erase(OTA_FLAG_ADDR, 4096);
    flash.program((const void*)f, OTA_FLAG_ADDR, sizeof(struct ota_flag));
    flash.deinit();
}

static void ota_read_flag(struct ota_flag *f) {
    memcpy(f, (const void*)OTA_FLAG_ADDR, sizeof(struct ota_flag));
}

static void set_error(ota_error_t e) {
    ctx.last_ota_error = e;
}

bool ota_is_pending_confirm(void) {
    struct ota_flag f;
    ota_read_flag(&f);
    return (f.magic == OTA_FLAG_MAGIC && f.pending == 1 && f.confirmed == 0);
}

void ota_clear_pending_confirm(void) {
    struct ota_flag f;
    ota_read_flag(&f);
    if (f.magic != OTA_FLAG_MAGIC) return;
    f.confirmed = 1;
    f.pending = 0;
    ota_write_flag(&f);
}

void ota_confirm(void) {
    ota_clear_pending_confirm();
}

void ota_rollback_pending(void) {
    struct ota_flag f;
    ota_read_flag(&f);
    if (f.magic != OTA_FLAG_MAGIC) return;
    f.pending = 0;
    f.confirmed = 0;
    ota_write_flag(&f);
}

const ota_ctx_t *ota_get_ctx(void) {
    return &ctx;
}

/* Background erase: one sector per call, progress every OTA_PROGRESS_INTERVAL_MS */
void ota_poll(void) {
    if (s_state != OTA_PREPARE_ERASE || s_erase_total == 0) return;

    if (!s_erase_started) {
        s_erase_started = true;
        s_erase_addr = OTA_SLOT_B_ADDR;
        s_last_progress_ms = millis();
    }

    if (s_erase_addr >= OTA_SLOT_B_ADDR + s_erase_total) {
        /* Erase complete */
        s_state = OTA_READY_FOR_DATA;
        ctx.erase_progress_bytes = s_erase_total;
        ota_log_event(4, s_erase_total);  /* READY */
        if (s_send) {
            uint8_t ready = 0;
            s_send(MSG_OTA_READY, &ready, 1);
        }
        s_erase_started = false;
        return;
    }

    if (s_yield) s_yield();  /* Yield before blocking erase to service BLE */
    mbed::FlashIAP flash;
    if (flash.init() != 0) return;
    uint32_t n = OTA_ERASE_SECTOR;
    if (s_erase_addr + n > OTA_SLOT_B_ADDR + s_erase_total)
        n = (OTA_SLOT_B_ADDR + s_erase_total) - s_erase_addr;
    flash.erase(s_erase_addr, n);
    flash.deinit();
    s_erase_addr += n;
    ctx.erase_progress_bytes = s_erase_addr - OTA_SLOT_B_ADDR;
    if (s_yield) s_yield();

    uint32_t now = millis();
    if (now - s_last_progress_ms >= OTA_PROGRESS_INTERVAL_MS) {
        s_last_progress_ms = now;
        if (s_send) {
            uint32_t off = ctx.erase_progress_bytes;
            s_send(MSG_OTA_PROGRESS, (const uint8_t*)&off, 4);
        }
    }
}

void ota_feed(const uint8_t *data, uint16_t len) {
    if (len < 3) return;
    uint8_t type = data[0];
    uint16_t paylen = data[1] | (data[2] << 8);
    const uint8_t *payload = (len >= 3 + paylen) ? data + 3 : NULL;
    if (!payload || paylen > len - 3) return;

    switch (type) {
        case CMD_OTA_START: {
            if (paylen < 11) break;
            if (s_state != OTA_IDLE) {
                ota_reset();
            }
            ctx.slot = payload[0];
            ctx.version = payload[1] | (payload[2] << 8);
            ctx.total_size = payload[3] | (payload[4]<<8) | (payload[5]<<16) | (payload[6]<<24);
            ctx.expected_crc32 = payload[7] | (payload[8]<<8) | (payload[9]<<16) | (payload[10]<<24);
            ctx.bytes_received = 0;
            ctx.crc32_accum = 0;
            ctx.next_expected_offset = 0;
            ctx.erase_progress_bytes = 0;
            set_error(OTA_ERR_NONE);

            if (ctx.total_size == 0 || ctx.total_size > OTA_STAGING_SIZE) {
                set_error(OTA_ERR_SIZE);
                if (s_send) { uint8_t e = RSP_OTA_ERR_SIZE; s_send(RSP_OTA, &e, 1); }
                break;
            }

            s_state = OTA_PREPARE_ERASE;
            s_erase_total = (ctx.total_size + (OTA_ERASE_SECTOR - 1)) & ~(OTA_ERASE_SECTOR - 1);
            if (s_erase_total < OTA_ERASE_SECTOR) s_erase_total = OTA_ERASE_SECTOR;
            s_erase_started = false;
            ota_log_event(1, ctx.total_size);  /* OTA_START */
            if (s_send) { uint8_t ok = RSP_OTA_OK_START; s_send(RSP_OTA, &ok, 1); }
            break;
        }
        case CMD_OTA_DATA: {
            if (paylen < 8) break;
            /* Still erasing: send progress to keep BLE link alive, host will retry */
            if (s_state == OTA_PREPARE_ERASE) {
                if (s_send) {
                    uint32_t off = ctx.erase_progress_bytes;
                    s_send(MSG_OTA_PROGRESS, (const uint8_t*)&off, 4);
                }
                break;
            }
            if (s_state != OTA_READY_FOR_DATA && s_state != OTA_RECEIVING) break;

            uint32_t offset = payload[0] | (payload[1]<<8) | (payload[2]<<16) | (payload[3]<<24);
            uint16_t chunk_len = paylen - 8;
            const uint8_t *chunk = payload + 4;
            uint32_t chunk_crc = (uint32_t)payload[paylen - 4] | ((uint32_t)payload[paylen - 3] << 8) |
                ((uint32_t)payload[paylen - 2] << 16) | ((uint32_t)payload[paylen - 1] << 24);

            if (offset + chunk_len > ctx.total_size || chunk_len > OTA_CHUNK_MAX) {
                set_error(OTA_ERR_CHUNK);
                s_state = OTA_ERROR;
                if (s_send) { uint8_t e = RSP_OTA_ERR_CHUNK; s_send(RSP_OTA, &e, 1); }
                break;
            }
            uint32_t cap = ctx.total_size - offset;
            if (chunk_len > cap) chunk_len = (uint16_t)cap;

            /* Out of order: reject with BAD_OFFSET so host can resume */
            if (offset > ctx.next_expected_offset) {
                set_error(OTA_ERR_BAD_OFFSET);
                if (s_send) {
                    uint8_t rsp[5];
                    rsp[0] = RSP_OTA_ERR_BAD_OFFSET;
                    memcpy(rsp + 1, &ctx.next_expected_offset, 4);
                    s_send(RSP_OTA, rsp, 5);
                }
                break;
            }
            /* Duplicate: re-ACK */
            if (offset < ctx.next_expected_offset) {
                uint8_t rsp[9] = {0};
                memcpy(rsp+1, &offset, 4);
                memcpy(rsp+5, &ctx.total_size, 4);
                if (s_send) s_send(RSP_OTA, rsp, 9);
                break;
            }

            uint32_t computed = crc32_update(0, chunk, chunk_len);
            if (computed != chunk_crc) {
                set_error(OTA_ERR_CHUNK_CRC);
                if (s_send) { uint8_t e = RSP_OTA_ERR_CHUNK_CRC; s_send(RSP_OTA, &e, 1); }
                break;
            }

            s_state = OTA_RECEIVING;
            ctx.crc32_accum = crc32_update(ctx.crc32_accum, chunk, chunk_len);
            ctx.bytes_received += chunk_len;

            mbed::FlashIAP flash;
            if (flash.init() == 0) {
                uint32_t addr = OTA_SLOT_B_ADDR + offset;
                uint32_t remain = chunk_len;
                const uint8_t *p = chunk;
                while (remain > 0) {
                    uint32_t n = (remain > OTA_DATA_PAGE) ? OTA_DATA_PAGE : remain;
                    flash.program(p, addr, n);
                    addr += n;
                    p += n;
                    remain -= n;
                    if (s_yield && remain > 0) s_yield();
                }
                flash.deinit();
            }

            ctx.next_expected_offset = offset + chunk_len;
            uint8_t rsp[9] = {0};
            memcpy(rsp+1, &ctx.next_expected_offset, 4);
            memcpy(rsp+5, &ctx.total_size, 4);
            if (s_send) s_send(RSP_OTA, rsp, 9);
            break;
        }
        case CMD_OTA_FINISH: {
            if (s_state != OTA_RECEIVING) break;
            s_state = OTA_VERIFYING;

            if (ctx.bytes_received != ctx.total_size) {
                s_state = OTA_ERROR;
                set_error(OTA_ERR_SIZE_MISMATCH);
                if (s_send) { uint8_t e = RSP_OTA_ERR_SIZE_MISMATCH; s_send(RSP_OTA, &e, 1); }
                break;
            }
            if (ctx.crc32_accum != ctx.expected_crc32) {
                s_state = OTA_ERROR;
                set_error(OTA_ERR_CRC_MISMATCH);
                uint8_t err[5];
                err[0] = RSP_OTA_ERR_CRC_MISMATCH;
                memcpy(err + 1, &ctx.crc32_accum, 4);
                if (s_send) s_send(RSP_OTA, err, 5);
                break;
            }
            const uint32_t *hdr = (const uint32_t*)OTA_SLOT_B_ADDR;
            if (hdr[0] != OTA_MAGIC) {
                s_state = OTA_ERROR;
                set_error(OTA_ERR_BAD_MAGIC);
                if (s_send) { uint8_t e = RSP_OTA_ERR_BAD_MAGIC; s_send(RSP_OTA, &e, 1); }
                break;
            }

            struct ota_flag f;
            memset(&f, 0, sizeof(f));
            f.magic = OTA_FLAG_MAGIC;
            f.pending = 1;
            f.confirmed = 0;
            f.slot = 1;
            f.size = ctx.total_size;
            f.crc32 = ctx.expected_crc32;
            ota_write_flag(&f);

            s_state = OTA_PENDING_REBOOT;
            if (s_send) { uint8_t ok = RSP_OTA_OK_FINISH; s_send(RSP_OTA, &ok, 1); }
            delay(50);
            NVIC_SystemReset();
            break;
        }
        case CMD_OTA_ABORT:
            ota_reset();
            if (s_send) s_send(RSP_OTA, (const uint8_t*)"", 0);
            break;
        case CMD_OTA_STATUS: {
            struct ota_flag f;
            ota_read_flag(&f);
            ctx.active_slot = (f.slot == 1 && f.confirmed) ? 1 : 0;
            ctx.pending_slot = (f.pending && !f.confirmed) ? 1 : 0;
            uint8_t rsp[24];
            rsp[0] = (uint8_t)s_state;
            memcpy(rsp+1, &ctx.next_expected_offset, 4);
            memcpy(rsp+5, &ctx.bytes_received, 4);
            memcpy(rsp+9, &ctx.total_size, 4);
            memcpy(rsp+13, &ctx.erase_progress_bytes, 4);
            rsp[17] = (uint8_t)ctx.last_ota_error;
            rsp[18] = ctx.active_slot;
            rsp[19] = ctx.pending_slot;
            memcpy(rsp+20, &ctx.expected_crc32, 4);
            if (s_send) s_send(RSP_OTA, rsp, 24);
            break;
        }
        case CMD_OTA_CONFIRM:
            ota_confirm();
            if (s_send) { uint8_t ok = 0; s_send(RSP_OTA, &ok, 1); }
            break;
        case CMD_OTA_REBOOT:
            ota_log_event(8, 0);  // REBOOT
            if (s_send) { uint8_t ok = 0; s_send(RSP_OTA, &ok, 1); }
            delay(100);
            NVIC_SystemReset();
            break;
        case CMD_OTA_GET_LOG: {
            uint8_t tmp[OTA_LOG_ENTRIES * OTA_LOG_ENTRY_SIZE];
            uint8_t n = ota_get_log(tmp, OTA_LOG_ENTRIES);
            if (s_send) s_send(RSP_OTA, tmp, n * OTA_LOG_ENTRY_SIZE);
            break;
        }
        default:
            break;
    }
}

ota_state_t ota_get_state(void) {
    return s_state;
}
