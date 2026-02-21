/**
 * BLE Binary Frame Parser
 */

#include "ble_parser.h"
#include "protocol.h"
#include <cstring>
#include "device_id.h"
#include "status.h"
#include "health.h"
#include "globals.h"
#include "Arduino.h"
#include <ArduinoBLE.h>

static ble_frame_handler_t s_handler = NULL;
static uint8_t s_rx_buf[MAX_FRAME_SIZE];
static uint16_t s_rx_len = 0;

// BLE TX - write to NUS characteristic
static BLECharacteristic *s_tx_char = NULL;

void ble_parser_init(ble_frame_handler_t handler) {
    s_handler = handler;
    s_rx_len = 0;
}

void ble_parser_feed(const uint8_t *data, size_t len) {
    for (size_t i = 0; i < len && s_rx_len < MAX_FRAME_SIZE; i++) {
        s_rx_buf[s_rx_len++] = data[i];
        if (s_rx_len >= FRAME_HEADER_SIZE) {
            uint16_t paylen = (uint16_t)s_rx_buf[1] | ((uint16_t)s_rx_buf[2] << 8);
            if (s_rx_len >= FRAME_HEADER_SIZE + paylen) {
                if (s_handler) {
                    s_handler(s_rx_buf[0], s_rx_buf + FRAME_HEADER_SIZE, paylen);
                }
                s_rx_len = 0;
            }
        }
    }
    if (s_rx_len >= MAX_FRAME_SIZE) s_rx_len = 0;
}

void ble_send_frame(uint8_t type, const uint8_t *payload, uint16_t len) {
    if (!s_tx_char || !s_tx_char->subscribed()) return;
    uint8_t buf[MAX_FRAME_SIZE];
    buf[0] = type;
    buf[1] = (uint8_t)(len & 0xFF);
    buf[2] = (uint8_t)(len >> 8);
    if (payload && len > 0 && len <= MAX_PAYLOAD_SIZE) {
        memcpy(buf + FRAME_HEADER_SIZE, payload, len);
    }
    s_tx_char->writeValue(buf, FRAME_HEADER_SIZE + len);
}

void ble_set_tx_characteristic(BLECharacteristic *c) {
    s_tx_char = c;
}

// Command handlers
static void handle_get_id(void) {
    rsp_id_t rsp;
    device_id_fill_rsp(&rsp);
    ble_send_frame(RSP_ID, (const uint8_t *)&rsp, 4 + rsp.uid_len);
}

static void handle_get_status(void) {
    rsp_status_t s;
    status_fill(&s);
    ble_send_frame(RSP_STATUS, (const uint8_t *)&s, RSP_STATUS_SIZE);
}

static void handle_set_stream(uint8_t accel, uint8_t gyro) {
    g_stream_accel = (accel != 0);
    g_stream_gyro = (gyro != 0);
}

static void frame_handler(uint8_t type, const uint8_t *payload, uint16_t len) {
    switch (type) {
        case CMD_GET_ID:
            handle_get_id();
            break;
        case CMD_GET_STATUS:
            handle_get_status();
            break;
        case CMD_SET_STREAM:
            if (len >= 2) handle_set_stream(payload[0], payload[1]);
            break;
        case CMD_OTA_START:
        case CMD_OTA_DATA:
        case CMD_OTA_FINISH:
        case CMD_OTA_ABORT:
        case CMD_OTA_STATUS:
        case CMD_OTA_CONFIRM:
            // OTA handlers - Phase 3
            break;
        default:
            break;
    }
}

// Called from main after BLE setup to register handler and TX char
void ble_parser_setup(void *tx_char) {
    ble_set_tx_characteristic((BLECharacteristic *)tx_char);
    ble_parser_init(frame_handler);
}
