/**
 * Device Identity - FICR DEVICEID
 */

#include "device_id.h"

// nRF52840 FICR INFO_DEVICEID at 0x10000060 (64-bit)
#define FICR_DEVICEID ((volatile const uint32_t *)0x10000060)

void device_id_read_ficr(uint8_t *uid_out, uint8_t *uid_len) {
    uint32_t id0 = FICR_DEVICEID[0];
    uint32_t id1 = FICR_DEVICEID[1];
    uid_out[0] = (uint8_t)(id0 >> 0);
    uid_out[1] = (uint8_t)(id0 >> 8);
    uid_out[2] = (uint8_t)(id0 >> 16);
    uid_out[3] = (uint8_t)(id0 >> 24);
    uid_out[4] = (uint8_t)(id1 >> 0);
    uid_out[5] = (uint8_t)(id1 >> 8);
    uid_out[6] = (uint8_t)(id1 >> 16);
    uid_out[7] = (uint8_t)(id1 >> 24);
    *uid_len = UID_SIZE;
}

void device_id_fill_rsp(rsp_id_t *rsp) {
    rsp->fw_version = SMARTBALL_FW_VERSION;
    rsp->protocol_version = SMARTBALL_PROTOCOL_VERSION;
    rsp->hw_revision = SMARTBALL_HW_REVISION;
    device_id_read_ficr(rsp->uid, &rsp->uid_len);
}
