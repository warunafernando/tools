/**
 * Health system - last_error, error_flags, reset_reason, SELFTEST
 */

#ifndef HEALTH_H
#define HEALTH_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define HEALTH_OK        0
#define HEALTH_ERR_IMU   1
#define HEALTH_ERR_MEM   2
#define HEALTH_ERR_BLE   3
#define HEALTH_ERR_FLASH 4

#define RESET_REASON_POR     0
#define RESET_REASON_PIN     1
#define RESET_REASON_WDT     2
#define RESET_REASON_SOFT    3
#define RESET_REASON_LOCKUP  4

void health_init(void);
void health_set_last_error(uint8_t err);
void health_set_error_flag(uint8_t flag);
void health_clear_error_flag(uint8_t flag);
uint8_t health_get_last_error(void);
uint8_t health_get_error_flags(void);
uint8_t health_get_reset_reason(void);

// SELFTEST: returns 0 on pass, non-zero on fail
int health_selftest_imu(void);
int health_selftest_mem(void);
int health_selftest_ble(void);
int health_selftest_all(void);

#ifdef __cplusplus
}
#endif

#endif /* HEALTH_H */
