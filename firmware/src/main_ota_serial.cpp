/**
 * SmartBall OTA Serial - BLE + Serial OTA receiver
 * OTA over COM port: send CMD_OTA_START, CMD_OTA_DATA, CMD_OTA_FINISH
 * LED: slow blink = idle, fast blink = OTA receiving
 */
#include <Arduino.h>
#include <ArduinoBLE.h>
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

static int ota_send_serial(uint8_t type, const uint8_t *payload, uint16_t len) {
    Serial.write(type);
    Serial.write((uint8_t)(len & 0xFF));
    Serial.write((uint8_t)(len >> 8));
    if (payload && len) Serial.write(payload, len);
    Serial.flush();
    return 0;
}

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

    Serial.begin(115200);
    delay(500);

    ota_init(ota_send_serial);

    if (!BLE.begin()) {
        while (1) {
            digitalWrite(LED_BUILTIN, HIGH); delay(100);
            digitalWrite(LED_BUILTIN, LOW);  delay(100);
        }
    }

    BLE.setLocalName("SmartBall");
    nus.addCharacteristic(txChar);
    nus.addCharacteristic(rxChar);
    BLE.addService(nus);
    BLE.advertise();
}

void loop() {
    BLE.poll();

    // Serial OTA: feed incoming bytes to OTA parser
    while (Serial.available()) {
        uint8_t b = Serial.read();
        if (s_serial_len < sizeof(s_serial_buf)) {
            s_serial_buf[s_serial_len++] = b;
        }
        if (s_serial_len >= 3) {
            uint16_t paylen = s_serial_buf[1] | (s_serial_buf[2] << 8);
            if (s_serial_len >= 3 + paylen) {
                ota_feed(s_serial_buf, s_serial_len);
                s_serial_len = 0;
            }
        }
    }
    if (s_serial_len >= sizeof(s_serial_buf)) s_serial_len = 0;

    // LED: fast blink during OTA, slow blink idle
    uint32_t ms = millis();
    bool fast = (ota_get_state() == OTA_RECEIVING || ota_get_state() == OTA_VERIFYING);
    uint32_t period = fast ? 100 : 1000;
    digitalWrite(LED_BUILTIN, ((ms / period) % 2) ? HIGH : LOW);

    delay(10);
}
