#ifndef MAIN_MAIN_H
#define MAIN_MAIN_H

#include <stddef.h>

/* Write the device's current STA IP to buf (e.g. "192.168.1.100"), null-terminated.
 * Returns 0 on success, -1 if no IP. */
int get_device_ip_string(char *buf, size_t size);

#endif
