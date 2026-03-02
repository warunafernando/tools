/**
 * SPI bus for XIAO ESP32-C6 — same 3 chips as nRF XIAO: LSM6DSOX, ADXL375, W25Q64.
 * CS: D2, D3, D4 (configurable via menuconfig or defaults below).
 */
#ifndef SPI_BUS_H
#define SPI_BUS_H

#include <stddef.h>
#include <stdint.h>

#define SPI_CS_LSM6   0
#define SPI_CS_ADXL   1
#define SPI_CS_FLASH  2

/* SPI mode: 0 = CPOL=0 CPHA=0 (W25Q64), 3 = CPOL=1 CPHA=1 (LSM6, ADXL) */
#define SPI_BUS_MODE_0  0
#define SPI_BUS_MODE_3  3

/**
 * Initialize SPI bus and CS GPIOs. Returns 0 on success, -1 on failure.
 */
int spi_bus_init(void);

/**
 * Full-duplex transfer. cs_index 0=LSM6, 1=ADXL, 2=W25Q64. mode SPI_BUS_MODE_0 or SPI_BUS_MODE_3.
 */
int spi_bus_transfer(uint8_t cs_index, const uint8_t *tx, uint8_t *rx, size_t len, uint8_t mode);

/**
 * Register read (LSM6/ADXL style: reg | 0x80, then len bytes). Uses SPI mode 3.
 * cs_index 0 or 1 only. len max 240.
 */
int spi_bus_chip_read(uint8_t cs_index, uint8_t reg, uint8_t *out, size_t len);

/**
 * Register write (LSM6/ADXL style). Uses SPI mode 3.
 */
int spi_bus_chip_write(uint8_t cs_index, uint8_t reg, const uint8_t *data, size_t len);

#endif /* SPI_BUS_H */
