/**
 * SmartBall OTA Serial + BLE
 * OTA over COM port AND over BLE NUS
 * LED: slow blink = idle, fast blink = OTA receiving
 */
#include <Arduino.h>
#include <ArduinoBLE.h>
#include <cstring>
#include "protocol.h"
#include "ota.h"

#define NUS_SERVICE "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_TX      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX      "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

BLEService nus(NUS_SERVICE);
BLECharacteristic txChar(NUS_TX, BLERead | BLENotify, 512);
BLECharacteristic rxChar(NUS_RX, BLEWrite | BLEWriteWithoutResponse, 512);

static uint8_t s_serial_buf[520];
static uint16_t s_serial_len = 0;
static uint8_t s_ble_buf[520];
static uint16_t s_ble_len = 0;

static int ota_send_serial(uint8_t type, const uint8_t *payload, uint16_t len) {
    Serial.write(type);
    Serial.write((uint8_t)(len & 0xFF));
    Serial.write((uint8_t)(len >> 8));
    if (payload && len) Serial.write(payload, len);
    Serial.flush();
    return 0;
}

static int ota_send_ble(uint8_t type, const uint8_t *payload, uint16_t len) {
    if (!txChar.subscribed()) return -1;
    uint8_t buf[520];
    buf[0] = type;
    buf[1] = (uint8_t)(len & 0xFF);
    buf[2] = (uint8_t)(len >> 8);
    if (payload && len) memcpy(buf + 3, payload, len);
    txChar.writeValue(buf, 3 + len);
    return 0;
}

static int ota_send_both(uint8_t type, const uint8_t *payload, uint16_t len) {
    ota_send_serial(type, payload, len);
    ota_send_ble(type, payload, len);
    return 0;
}

static void ota_yield_cb(void) {
    BLE.poll();
}

void onBleWritten(BLEDevice central, BLECharacteristic characteristic) {
    const uint8_t *data = rxChar.value();
    size_t len = rxChar.valueLength();
    for (size_t i = 0; i < len && s_ble_len < sizeof(s_ble_buf); i++) {
        s_ble_buf[s_ble_len++] = data[i];
    }
}

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    Serial.begin(115200);
    delay(500);

    ota_init(ota_send_both);
    ota_set_yield(ota_yield_cb);

    // If we booted after OTA: 30s confirm timer; if no CONFIRM in 30s -> rollback
    (void)ota_is_pending_confirm();  // checked in loop

    if (!BLE.begin()) {
        while (1) {
            digitalWrite(LED_BUILTIN, HIGH); delay(100);
            digitalWrite(LED_BUILTIN, LOW);  delay(100);
        }
    }

    BLE.setLocalName("SmartBall");
    nus.addCharacteristic(txChar);
    nus.addCharacteristic(rxChar);
    rxChar.setEventHandler(BLEWritten, onBleWritten);
    BLE.addService(nus);
    BLE.advertise();
}

#define PENDING_CONFIRM_TIMEOUT_MS 30000
static uint32_t s_pending_confirm_start = 0;

void loop() {
    BLE.poll();
    ota_poll();

    if (ota_is_pending_confirm()) {
        if (s_pending_confirm_start == 0) s_pending_confirm_start = millis();
        if (millis() - s_pending_confirm_start >= PENDING_CONFIRM_TIMEOUT_MS) {
            ota_rollback_pending();
            s_pending_confirm_start = 0;
        }
    } else {
        s_pending_confirm_start = 0;
    }

    // Serial OTA
    while (Serial.available()) {
        uint8_t b = Serial.read();
        if (s_serial_len < sizeof(s_serial_buf)) s_serial_buf[s_serial_len++] = b;
        if (s_serial_len >= 3) {
            uint16_t paylen = s_serial_buf[1] | (s_serial_buf[2] << 8);
            if (s_serial_len >= 3 + paylen) {
                ota_feed(s_serial_buf, s_serial_len);
                s_serial_len = 0;
            }
        }
    }
    if (s_serial_len >= sizeof(s_serial_buf)) s_serial_len = 0;

    // BLE OTA
    if (s_ble_len >= 3) {
        uint16_t paylen = s_ble_buf[1] | (s_ble_buf[2] << 8);
        if (s_ble_len >= 3 + paylen) {
            ota_feed(s_ble_buf, s_ble_len);
            s_ble_len = 0;
        }
    }
    if (s_ble_len >= sizeof(s_ble_buf)) s_ble_len = 0;

    // LED: fast = OTA active
    uint32_t ms = millis();
    ota_state_t st = ota_get_state();
    bool fast = (st == OTA_PREPARE_ERASE || st == OTA_READY_FOR_DATA || st == OTA_RECEIVING || st == OTA_VERIFYING);
    uint32_t period = fast ? 100 : 1000;
    digitalWrite(LED_BUILTIN, ((ms / period) % 2) ? HIGH : LOW);

    delay(10);
}
