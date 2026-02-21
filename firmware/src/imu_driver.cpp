/**
 * Internal IMU - LSM6DS3TR-C on XIAO Sense via Adafruit_LSM6DS3TRC
 */

#include "imu_driver.h"
#include "Adafruit_LSM6DS3TRC.h"
#include "Arduino.h"
#include "Wire.h"

static Adafruit_LSM6DS3TRC lsm6ds;
static bool s_initialized = false;

bool imu_init(void) {
    if (s_initialized) return true;
    Wire.begin();
    if (!lsm6ds.begin_I2C(0x6A)) {
        if (!lsm6ds.begin_I2C(0x6B)) {  // try alternate addr
            return false;
        }
    }
    s_initialized = true;
    return true;
}

bool imu_read_accel(float *ax, float *ay, float *az) {
    if (!s_initialized) return false;
    sensors_event_t accel, gyro, temp;
    lsm6ds.getEvent(&accel, &gyro, &temp);
    *ax = accel.acceleration.x / 9.80665f;  // m/s^2 -> g
    *ay = accel.acceleration.y / 9.80665f;
    *az = accel.acceleration.z / 9.80665f;
    return true;
}

bool imu_read_gyro(float *gx, float *gy, float *gz) {
    if (!s_initialized) return false;
    sensors_event_t accel, gyro, temp;
    lsm6ds.getEvent(&accel, &gyro, &temp);
    *gx = gyro.gyro.x;  // rad/s
    *gy = gyro.gyro.y;
    *gz = gyro.gyro.z;
    return true;
}

bool imu_read(imu_sample_t *out) {
    if (!s_initialized || !out) return false;
    sensors_event_t accel, gyro, temp;
    lsm6ds.getEvent(&accel, &gyro, &temp);
    out->t_ms = (uint32_t)millis();
    out->ax = accel.acceleration.x / 9.80665f;
    out->ay = accel.acceleration.y / 9.80665f;
    out->az = accel.acceleration.z / 9.80665f;
    out->gx = gyro.gyro.x;
    out->gy = gyro.gyro.y;
    out->gz = gyro.gyro.z;
    return true;
}

void imu_set_accel_range(int range_g) {
    (void)range_g;
}

void imu_set_gyro_range(int range_dps) {
    (void)range_dps;
}

void imu_set_sample_rate_hz(int hz) {
    (void)hz;
}
