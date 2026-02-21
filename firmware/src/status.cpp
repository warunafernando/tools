/**
 * RSP_STATUS filling
 */

#include "status.h"
#include "health.h"
#include "globals.h"
#include <cstring>
#include "Arduino.h"

extern uint32_t g_uptime_ms;
extern uint32_t g_samples_recorded;
extern uint16_t g_gyro_saturation;
extern uint8_t g_device_state;
extern uint8_t g_imu_source_active;
extern uint8_t g_active_slot;
extern uint8_t g_pending_slot;
extern uint32_t g_storage_used;
extern uint32_t g_storage_free;

void status_fill(rsp_status_t *s) {
    memset(s, 0, sizeof(*s));
    s->uptime_ms = g_uptime_ms;
    s->last_error = health_get_last_error();
    s->error_flags = health_get_error_flags();
    s->device_state = g_device_state;
    s->imu_source_active = g_imu_source_active;
    s->active_slot = g_active_slot;
    s->pending_slot = g_pending_slot;
    s->samples_recorded = g_samples_recorded;
    s->gyro_saturation_counter = g_gyro_saturation;
    s->_pad1 = 0;
    s->storage_used = g_storage_used;
    s->storage_free = g_storage_free;
    s->battery_voltage = 0;  // Placeholder - no battery sense on USB
    s->temperature = 0;      // Placeholder - will add nRF temp sensor
    s->reset_reason = health_get_reset_reason();
    s->_pad2 = 0;
    s->firmware_build_id = SMARTBALL_FW_VERSION;
}
