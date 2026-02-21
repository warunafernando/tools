/**
 * Health system
 */

#include "health.h"
#include "imu_driver.h"
#include "Arduino.h"
#include "nrf.h"

static uint8_t s_last_error = 0;
static uint8_t s_error_flags = 0;
static uint8_t s_reset_reason = RESET_REASON_POR;

void health_init(void) {
    // Read reset reason from NRF_POWER
    uint32_t reason = NRF_POWER->RESETREAS;
    if (reason & POWER_RESETREAS_DOG_Msk) {
        s_reset_reason = RESET_REASON_WDT;
    } else if (reason & POWER_RESETREAS_SREQ_Msk) {
        s_reset_reason = RESET_REASON_SOFT;
    } else if (reason & POWER_RESETREAS_LOCKUP_Msk) {
        s_reset_reason = RESET_REASON_LOCKUP;
    } else if (reason & POWER_RESETREAS_RESETPIN_Msk) {
        s_reset_reason = RESET_REASON_PIN;
    } else {
        s_reset_reason = RESET_REASON_POR;
    }
    NRF_POWER->RESETREAS = 0xFFFFFFFF;  // Clear
}

void health_set_last_error(uint8_t err) { s_last_error = err; }
void health_set_error_flag(uint8_t flag) { s_error_flags |= (1u << flag); }
void health_clear_error_flag(uint8_t flag) { s_error_flags &= ~(1u << flag); }
uint8_t health_get_last_error(void) { return s_last_error; }
uint8_t health_get_error_flags(void) { return s_error_flags; }
uint8_t health_get_reset_reason(void) { return s_reset_reason; }

int health_selftest_imu(void) {
    return imu_init() ? 0 : -1;
}

int health_selftest_mem(void) {
    // Simple heap check - allocate and free
    void *p = malloc(64);
    if (!p) return -1;
    free(p);
    return 0;
}

int health_selftest_ble(void) {
    // Placeholder - BLE stack check
    return 0;
}

int health_selftest_all(void) {
    if (health_selftest_imu() != 0) return -1;
    if (health_selftest_mem() != 0) return -2;
    if (health_selftest_ble() != 0) return -3;
    return 0;
}
