/**
 * SPI bus driver for XIAO ESP32-C6 — LSM6DSOX (CS0), ADXL375 (CS1), W25Q64 (CS2).
 * Same protocol as nRF: mode 3 for LSM6/ADXL (reg | 0x80 read), mode 0 for W25Q (cmd 0x9F JEDEC).
 */
#include "spi_bus.h"
#include "driver/spi_master.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include <string.h>

static const char *TAG = "spi_bus";

/* XIAO ESP32-C6 pinout (Seeed wiki): D8=SCK, D9=MISO, D10=MOSI, D2/D3/D4=CS */
#define PIN_SPI_MOSI  18   /* D10 MOSI */
#define PIN_SPI_MISO  20   /* D9  MISO */
#define PIN_SPI_SCLK  19   /* D8  SCK  */
#define PIN_CS_LSM6   2    /* D2  LSM6DSOX */
#define PIN_CS_ADXL   21   /* D3  ADXL375 */
#define PIN_CS_FLASH  22   /* D4  W25Q64 */

#define SPI_FREQ_HZ   1000000
#define SPI_MAX_TRANSFER  (256)

static spi_device_handle_t s_lsm6;
static spi_device_handle_t s_adxl;
static spi_device_handle_t s_flash;
static bool s_inited;

static int do_transfer(spi_device_handle_t dev, const uint8_t *tx, uint8_t *rx, size_t len) {
    if (len == 0 || len > SPI_MAX_TRANSFER || !tx) return -1;
    spi_transaction_t t = { 0 };
    t.length = len * 8;
    t.tx_buffer = tx;
    t.rx_buffer = rx;
    if (spi_device_polling_transmit(dev, &t) != ESP_OK) return -1;
    return 0;
}

int spi_bus_init(void) {
    if (s_inited) return 0;
    spi_bus_config_t bus = {
        .mosi_io_num = PIN_SPI_MOSI,
        .miso_io_num = PIN_SPI_MISO,
        .sclk_io_num = PIN_SPI_SCLK,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = SPI_MAX_TRANSFER,
    };
    if (spi_bus_initialize(SPI2_HOST, &bus, SPI_DMA_DISABLED) != ESP_OK) {
        ESP_LOGE(TAG, "spi_bus_initialize failed");
        return -1;
    }
    /* LSM6: mode 3, CS = D2 */
    spi_device_interface_config_t dev_lsm6 = {
        .clock_speed_hz = SPI_FREQ_HZ,
        .mode = 3,
        .spics_io_num = PIN_CS_LSM6,
        .queue_size = 1,
    };
    if (spi_bus_add_device(SPI2_HOST, &dev_lsm6, &s_lsm6) != ESP_OK) {
        ESP_LOGE(TAG, "add LSM6 failed");
        spi_bus_free(SPI2_HOST);
        return -1;
    }
    /* ADXL: mode 3, CS = D3 */
    spi_device_interface_config_t dev_adxl = {
        .clock_speed_hz = SPI_FREQ_HZ,
        .mode = 3,
        .spics_io_num = PIN_CS_ADXL,
        .queue_size = 1,
    };
    if (spi_bus_add_device(SPI2_HOST, &dev_adxl, &s_adxl) != ESP_OK) {
        ESP_LOGE(TAG, "add ADXL failed");
        spi_bus_remove_device(s_lsm6);
        spi_bus_free(SPI2_HOST);
        return -1;
    }
    /* W25Q64: mode 0, CS = D4 */
    spi_device_interface_config_t dev_flash = {
        .clock_speed_hz = SPI_FREQ_HZ,
        .mode = 0,
        .spics_io_num = PIN_CS_FLASH,
        .queue_size = 1,
    };
    if (spi_bus_add_device(SPI2_HOST, &dev_flash, &s_flash) != ESP_OK) {
        ESP_LOGE(TAG, "add W25Q64 failed");
        spi_bus_remove_device(s_adxl);
        spi_bus_remove_device(s_lsm6);
        spi_bus_free(SPI2_HOST);
        return -1;
    }
    s_inited = true;
    return 0;
}

static spi_device_handle_t dev_for_cs(uint8_t cs_index) {
    switch (cs_index) {
    case SPI_CS_LSM6:  return s_lsm6;
    case SPI_CS_ADXL:  return s_adxl;
    case SPI_CS_FLASH: return s_flash;
    default: return NULL;
    }
}

int spi_bus_transfer(uint8_t cs_index, const uint8_t *tx, uint8_t *rx, size_t len, uint8_t mode) {
    if (!s_inited || cs_index > 2) return -1;
    spi_device_handle_t dev = dev_for_cs(cs_index);
    if (!dev) return -1;
    (void)mode; /* each device has fixed mode in add_device */
    return do_transfer(dev, tx, rx, len);
}

int spi_bus_chip_read(uint8_t cs_index, uint8_t reg, uint8_t *out, size_t len) {
    if (cs_index > 1 || !out || len == 0 || len > 240) return -1;
    uint8_t tx[256];
    uint8_t rx[256];
    tx[0] = reg | 0x80;  /* read bit */
    memset(&tx[1], 0, len);
    int ret = spi_bus_transfer(cs_index, tx, rx, 1 + len, SPI_BUS_MODE_3);
    if (ret != 0) return ret;
    memcpy(out, &rx[1], len);
    return 0;
}

int spi_bus_chip_write(uint8_t cs_index, uint8_t reg, const uint8_t *data, size_t len) {
    if (cs_index > 1 || !data || len > 239) return -1;
    uint8_t tx[256];
    uint8_t rx[256];
    tx[0] = reg & 0x7F;
    memcpy(&tx[1], data, len);
    memset(rx, 0, 1 + len);
    return spi_bus_transfer(cs_index, tx, rx, 1 + len, SPI_BUS_MODE_3);
}
