/**
 * Global state definitions
 */

#include "globals.h"

uint32_t g_uptime_ms = 0;
uint32_t g_samples_recorded = 0;
uint16_t g_gyro_saturation = 0;
uint8_t g_device_state = 0;  // BOOT
uint8_t g_imu_source_active = 0;  // INTERNAL_IMU
uint8_t g_active_slot = 0;
uint8_t g_pending_slot = 0xFF;
uint32_t g_storage_used = 0;
uint32_t g_storage_free = 0;

bool g_stream_accel = false;
bool g_stream_gyro = false;
