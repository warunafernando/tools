/**
 * BLE Binary Frame Parser
 * Type (1) + Length (2 LE) + Payload
 */

#ifndef BLE_PARSER_H
#define BLE_PARSER_H

#include <stdint.h>
#include <stddef.h>

// Callback when a complete frame is received
// Returns bytes consumed (or 0 to reject)
typedef void (*ble_frame_handler_t)(uint8_t type, const uint8_t *payload, uint16_t len);

void ble_parser_init(ble_frame_handler_t handler);
void ble_parser_feed(const uint8_t *data, size_t len);

// Send a response frame over BLE
void ble_send_frame(uint8_t type, const uint8_t *payload, uint16_t len);

// Setup: call after BLE init, pass NUS TX characteristic
void ble_parser_setup(void *tx_char);

#endif /* BLE_PARSER_H */
