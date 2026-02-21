/**
 * RSP_STATUS (0x86) - 48 bytes
 * Health and device status
 */

#ifndef STATUS_H
#define STATUS_H

#include <stdint.h>
#include "protocol.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct __attribute__((packed)) {
    uint32_t uptime_ms;
    uint8_t  last_error;
    uint8_t  error_flags;
    uint8_t  device_state;
    uint8_t  imu_source_active;
    uint8_t  active_slot;
    uint8_t  pending_slot;
    uint32_t samples_recorded;
    uint16_t gyro_saturation_counter;
    uint16_t _pad1;
    uint32_t storage_used;
    uint32_t storage_free;
    uint16_t battery_voltage;   // mV
    int16_t  temperature;       // 0.25 °C
    uint8_t  reset_reason;
    uint8_t  _pad2;
    uint16_t firmware_build_id;
    uint8_t  _reserved[14];     // pad to 48 bytes
} rsp_status_t;

void status_fill(rsp_status_t *s);

#ifdef __cplusplus
}
#endif

#endif /* STATUS_H */
