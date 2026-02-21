/**
 * Global state variables
 */

#ifndef GLOBALS_H
#define GLOBALS_H

#include <stdint.h>

extern uint32_t g_uptime_ms;
extern uint32_t g_samples_recorded;
extern uint16_t g_gyro_saturation;
extern uint8_t g_device_state;
extern uint8_t g_imu_source_active;
extern uint8_t g_active_slot;
extern uint8_t g_pending_slot;
extern uint32_t g_storage_used;
extern uint32_t g_storage_free;

extern bool g_stream_accel;
extern bool g_stream_gyro;

#endif /* GLOBALS_H */
