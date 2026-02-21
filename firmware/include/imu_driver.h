/**
 * Internal IMU driver - LSM6DS3 on XIAO Sense
 */

#ifndef IMU_DRIVER_H
#define IMU_DRIVER_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t t_ms;
    float ax, ay, az;  // g
    float gx, gy, gz;  // rad/s
} imu_sample_t;

bool imu_init(void);
bool imu_read_accel(float *ax, float *ay, float *az);
bool imu_read_gyro(float *gx, float *gy, float *gz);
bool imu_read(imu_sample_t *out);

void imu_set_accel_range(int range_g);   // 2, 4, 8, 16
void imu_set_gyro_range(int range_dps);  // 125, 250, 500, 1000, 2000
void imu_set_sample_rate_hz(int hz);     // e.g. 26, 52, 104, 208, 416

#ifdef __cplusplus
}
#endif

#endif /* IMU_DRIVER_H */
