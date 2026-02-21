/**
 * SmartBall BLE Binary Protocol v2
 * Message IDs and frame constants
 */

#ifndef PROTOCOL_H
#define PROTOCOL_H

#include <stdint.h>

// Frame header: Type (1) + Length (2 LE) + Payload
#define FRAME_HEADER_SIZE 3
#define MAX_PAYLOAD_SIZE 512
#define MAX_FRAME_SIZE (FRAME_HEADER_SIZE + MAX_PAYLOAD_SIZE)

// Commands (request)
#define CMD_GET_ID     0x80
#define CMD_GET_STATUS 0x85
#define CMD_SET_STREAM 0x87

// Response messages
#define RSP_ID         0x81
#define MSG_ACCEL      0x84
#define RSP_STATUS     0x86
#define MSG_GYRO       0x89

// OTA commands
#define CMD_OTA_START   0x10
#define CMD_OTA_DATA    0x11
#define CMD_OTA_FINISH  0x12
#define CMD_OTA_ABORT   0x13
#define CMD_OTA_STATUS  0x16
#define CMD_OTA_CONFIRM 0x17
#define CMD_OTA_REBOOT  0x18
#define CMD_OTA_GET_LOG 0x19

// OTA response (type 0x90) payload subtype / errors
#define RSP_OTA_OK_START       0x00
#define RSP_OTA_OK_FINISH      0x01
#define RSP_OTA_ERR_SIZE       0x02
#define RSP_OTA_ERR_SIZE_MISMATCH 0x03
#define RSP_OTA_ERR_CHUNK      0x04
#define RSP_OTA_ERR_BAD_MAGIC  0x05
#define RSP_OTA_ERR_CHUNK_CRC  0x06
#define RSP_OTA_ERR_BAD_OFFSET 0x07
#define RSP_OTA_ERR_CRC_MISMATCH 0x08

// OTA progress / ready (device -> host)
#define MSG_OTA_PROGRESS 0x91   // payload: offset (4 bytes) erase progress
#define MSG_OTA_READY    0x92   // payload: empty or 0 = ready for OTA_DATA

#define RSP_OTA 0x90

// Device states
#define DEV_STATE_BOOT      0
#define DEV_STATE_IDLE      1
#define DEV_STATE_ARMED     2
#define DEV_STATE_RECORDING 3
#define DEV_STATE_FLUSHING  4
#define DEV_STATE_OTA       5
#define DEV_STATE_ERROR     6

// IMU source
#define IMU_SOURCE_INTERNAL  0
#define IMU_SOURCE_LSM6_SPI  1
#define IMU_SOURCE_AUTO      2

// RSP_STATUS payload size
#define RSP_STATUS_SIZE 48

// Shot file format v3
#define SHOT_MAGIC "SVTSHOT3"
#define SHOT_VERSION 3

#endif /* PROTOCOL_H */
