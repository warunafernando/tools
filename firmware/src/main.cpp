/**
 * SmartBall XIAO nRF52840 Sense - Main
 */

#include <Arduino.h>
#include <ArduinoBLE.h>
#include "protocol.h"
#include "device_id.h"
#include "status.h"
#include "health.h"
#include "globals.h"
#include "ble_parser.h"
#include "imu_driver.h"

// NUS UUIDs
#define NUS_SERVICE_UUID     "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_TX_CHAR_UUID     "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX_CHAR_UUID     "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_MAX_PACKET       512

BLEService nusService(NUS_SERVICE_UUID);
BLECharacteristic txChar(NUS_TX_CHAR_UUID, BLERead | BLENotify, NUS_MAX_PACKET);
BLECharacteristic rxChar(NUS_RX_CHAR_UUID, BLEWrite | BLEWriteWithoutResponse, NUS_MAX_PACKET);

static uint32_t s_last_status_ms = 0;
static uint32_t s_last_debug_ms = 0;
#define STATUS_INTERVAL_MS 1000
#define DEBUG_INTERVAL_MS  10000  // debug print every 10s

void onRxWritten(BLEDevice central, BLECharacteristic characteristic) {
    const uint8_t *data = rxChar.value();
    size_t len = rxChar.valueLength();
    ble_parser_feed(data, len);
}

#define DBG(x) do { Serial.print(x); Serial.flush(); } while(0)
#define DBGLN(x) do { Serial.println(x); Serial.flush(); } while(0)

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    Serial.begin(115200);
    delay(500);
    DBGLN("[1] SmartBall XIAO Sense - boot");

    health_init();
    g_device_state = DEV_STATE_BOOT;
    DBGLN("[2] health_init OK");

    // SELFTEST
    int st = health_selftest_all();
    if (st != 0) {
        health_set_last_error(HEALTH_ERR_IMU);
        g_device_state = DEV_STATE_ERROR;
        Serial.print("[ERR] SELFTEST failed: ");
        Serial.println(st);
        Serial.flush();
        // 1 short blink = SELFTEST failed
        while (1) {
            digitalWrite(LED_BUILTIN, HIGH); delay(100);
            digitalWrite(LED_BUILTIN, LOW);  delay(1200);
        }
    }
    DBGLN("[3] SELFTEST OK");

    if (!imu_init()) {
        health_set_last_error(HEALTH_ERR_IMU);
        g_device_state = DEV_STATE_ERROR;
        DBGLN("[ERR] IMU init failed");
        // 2 short blinks = IMU failed
        while (1) {
            digitalWrite(LED_BUILTIN, HIGH); delay(100);
            digitalWrite(LED_BUILTIN, LOW);  delay(100);
            digitalWrite(LED_BUILTIN, HIGH); delay(100);
            digitalWrite(LED_BUILTIN, LOW);  delay(1200);
        }
    }
    DBGLN("[4] IMU init OK");

    if (!BLE.begin()) {
        health_set_last_error(HEALTH_ERR_BLE);
        g_device_state = DEV_STATE_ERROR;
        DBGLN("[ERR] BLE init failed");
        // 3 short blinks = BLE failed
        while (1) {
            for (int i = 0; i < 3; i++) {
                digitalWrite(LED_BUILTIN, HIGH); delay(100);
                digitalWrite(LED_BUILTIN, LOW);  delay(100);
            }
            delay(1200);
        }
    }
    DBGLN("[5] BLE init OK");

    BLE.setLocalName("SmartBall");
    BLE.setDeviceName("SmartBall");
    nusService.addCharacteristic(txChar);
    nusService.addCharacteristic(rxChar);
    rxChar.setEventHandler(BLEWritten, onRxWritten);
    BLE.addService(nusService);
    BLE.advertise();

    ble_parser_setup(&txChar);
    g_device_state = DEV_STATE_IDLE;
    g_imu_source_active = IMU_SOURCE_INTERNAL;

    DBGLN("[6] BLE advertising as SmartBall");
    digitalWrite(LED_BUILTIN, HIGH);  // solid = running
}

void loop() {
    BLE.poll();

    uint32_t now = millis();
    g_uptime_ms = now;

    // Periodic RSP_STATUS
    if (now - s_last_status_ms >= STATUS_INTERVAL_MS) {
        s_last_status_ms = now;
        rsp_status_t s;
        status_fill(&s);
        ble_send_frame(RSP_STATUS, (const uint8_t *)&s, RSP_STATUS_SIZE);
    }

    // Debug heartbeat
    if (now - s_last_debug_ms >= DEBUG_INTERVAL_MS) {
        s_last_debug_ms = now;
        Serial.print("[DBG] uptime=");
        Serial.print(now);
        Serial.print(" state=");
        Serial.println(g_device_state);
        Serial.flush();
    }

    // Streaming IMU (if enabled)
    if (g_stream_accel || g_stream_gyro) {
        imu_sample_t sample;
        if (imu_read(&sample)) {
            if (g_stream_accel) {
                uint8_t buf[4 + 12];  // t_ms + ax,ay,az
                memcpy(buf, &sample.t_ms, 4);
                memcpy(buf + 4, &sample.ax, 4);
                memcpy(buf + 8, &sample.ay, 4);
                memcpy(buf + 12, &sample.az, 4);
                ble_send_frame(MSG_ACCEL, buf, 16);
            }
            if (g_stream_gyro) {
                uint8_t buf[4 + 12];  // t_ms + gx,gy,gz
                memcpy(buf, &sample.t_ms, 4);
                memcpy(buf + 4, &sample.gx, 4);
                memcpy(buf + 8, &sample.gy, 4);
                memcpy(buf + 12, &sample.gz, 4);
                ble_send_frame(MSG_GYRO, buf, 16);
            }
        }
    }

    delay(10);
}
