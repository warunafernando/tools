/**
 * SmartBall Binary Protocol — ESP32-C6 WiFi implementation.
 * Same frame format as nRF BLE; handlers return compatible responses.
 */
#include "binary_protocol.h"
#include "spi_bus.h"
#include "esp_timer.h"
#include "esp_system.h"
#include "esp_chip_info.h"
#include "esp_wifi.h"
#include <string.h>
#include <sys/param.h>

static inline uint16_t get_le16(const uint8_t *p) {
    return (uint16_t)p[0] | ((uint16_t)p[1] << 8);
}
static inline void put_le16(uint8_t *p, uint16_t v) {
    p[0] = (uint8_t)(v & 0xff);
    p[1] = (uint8_t)(v >> 8);
}
static inline uint32_t get_le32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static inline void put_le32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v & 0xff);
    p[1] = (uint8_t)((v >> 8) & 0xff);
    p[2] = (uint8_t)((v >> 16) & 0xff);
    p[3] = (uint8_t)(v >> 24);
}

int binary_get_rssi(int *rssi) {
    if (!rssi) return -1;
    *rssi = -128;
    wifi_ap_record_t ap;
    if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
        *rssi = ap.rssi;
        return 0;
    }
    return -1;
}

static uint8_t get_reset_reason(void) {
    switch (esp_reset_reason()) {
    case ESP_RST_POWERON:  return 1;
    case ESP_RST_EXT:      return 2;
    case ESP_RST_SW:       return 3;
    case ESP_RST_PANIC:    return 4;
    case ESP_RST_INT_WDT:  return 5;
    case ESP_RST_TASK_WDT: return 6;
    case ESP_RST_WDT:      return 6;
    case ESP_RST_DEEPSLEEP: return 7;
    case ESP_RST_BROWNOUT: return 8;
    case ESP_RST_SDIO:     return 9;
    default:               return 0;
    }
}

static void build_rsp_id(uint8_t *out, size_t *out_len) {
    uint8_t uid[8] = { 0 };
    uint8_t mac[6];
    if (esp_wifi_get_mac(WIFI_IF_STA, mac) == ESP_OK) {
        memcpy(uid, mac, 6);
        uid[6] = 0xC6;  /* ESP32-C6 marker */
        uid[7] = 0x01;
    } else {
        uid[0] = 0xC6;
        uid[1] = 0x32;
    }
    uint16_t payload_len = 2 + 1 + 1 + 1 + 8;
    out[0] = RSP_ID;
    put_le16(&out[1], payload_len);
    put_le16(&out[3], FW_VERSION);
    out[5] = PROTOCOL_VERSION;
    out[6] = HW_REVISION;
    out[7] = 8;
    memcpy(&out[8], uid, 8);
    *out_len = 3 + payload_len;
}

static void build_rsp_status(uint8_t *out, size_t *out_len) {
    size_t n = 3;
    uint32_t uptime_ms = (uint32_t)(esp_timer_get_time() / 1000);
    put_le32(&out[n], uptime_ms); n += 4;
    put_le32(&out[n], 0); n += 4;
    put_le32(&out[n], 0); n += 4;
    out[n++] = 1;  /* state: idle (no recording on ESP32-C6 yet) */
    put_le32(&out[n], 0); n += 4;  /* samples */
    out[n++] = 0;
    out[n++] = 0;
    put_le32(&out[n], 0); n += 4;  /* used */
    put_le32(&out[n], esp_get_free_heap_size()); n += 4;
    put_le16(&out[n], 0); n += 2;
    out[n++] = 0;   /* temp (no IMU temp on ESP32-C6) */
    out[n++] = get_reset_reason();
    put_le32(&out[n], 0x01000001); n += 4;

    uint16_t payload_len = (uint16_t)(n - 3);
    out[0] = RSP_STATUS;
    put_le16(&out[1], payload_len);
    *out_len = n;
}

/* RSP_DIAG layout matches nRF for format_response: imu_ready, whoami, pad, voltage_mv, temp, lsm6_ok, fa, fg */
static void build_rsp_diag(uint8_t *out, size_t *out_len) {
    size_t n = 3;
    out[n++] = 0;   /* imu_ready (no IMU) */
    out[n++] = 0xC6;  /* whoami: ESP32-C6 marker (nRF uses 0x6A for LSM6) */
    out[n++] = 0;
    out[n++] = 0;
    put_le16(&out[n], 0); n += 2;  /* voltage_mv (n/a on ESP32) */
    out[n++] = 0;   /* temp (n/a) */
    out[n++] = 0;   /* lsm6_ok (no LSM6) */
    put_le16(&out[n], 0); n += 2;  /* fa */
    put_le16(&out[n], 0); n += 2;  /* fg */
    /* Extra ESP32-C6 fields (format_response ignores these) */
    int rssi = -128;
    binary_get_rssi(&rssi);
    out[n++] = (uint8_t)(rssi < -128 ? 0 : (rssi > 127 ? 127 : rssi));
    put_le32(&out[n], esp_get_free_heap_size()); n += 4;
    out[n++] = get_reset_reason();
    esp_chip_info_t chip;
    esp_chip_info(&chip);
    out[n++] = (uint8_t)chip.cores;
    out[n++] = (uint8_t)chip.revision;

    uint16_t payload_len = (uint16_t)(n - 3);
    out[0] = RSP_DIAG;
    put_le16(&out[1], payload_len);
    *out_len = n;
}

static void build_rsp_selftest(uint8_t *out, size_t *out_len, uint8_t result) {
    out[0] = RSP_SELFTEST;
    put_le16(&out[1], 1);
    out[3] = result;
    *out_len = 4;
}

/* RSP_BUS_SCAN payload: same as nRF — num_spi | [type,cs,id0,id1,id2,flags]... | num_i2c | [addr,flags]... */
#define BUS_SCAN_TYPE_LSM6    1
#define BUS_SCAN_TYPE_ADXL    2
#define BUS_SCAN_TYPE_W25Q64  3
#define BUS_SCAN_FLAG_PRESENT 0x01
#define LSM6_WHOAMI_REG       0x0F
#define ADXL_DEVID_REG        0x00
#define ADXL375_DEVID         0xE5
#define W25Q64_CMD_JEDEC_ID   0x9F
#define W25Q64_JEDEC_MFG      0xEF

static void build_rsp_bus_scan(uint8_t *out, size_t *out_len) {
    size_t n = 3;
    uint8_t num_spi = 0;
    uint8_t tmp[8];

    if (spi_bus_init() == 0) {
        uint8_t flags;
        /* LSM6DSOX — WHO_AM_I reg 0x0F */
        uint8_t whoami = 0;
        if (spi_bus_chip_read(SPI_CS_LSM6, LSM6_WHOAMI_REG, &whoami, 1) == 0) {
            flags = (whoami == 0x6C || whoami == 0x6A || whoami == 0x69) ? BUS_SCAN_FLAG_PRESENT : 0;
        } else {
            flags = 0;
        }
        out[n++] = BUS_SCAN_TYPE_LSM6;
        out[n++] = 0;
        out[n++] = whoami;
        out[n++] = 0;
        out[n++] = 0;
        out[n++] = flags;
        num_spi++;

        /* ADXL375 — DEVID reg 0x00 */
        uint8_t devid = 0;
        if (spi_bus_chip_read(SPI_CS_ADXL, ADXL_DEVID_REG, &devid, 1) == 0) {
            flags = (devid == ADXL375_DEVID) ? BUS_SCAN_FLAG_PRESENT : 0;
        } else {
            flags = 0;
        }
        out[n++] = BUS_SCAN_TYPE_ADXL;
        out[n++] = 1;
        out[n++] = devid;
        out[n++] = 0;
        out[n++] = 0;
        out[n++] = flags;
        num_spi++;

        /* W25Q64 — JEDEC 0x9F */
        memset(tmp, 0, sizeof(tmp));
        tmp[0] = W25Q64_CMD_JEDEC_ID;
        if (spi_bus_transfer(SPI_CS_FLASH, tmp, tmp, 4, 0) == 0) {
            uint8_t mfg = tmp[1], mem = tmp[2], cap = tmp[3];
            flags = (mfg == W25Q64_JEDEC_MFG && mem == 0x40 && (cap == 0x17 || cap == 0x16)) ?
                BUS_SCAN_FLAG_PRESENT : 0;
            out[n++] = BUS_SCAN_TYPE_W25Q64;
            out[n++] = 2;
            out[n++] = mfg;
            out[n++] = mem;
            out[n++] = cap;
            out[n++] = flags;
        } else {
            out[n++] = BUS_SCAN_TYPE_W25Q64;
            out[n++] = 2;
            out[n++] = 0;
            out[n++] = 0;
            out[n++] = 0;
            out[n++] = 0;
        }
        num_spi++;
    }

    /* nRF format: num_spi at offset 3, then SPI entries */
    if (num_spi > 0) {
        memmove(&out[4], &out[3], num_spi * 6);
        out[3] = num_spi;
        n = 4 + num_spi * 6;
    } else {
        out[n++] = 0;
    }

    /* num_i2c — no I2C sensors on this board */
    out[n++] = 0;

    uint16_t payload_len = (uint16_t)(n - 3);
    out[0] = RSP_BUS_SCAN;
    put_le16(&out[1], payload_len);
    *out_len = n;
}

static void build_rsp_cfg(uint8_t *out, size_t *out_len) {
    size_t n = 3;
    out[n++] = 0;   /* no config storage yet */
    uint16_t payload_len = (uint16_t)(n - 3);
    out[0] = RSP_CFG;
    put_le16(&out[1], payload_len);
    *out_len = n;
}

static uint8_t test_shot_byte_at(size_t off) {
    if (off >= TEST_SHOT_SIZE) return 0;
    if (off < 8) return (uint8_t)("SVTSHOT3"[off]);
    if (off < 24) {
        const uint8_t hdr[] = { 0x01, 0x00, 0x64, 0x00, 0x23, 0x02, 0x00, 0x00,
                                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
        return hdr[off - 8];
    }
    if (off >= TEST_SHOT_SIZE - 4) return (uint8_t)(off & 0xff);
    return (uint8_t)((off * 31) & 0xff);
}

static void test_shot_fill(uint8_t *dst, size_t offset, size_t len) {
    for (size_t i = 0; i < len && (offset + i) < TEST_SHOT_SIZE; i++) {
        dst[i] = test_shot_byte_at(offset + i);
    }
}

int binary_parse_frame(const uint8_t *buf, size_t len,
                       uint8_t *out_type, const uint8_t **out_payload, uint16_t *out_len) {
    if (!buf || len < BIN_FRAME_HEADER_SIZE || !out_type || !out_payload || !out_len)
        return -1;
    uint16_t plen = get_le16(&buf[1]);
    if (plen == 0 || plen > BIN_MAX_PAYLOAD)
        return -1;
    if (len < BIN_FRAME_HEADER_SIZE + plen)
        return -1;
    *out_type = buf[0];
    *out_payload = &buf[BIN_FRAME_HEADER_SIZE];
    *out_len = plen;
    return 0;
}

size_t binary_process_cmd(uint8_t type, const uint8_t *payload, uint16_t len,
                          uint8_t *rsp_buf, size_t rsp_buf_size, uint16_t max_chunk) {
    (void)payload;
    (void)len;
    if (!rsp_buf || rsp_buf_size < BIN_FRAME_HEADER_SIZE + 4)
        return 0;
    uint16_t chunk_limit = (max_chunk > 0) ? max_chunk : BIN_MAX_PAYLOAD;
    if (chunk_limit > BIN_MAX_PAYLOAD)
        chunk_limit = BIN_MAX_PAYLOAD;
    size_t rsp_len = 0;

    switch (type) {
    case CMD_ID:
        build_rsp_id(rsp_buf, &rsp_len);
        break;
    case CMD_STATUS:
        build_rsp_status(rsp_buf, &rsp_len);
        break;
    case CMD_DIAG:
        build_rsp_diag(rsp_buf, &rsp_len);
        break;
    case CMD_SELFTEST:
        build_rsp_selftest(rsp_buf, &rsp_len, 0);  /* pass */
        break;
    case CMD_CLEAR_ERRORS:
    case CMD_SET:
    case CMD_SAVE_CFG:
    case CMD_LOAD_CFG:
    case CMD_FACTORY_RESET:
    case CMD_START_RECORD:
    case CMD_STOP_RECORD:
    case CMD_DEL_SHOT:
    case CMD_FORMAT_STORAGE:
    case CMD_SPI_READ:
    case CMD_SPI_WRITE:
    case CMD_OTA_START:
        build_rsp_status(rsp_buf, &rsp_len);
        break;
    case CMD_GET_CFG:
        build_rsp_cfg(rsp_buf, &rsp_len);
        break;
    case CMD_BUS_SCAN:
        build_rsp_bus_scan(rsp_buf, &rsp_len);
        break;
    case CMD_LIST_SHOTS: {
        size_t nn = 3;
        rsp_buf[nn++] = 1;
        put_le32(&rsp_buf[nn], TEST_SHOT_ID);
        put_le32(&rsp_buf[nn + 4], (uint32_t)TEST_SHOT_SIZE);
        nn += 8;
        rsp_buf[0] = RSP_SHOT_LIST;
        put_le16(&rsp_buf[1], (uint16_t)(nn - 3));
        rsp_len = nn;
        break;
    }
    case CMD_GET_SHOT:
    case CMD_GET_SHOT_CHUNK: {
        uint32_t id = payload && len >= 4 ? get_le32(payload) : 0;
        uint16_t off = (type == CMD_GET_SHOT_CHUNK && payload && len >= 6) ? get_le16(&payload[4]) : 0;
        if (id != TEST_SHOT_ID) {
            build_rsp_status(rsp_buf, &rsp_len);
            break;
        }
        if (off >= TEST_SHOT_SIZE) {
            build_rsp_status(rsp_buf, &rsp_len);
            break;
        }
        size_t chunk = TEST_SHOT_SIZE - off;
        if (chunk > chunk_limit)
            chunk = chunk_limit;
        if (chunk > rsp_buf_size - 3)
            chunk = rsp_buf_size - 3;
        if (chunk > 0) {
            test_shot_fill(&rsp_buf[3], off, chunk);
            rsp_buf[0] = RSP_SHOT;
            put_le16(&rsp_buf[1], (uint16_t)chunk);
            rsp_len = 3 + chunk;
        } else {
            build_rsp_status(rsp_buf, &rsp_len);
        }
        break;
    }
    default:
        build_rsp_status(rsp_buf, &rsp_len);
        break;
    }
    return rsp_len;
}
