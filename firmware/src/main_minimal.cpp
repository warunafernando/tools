/**
 * SmartBall MINIMAL TEST - BLE only, no IMU, no selftest
 * LED blinks slowly (1 sec on, 1 sec off) when running
 * Use: rename to main.cpp and build, or add to platformio as alternate env
 */
#include <Arduino.h>
#include <ArduinoBLE.h>

#define NUS_SERVICE "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_TX      "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"
#define NUS_RX      "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"

BLEService nus(NUS_SERVICE);
BLECharacteristic txChar(NUS_TX, BLERead | BLENotify, 512);
BLECharacteristic rxChar(NUS_RX, BLEWrite | BLEWriteWithoutResponse, 512);

void setup() {
    pinMode(LED_BUILTIN, OUTPUT);
    digitalWrite(LED_BUILTIN, LOW);

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
    // Heartbeat: 1 sec on, 1 sec off
    uint32_t s = millis() / 1000;
    digitalWrite(LED_BUILTIN, (s % 2) ? HIGH : LOW);
    delay(100);
}
