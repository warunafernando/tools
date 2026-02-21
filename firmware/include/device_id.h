/**
 * Device Identity - FICR DEVICEID, serial, RSP_ID
 */

#ifndef DEVICE_ID_H
#define DEVICE_ID_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define UID_SIZE 8   // 64-bit DEVICEID

typedef struct {
    uint16_t fw_version;
    uint8_t  protocol_version;
    uint8_t  hw_revision;
    uint8_t  uid_len;
    uint8_t  uid[UID_SIZE];
} rsp_id_t;

// Read 64-bit device ID from FICR
void device_id_read_ficr(uint8_t *uid_out, uint8_t *uid_len);

// Fill RSP_ID structure
void device_id_fill_rsp(rsp_id_t *rsp);

#ifdef __cplusplus
}
#endif

#endif /* DEVICE_ID_H */
