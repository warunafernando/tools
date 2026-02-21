/*
 * SmartBall NCS App - BLE + mcumgr SMP + health-gated confirm + DFU-safe mode
 * BLE_OTA_upgrade.md steps 1-6
 * Board: xiao_ble (Seeed XIAO nRF52840 Sense)
 */
#include <zephyr/kernel.h>
#include <zephyr/bluetooth/bluetooth.h>
#include <zephyr/bluetooth/conn.h>
#include <zephyr/bluetooth/gap.h>
#include <zephyr/settings/settings.h>
#include <zephyr/dfu/mcuboot.h>
#include <zephyr/sys/reboot.h>
#include <stdio.h>

#define N_FAIL_MAX 3
#define T_CONFIRM_WINDOW_SEC 30
#define BATTERY_THRESHOLD_MV 3700

/* Boot count stored via settings (key: boot/count) */
#define SETTINGS_BOOT_COUNT_KEY "boot/cnt"
static uint32_t boot_count;
static bool dfu_safe_mode;
static bool health_ok;

static void connected(struct bt_conn *conn, uint8_t err)
{
	if (err) {
		printk("Connection failed (err 0x%02x)\n", err);
	} else {
		printk("Connected\n");
	}
}

static void disconnected(struct bt_conn *conn, uint8_t reason)
{
	printk("Disconnected (reason 0x%02x)\n", reason);
}

BT_CONN_CB_DEFINE(conn_callbacks) = {
	.connected = connected,
	.disconnected = disconnected,
};

static const struct bt_data ad[] = {
	BT_DATA_BYTES(BT_DATA_FLAGS, (BT_LE_AD_GENERAL | BT_LE_AD_NO_BREDR)),
	BT_DATA_BYTES(BT_DATA_UUID16_ALL, BT_UUID_DIS_VAL),
};

static const struct bt_data sd[] = {
	BT_DATA(BT_DATA_NAME_COMPLETE, CONFIG_BT_DEVICE_NAME, sizeof(CONFIG_BT_DEVICE_NAME) - 1),
};

/* Boot failure counter (§7.1) - uses settings (load done after bt_ready) */
static void boot_counter_increment(void)
{
	boot_count++;
}

static void boot_counter_clear(void)
{
	boot_count = 0;
}

/* Load boot count from settings - call after settings_load() */
static void boot_counter_load_from_settings(void)
{
	char buf[12];
	size_t len = sizeof(buf);
	if (settings_get(SETTINGS_BOOT_COUNT_KEY, buf, &len) == 0 && len > 0) {
		boot_count = (uint32_t)strtoul(buf, NULL, 10);
	}
}

static void boot_counter_save(void)
{
	char buf[12];
	snprintf(buf, sizeof(buf), "%u", boot_count);
	settings_save_one(SETTINGS_BOOT_COUNT_KEY, buf);
}

/* Health checks (§6.1) - minimal: BLE + stub battery/sensors */
static bool run_health_checks(void)
{
	/* BLE: already initialized and advertising */
	/* Battery: stub - in production use ADC. Assume OK for now */
	(void)BATTERY_THRESHOLD_MV;
	/* Sensors: stub - in production init IMU. Assume OK for now */
	return true;
}

static void bt_ready(int err)
{
	if (err) {
		printk("Bluetooth init failed (err %d)\n", err);
		return;
	}
	printk("Bluetooth initialized\n");

	if (IS_ENABLED(CONFIG_SETTINGS)) {
		settings_load();
	}

	err = bt_le_adv_start(BT_LE_ADV_CONN_FAST_1, ad, ARRAY_SIZE(ad), sd, ARRAY_SIZE(sd));
	if (err) {
		printk("Advertising failed to start (err %d)\n", err);
		return;
	}
	printk("Advertising started as '%s'\n", CONFIG_BT_DEVICE_NAME);
}

int main(void)
{
	int err;
	uint32_t confirm_deadline;
	bool pending_confirm = false;

	if (IS_ENABLED(CONFIG_SETTINGS)) {
		settings_subsys_init();
		settings_load();
		boot_counter_load_from_settings();
	}
	boot_counter_increment();
	boot_counter_save();

	/* DFU-safe mode (§7.2): if boot failures exceed N_FAIL_MAX */
	if (boot_count >= N_FAIL_MAX) {
		dfu_safe_mode = true;
		printk("DFU-safe mode: boot_count=%u >= %d\n", boot_count, N_FAIL_MAX);
	}

	err = bt_enable(bt_ready);
	if (err) {
		printk("bt_enable failed (err %d)\n", err);
		return 0;
	}

	/* Check if we are in test (pending confirm) state (§6.2) */
	if (boot_is_img_confirmed()) {
		boot_counter_clear();
		boot_counter_save();
	} else {
		pending_confirm = true;
		confirm_deadline = k_uptime_get_32() + (T_CONFIRM_WINDOW_SEC * 1000);
		printk("Image in TEST state - health check window %ds\n", T_CONFIRM_WINDOW_SEC);
	}

	/* Main loop: run health checks and confirm when ready */
	for (;;) {
		k_sleep(K_SECONDS(1));

		if (pending_confirm && k_uptime_get_32() < confirm_deadline) {
			health_ok = run_health_checks();
			if (health_ok) {
				err = boot_write_img_confirmed();
				if (err == 0) {
					printk("Image confirmed\n");
					pending_confirm = false;
					boot_counter_clear();
					boot_counter_save();
				} else {
					printk("boot_write_img_confirmed failed %d\n", err);
				}
			}
		}

		if (pending_confirm && k_uptime_get_32() >= confirm_deadline) {
			printk("Health check window expired without confirm - rollback on next reboot\n");
			pending_confirm = false;
		}
	}
	return 0;
}
