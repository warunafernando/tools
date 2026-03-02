/**
 * SmartBall Binary Protocol — ESP32-C6 WiFi implementation.
 * Same frame format as nRF BLE: Type (1) | Length (2 LE) | Payload (N)
 * Compatible with ble_binary_client / wifi_binary_client.
 */
#ifndef BINARY_PROTOCOL_H
#define BINARY_PROTOCOL_H

#include <stdint.h>
#include <stddef.h>

#define BIN_FRAME_HEADER_SIZE 3
#define BIN_RX_BUF_SIZE       256
#define BIN_MAX_PAYLOAD       (BIN_RX_BUF_SIZE - BIN_FRAME_HEADER_SIZE)

#define TEST_SHOT_ID   0xAAAAAAAAU
#define TEST_SHOT_SIZE 15360U

/* Protocol versions (match nRF) */
#define PROTOCOL_VERSION  2
#define FW_VERSION        0x0100   /* 1.0 */
#define HW_REVISION       2        /* ESP32-C6 = rev 2 */

/* Command IDs (host -> device) — match ble_binary.h */
#define CMD_ID            0x01
#define CMD_STATUS        0x02
#define CMD_DIAG          0x03
#define CMD_SELFTEST      0x04
#define CMD_CLEAR_ERRORS  0x05
#define CMD_SET           0x06
#define CMD_GET_CFG       0x07
#define CMD_SAVE_CFG      0x08
#define CMD_LOAD_CFG      0x09
#define CMD_FACTORY_RESET 0x0A
#define CMD_START_RECORD  0x0B
#define CMD_STOP_RECORD   0x0C
#define CMD_LIST_SHOTS    0x0D
#define CMD_GET_SHOT      0x0E
#define CMD_DEL_SHOT      0x0F
#define CMD_FORMAT_STORAGE 0x10
#define CMD_BUS_SCAN      0x11
#define CMD_GET_SHOT_CHUNK 0x12
#define CMD_SPI_READ      0x13
#define CMD_SPI_WRITE     0x14
#define CMD_OTA_START     0x15     /* ESP32: OTA over HTTP (stub) */

/* Response IDs (device -> host) */
#define RSP_ID        0x81
#define RSP_STATUS    0x86
#define RSP_DIAG      0x87
#define RSP_SELFTEST  0x88
#define RSP_BUS_SCAN  0x89
#define RSP_SHOT      0x8A
#define RSP_CFG       0x8B
#define RSP_SHOT_LIST 0x8C
#define RSP_SPI_DATA  0x8D

/**
 * Optional: provide current WiFi RSSI for RSP_STATUS/RSP_DIAG.
 * Implement in main.c; default -128 if not connected.
 */
int binary_get_rssi(int *rssi);

int binary_parse_frame(const uint8_t *buf, size_t len,
                       uint8_t *out_type, const uint8_t **out_payload, uint16_t *out_len);

size_t binary_process_cmd(uint8_t type, const uint8_t *payload, uint16_t len,
                          uint8_t *rsp_buf, size_t rsp_buf_size, uint16_t max_chunk);

#endif
