"""Ball Logger firmware prototype (EPIC 1).

Implements:
- SPI bring-up and device detection
- Sampling loop
- Pre-trigger ring buffer
- Threshold trigger on ADXL375
- Simple shot file write with CRC32
"""

import time
import os
import struct
import binascii

import board
import busio
import digitalio


# SPI pins
SPI_SCK = board.D8
SPI_MOSI = board.D10
SPI_MISO = board.D9

# CS pins
CS_LSM6DSOX = board.D2
CS_ADXL375 = board.D3
CS_W25Q64 = board.D4

# LSM6DSOX registers
LSM6DS_WHOAMI_REG = 0x0F
LSM6DS_WHOAMI_OK = (0x69, 0x6A, 0x6C)
LSM6DS_CTRL1_XL = 0x10
LSM6DS_OUTX_L_A = 0x28

# ADXL375 registers
ADXL375_DEVID_REG = 0x00
ADXL375_DEVID_OK = 0xE5
ADXL375_POWER_CTL = 0x2D
ADXL375_DATA_FORMAT = 0x31
ADXL375_BW_RATE = 0x2C
ADXL375_DATAX0 = 0x32

# W25Q64 JEDEC
FLASH_JEDEC_CMD = 0x9F

# Sampling configuration
SAMPLE_RATE_HZ = 200
SAMPLE_PERIOD_S = 1.0 / SAMPLE_RATE_HZ
PRE_TRIGGER_S = 0.25
POST_TRIGGER_S = 0.75
TRIGGER_THRESHOLD_G = 15.0
TRIGGER_DEBOUNCE_SAMPLES = 3


class RingBuffer:
	def __init__(self, capacity):
		self.capacity = capacity
		self.data = [None] * capacity
		self.index = 0
		self.full = False

	def append(self, item):
		self.data[self.index] = item
		self.index = (self.index + 1) % self.capacity
		if self.index == 0:
			self.full = True

	def snapshot(self):
		if not self.full:
			return [x for x in self.data[: self.index] if x is not None]
		return self.data[self.index :] + self.data[: self.index]


class TriggerDetector:
	def __init__(self, threshold_g, debounce_samples):
		self.threshold_g = threshold_g
		self.debounce_samples = debounce_samples
		self.hit_count = 0

	def update(self, x_g, y_g, z_g):
		peak = max(abs(x_g), abs(y_g), abs(z_g))
		if peak >= self.threshold_g:
			self.hit_count += 1
		else:
			self.hit_count = 0
		return self.hit_count >= self.debounce_samples


class StorageEngine:
	def __init__(self, base_dir="/shots"):
		self.base_dir = base_dir
		if self.base_dir.strip("/") not in os.listdir("/"):
			os.mkdir(self.base_dir)

	def _next_filename(self):
		stamp = int(time.monotonic() * 1000)
		return "%s/shot_%d.svtshot" % (self.base_dir, stamp)

	def write_shot(self, samples, sample_rate_hz):
		path = self._next_filename()
		crc = 0
		with open(path, "wb") as f:
			# Header: magic(8), ver(u16), rate(u16), count(u32)
			magic = b"SVTSHOT1"
			header = struct.pack("<8sHHI", magic, 1, sample_rate_hz, len(samples))
			f.write(header)
			crc = binascii.crc32(header, crc)
			
			# Sample payload
			for s in samples:
				# t_ms, lsm_x, lsm_y, lsm_z, adxl_x, adxl_y, adxl_z
				payload = struct.pack("<Iffffff", *s)
				f.write(payload)
				crc = binascii.crc32(payload, crc)
			
			# CRC32 footer
			f.write(struct.pack("<I", crc & 0xFFFFFFFF))
		return path


def init_spi():
	spi = busio.SPI(SPI_SCK, SPI_MOSI, SPI_MISO)
	while not spi.try_lock():
		pass
	spi.configure(baudrate=1_000_000, polarity=1, phase=1)
	spi.unlock()
	return spi


def make_cs(pin):
	cs = digitalio.DigitalInOut(pin)
	cs.direction = digitalio.Direction.OUTPUT
	cs.value = True
	return cs


def spi_read_register(spi, cs, reg_addr):
	rx = bytearray(1)
	while not spi.try_lock():
		pass
	try:
		spi.configure(baudrate=1_000_000, polarity=1, phase=1)
		cs.value = False
		spi.write(bytes([reg_addr | 0x80]))
		spi.readinto(rx)
		cs.value = True
	finally:
		spi.unlock()
	return rx[0]


def spi_write_register(spi, cs, reg_addr, value):
	while not spi.try_lock():
		pass
	try:
		spi.configure(baudrate=1_000_000, polarity=1, phase=1)
		cs.value = False
		spi.write(bytes([reg_addr & 0x7F, value]))
		cs.value = True
	finally:
		spi.unlock()


def spi_read_bytes(spi, cs, reg_addr, num_bytes, mb=False):
	rx = bytearray(num_bytes)
	while not spi.try_lock():
		pass
	try:
		spi.configure(baudrate=1_000_000, polarity=1, phase=1)
		cs.value = False
		read_addr = reg_addr | 0x80
		if mb:
			read_addr |= 0x40
		spi.write(bytes([read_addr]))
		spi.readinto(rx)
		cs.value = True
	finally:
		spi.unlock()
	return rx


def init_lsm6dsox(spi, cs):
	# CTRL1_XL: 104 Hz, +/-4g
	spi_write_register(spi, cs, LSM6DS_CTRL1_XL, 0x40)


def read_lsm6dsox_accel(spi, cs):
	data = spi_read_bytes(spi, cs, LSM6DS_OUTX_L_A, 6)
	x_raw = (data[1] << 8) | data[0]
	y_raw = (data[3] << 8) | data[2]
	z_raw = (data[5] << 8) | data[4]
	if x_raw > 32767:
		x_raw -= 65536
	if y_raw > 32767:
		y_raw -= 65536
	if z_raw > 32767:
		z_raw -= 65536
	scale = 0.122 / 1000.0
	return x_raw * scale, y_raw * scale, z_raw * scale


def init_adxl375(spi, cs):
	spi_write_register(spi, cs, ADXL375_BW_RATE, 0x0A)
	spi_write_register(spi, cs, ADXL375_DATA_FORMAT, 0x0B)
	spi_write_register(spi, cs, ADXL375_POWER_CTL, 0x08)


def read_adxl375_accel(spi, cs):
	data = spi_read_bytes(spi, cs, ADXL375_DATAX0, 6, mb=True)
	x_raw = (data[1] << 8) | data[0]
	y_raw = (data[3] << 8) | data[2]
	z_raw = (data[5] << 8) | data[4]
	if x_raw > 32767:
		x_raw -= 65536
	if y_raw > 32767:
		y_raw -= 65536
	if z_raw > 32767:
		z_raw -= 65536
	scale = 0.049
	return x_raw * scale, y_raw * scale, z_raw * scale


def read_w25q64_jedec(spi, cs):
	tx = bytearray(4)
	rx = bytearray(4)
	tx[0] = FLASH_JEDEC_CMD
	while not spi.try_lock():
		pass
	try:
		spi.configure(baudrate=1_000_000, polarity=0, phase=0)
		cs.value = False
		spi.write_readinto(tx, rx)
		cs.value = True
	finally:
		spi.unlock()
	return tuple(rx[1:4])


def detect_devices(spi, cs_lsm, cs_adxl, cs_flash):
	lsm_whoami = spi_read_register(spi, cs_lsm, LSM6DS_WHOAMI_REG)
	adxl_devid = spi_read_register(spi, cs_adxl, ADXL375_DEVID_REG)
	flash_jedec = read_w25q64_jedec(spi, cs_flash)
	return lsm_whoami, adxl_devid, flash_jedec


def main():
	spi = init_spi()
	cs_lsm = make_cs(CS_LSM6DSOX)
	cs_adxl = make_cs(CS_ADXL375)
	cs_flash = make_cs(CS_W25Q64)
	
	cs_lsm.value = True
	cs_adxl.value = True
	cs_flash.value = True
	
	lsm_whoami, adxl_devid, flash_jedec = detect_devices(spi, cs_lsm, cs_adxl, cs_flash)
	if lsm_whoami not in LSM6DS_WHOAMI_OK:
		print("LSM6DSOX missing")
		return
	if adxl_devid != ADXL375_DEVID_OK:
		print("ADXL375 missing")
		return
	if flash_jedec not in ((0xEF, 0x40, 0x17), (0xEF, 0x40, 0x16)):
		print("W25Q64 missing")
		return
	
	init_lsm6dsox(spi, cs_lsm)
	init_adxl375(spi, cs_adxl)
	
	pre_count = int(PRE_TRIGGER_S * SAMPLE_RATE_HZ)
	post_count = int(POST_TRIGGER_S * SAMPLE_RATE_HZ)
	buffer = RingBuffer(pre_count)
	trigger = TriggerDetector(TRIGGER_THRESHOLD_G, TRIGGER_DEBOUNCE_SAMPLES)
	storage = StorageEngine()
	
	print("Sampling... waiting for trigger")
	post_samples = []
	triggered = False
	
	next_t = time.monotonic()
	while True:
		now = time.monotonic()
		if now < next_t:
			continue
		next_t += SAMPLE_PERIOD_S
		
		lsm_x, lsm_y, lsm_z = read_lsm6dsox_accel(spi, cs_lsm)
		adxl_x, adxl_y, adxl_z = read_adxl375_accel(spi, cs_adxl)
		t_ms = int(now * 1000)
		sample = (t_ms, lsm_x, lsm_y, lsm_z, adxl_x, adxl_y, adxl_z)
		
		if not triggered:
			buffer.append(sample)
			if trigger.update(adxl_x, adxl_y, adxl_z):
				triggered = True
				post_samples = []
				print("Trigger detected")
		else:
			post_samples.append(sample)
			if len(post_samples) >= post_count:
				full_shot = buffer.snapshot() + post_samples
				path = storage.write_shot(full_shot, SAMPLE_RATE_HZ)
				print("Shot saved:", path)
				triggered = False
				post_samples = []


if __name__ == "__main__":
	main()
