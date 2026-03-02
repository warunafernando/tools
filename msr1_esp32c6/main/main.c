#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "esp_netif.h"
#include "http_server.h"
#include "main.h"
#include <string.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include "lwip/inet.h"

static const char *TAG = "main";

#define WIFI_STA_SSID "SinhaleD"
#define WIFI_STA_PASS "emmyemmy"
#define WIFI_STA_HOSTNAME "smartball-esp32c6"

static esp_netif_t *s_sta_netif = NULL;

static const char *wifi_reason_str(uint8_t reason) {
    switch (reason) {
    case WIFI_REASON_UNSPECIFIED:           return "unspecified";
    case WIFI_REASON_AUTH_EXPIRE:           return "auth expire";
    case WIFI_REASON_AUTH_LEAVE:            return "auth leave";
    case WIFI_REASON_ASSOC_EXPIRE:          return "assoc expire";
    case WIFI_REASON_ASSOC_TOOMANY:         return "assoc too many";
    case WIFI_REASON_NOT_AUTHED:            return "not authed";
    case WIFI_REASON_NOT_ASSOCED:           return "not assoced";
    case WIFI_REASON_ASSOC_LEAVE:           return "assoc leave";
    case WIFI_REASON_ASSOC_NOT_AUTHED:      return "assoc not authed";
    case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:return "4way handshake timeout";
    case WIFI_REASON_GROUP_KEY_UPDATE_TIMEOUT: return "group key update timeout";
    case WIFI_REASON_MIC_FAILURE:           return "MIC failure";
    case WIFI_REASON_IE_IN_4WAY_DIFFERS:    return "IE in 4way differs";
    case WIFI_REASON_GROUP_CIPHER_INVALID:  return "group cipher invalid";
    case WIFI_REASON_PAIRWISE_CIPHER_INVALID: return "pairwise cipher invalid";
    case WIFI_REASON_AKMP_INVALID:          return "AKMP invalid";
    case WIFI_REASON_UNSUPP_RSN_IE_VERSION: return "unsupp RSN IE version";
    case WIFI_REASON_802_1X_AUTH_FAILED:    return "802.1X auth failed";
    case WIFI_REASON_CIPHER_SUITE_REJECTED: return "cipher suite rejected";
    case WIFI_REASON_BAD_CIPHER_OR_AKM:     return "bad cipher or AKM";
    case WIFI_REASON_TIMEOUT:               return "timeout";
    case WIFI_REASON_BEACON_TIMEOUT:        return "beacon timeout";
    case WIFI_REASON_NO_AP_FOUND:           return "AP not found";
    case WIFI_REASON_AUTH_FAIL:             return "auth failed (wrong password?)";
    case WIFI_REASON_ASSOC_FAIL:            return "assoc fail";
    case WIFI_REASON_HANDSHAKE_TIMEOUT:     return "handshake timeout";
    case WIFI_REASON_CONNECTION_FAIL:       return "connection fail";
    case WIFI_REASON_AP_TSF_RESET:          return "AP TSF reset";
    case WIFI_REASON_ROAMING:               return "roaming";
    default:                                return "other";
    }
}

static void wifi_event_handler(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == WIFI_EVENT) {
        switch (id) {
        case WIFI_EVENT_STA_START:
            ESP_LOGI(TAG, "WiFi STA_START: driver ready, scanning for %s", WIFI_STA_SSID);
            break;
        case WIFI_EVENT_STA_CONNECTED: {
            wifi_event_sta_connected_t *ev = (wifi_event_sta_connected_t *)data;
            ESP_LOGI(TAG, "WiFi CONNECTED: SSID=%s channel=%d auth=%d BSSID=%02x:%02x:%02x:%02x:%02x:%02x",
                     (const char *)ev->ssid, ev->channel, ev->authmode,
                     ev->bssid[0], ev->bssid[1], ev->bssid[2],
                     ev->bssid[3], ev->bssid[4], ev->bssid[5]);
            int rssi = 0;
            if (esp_wifi_sta_get_rssi(&rssi) == ESP_OK) {
                ESP_LOGI(TAG, "  RSSI: %d dBm (higher=better, -50 excellent, -70 ok, -85 poor)", rssi);
            }
            ESP_LOGI(TAG, "  Waiting for DHCP...");
            break;
        }
        case WIFI_EVENT_STA_DISCONNECTED: {
            wifi_event_sta_disconnected_t *ev = (wifi_event_sta_disconnected_t *)data;
            ESP_LOGW(TAG, "WiFi DISCONNECTED: reason=%d (%s)", ev->reason, wifi_reason_str(ev->reason));
            if (ev->reason == WIFI_REASON_NO_AP_FOUND) {
                ESP_LOGW(TAG, "  -> SSID '%s' not in range or typo?", WIFI_STA_SSID);
            } else if (ev->reason == WIFI_REASON_AUTH_FAIL || ev->reason == WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT) {
                ESP_LOGW(TAG, "  -> Check password for '%s'", WIFI_STA_SSID);
            }
            break;
        }
        default:
            ESP_LOGD(TAG, "WiFi event id=%ld", (long)id);
            break;
        }
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *ev = (ip_event_got_ip_t *)data;
        uint32_t ip = ntohl(ev->ip_info.ip.addr);
        uint32_t gw = ntohl(ev->ip_info.gw.addr);
        uint32_t mask = ntohl(ev->ip_info.netmask.addr);
        ESP_LOGI(TAG, "DHCP OK: IP=%lu.%lu.%lu.%lu gw=%lu.%lu.%lu.%lu mask=%lu.%lu.%lu.%lu",
                 (unsigned long)((ip >> 24) & 0xff), (unsigned long)((ip >> 16) & 0xff),
                 (unsigned long)((ip >> 8) & 0xff), (unsigned long)(ip & 0xff),
                 (unsigned long)((gw >> 24) & 0xff), (unsigned long)((gw >> 16) & 0xff),
                 (unsigned long)((gw >> 8) & 0xff), (unsigned long)(gw & 0xff),
                 (unsigned long)((mask >> 24) & 0xff), (unsigned long)((mask >> 16) & 0xff),
                 (unsigned long)((mask >> 8) & 0xff), (unsigned long)(mask & 0xff));
        int rssi = 0;
        if (esp_wifi_sta_get_rssi(&rssi) == ESP_OK) {
            ESP_LOGI(TAG, "  RSSI: %d dBm", rssi);
        }
        ESP_LOGI(TAG, "  API: http://%lu.%lu.%lu.%lu/api/cmd  GET /api/ip for IP", (ip>>24)&0xff, (ip>>16)&0xff, (ip>>8)&0xff, ip&0xff);
    }
}

static void wifi_sta_start(void) {
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    s_sta_netif = esp_netif_create_default_wifi_sta();
    if (s_sta_netif) {
        esp_netif_set_hostname(s_sta_netif, WIFI_STA_HOSTNAME);
    }

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, wifi_event_handler, NULL, NULL));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, wifi_event_handler, NULL, NULL));

    wifi_config_t sta_cfg = { 0 };
    strncpy((char *)sta_cfg.sta.ssid, WIFI_STA_SSID, sizeof(sta_cfg.sta.ssid) - 1);
    strncpy((char *)sta_cfg.sta.password, WIFI_STA_PASS, sizeof(sta_cfg.sta.password) - 1);
    sta_cfg.sta.threshold.authmode = WIFI_AUTH_WPA_WPA2_PSK;  /* accept WPA or WPA2 */

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &sta_cfg));
    ESP_ERROR_CHECK(esp_wifi_start());
    uint8_t mac[6];
    esp_wifi_get_mac(WIFI_IF_STA, mac);
    ESP_LOGI(TAG, "STA started: SSID='%s' (len %d), pass len %d, hostname=%s",
             WIFI_STA_SSID, (int)strlen(WIFI_STA_SSID), (int)strlen(WIFI_STA_PASS), WIFI_STA_HOSTNAME);
    ESP_LOGI(TAG, "  MAC: %02x:%02x:%02x:%02x:%02x:%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    ESP_LOGI(TAG, "  Connecting...");
}

static void wait_for_ip(void) {
    /* Give driver a moment after esp_wifi_start() before polling (first connect can be slow). */
    vTaskDelay(pdMS_TO_TICKS(1500));

    for (int i = 0; i < 60; i++) {
        if (s_sta_netif) {
            esp_netif_ip_info_t info;
            if (esp_netif_get_ip_info(s_sta_netif, &info) == ESP_OK && info.ip.addr != 0) {
                uint32_t ip = ntohl(info.ip.addr);
                ESP_LOGI(TAG, "Got IP: %lu.%lu.%lu.%lu - use http://%lu.%lu.%lu.%lu/api/cmd",
                         (unsigned long)((ip >> 24) & 0xff), (unsigned long)((ip >> 16) & 0xff),
                         (unsigned long)((ip >> 8) & 0xff), (unsigned long)(ip & 0xff),
                         (unsigned long)((ip >> 24) & 0xff), (unsigned long)((ip >> 16) & 0xff),
                         (unsigned long)((ip >> 8) & 0xff), (unsigned long)(ip & 0xff));
                return;
            }
        }
        /* Early retry: after ~8s with no IP, force disconnect+connect (first attempt often stalls). */
        if (i == 16) {
            ESP_LOGW(TAG, "No IP after 8s - forcing reconnect...");
            esp_wifi_disconnect();
            vTaskDelay(pdMS_TO_TICKS(500));
            esp_wifi_connect();
        }
        if ((i + 1) % 10 == 0) {
            int sec = (i + 1) * 500 / 1000;
            ESP_LOGW(TAG, "Waiting for IP... %ds/30s (no CONNECTED/DISCONNECTED = AP '%s' not found?)", sec, WIFI_STA_SSID);
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    ESP_LOGW(TAG, "No IP after 30s. Scanning for visible APs...");
    esp_err_t err = esp_wifi_scan_start(NULL, true);
    if (err == ESP_OK) {
        uint16_t count = 0;
        esp_wifi_scan_get_ap_num(&count);
        ESP_LOGW(TAG, "  Found %u AP(s):", (unsigned)count);
        if (count > 0) {
            wifi_ap_record_t *ap = malloc(count * sizeof(wifi_ap_record_t));
            if (ap) {
                uint16_t n = count;
                if (esp_wifi_scan_get_ap_records(&n, ap) == ESP_OK) {
                    bool found = false;
                    for (uint16_t j = 0; j < n && j < 16; j++) {
                        char ssid[33];
                        memcpy(ssid, ap[j].ssid, 32);
                        ssid[32] = '\0';
                        ESP_LOGW(TAG, "    [%u] '%s' ch=%d rssi=%d auth=%d %s",
                                 (unsigned)j + 1, ssid, ap[j].primary, ap[j].rssi, ap[j].authmode,
                                 (strcmp(ssid, WIFI_STA_SSID) == 0) ? "<-- TARGET" : "");
                        if (strcmp(ssid, WIFI_STA_SSID) == 0) found = true;
                    }
                    if (n > 16) ESP_LOGW(TAG, "    ... and %u more", (unsigned)(n - 16));
                    if (!found) ESP_LOGW(TAG, "  '%s' NOT in scan list - check SSID spelling", WIFI_STA_SSID);
                }
                free(ap);
            }
        }
    } else {
        ESP_LOGW(TAG, "  Scan failed: %s", esp_err_to_name(err));
    }
    ESP_LOGW(TAG, "Retrying connect (SinhaleD visible - forcing reconnect)...");
    esp_wifi_disconnect();
    vTaskDelay(pdMS_TO_TICKS(500));
    esp_wifi_connect();
    for (int i = 0; i < 60; i++) {
        if (s_sta_netif) {
            esp_netif_ip_info_t info;
            if (esp_netif_get_ip_info(s_sta_netif, &info) == ESP_OK && info.ip.addr != 0) {
                uint32_t ip = ntohl(info.ip.addr);
                ESP_LOGI(TAG, "Got IP (retry): %lu.%lu.%lu.%lu", (ip>>24)&0xff, (ip>>16)&0xff, (ip>>8)&0xff, ip&0xff);
                return;
            }
        }
        if ((i + 1) % 10 == 0) {
            ESP_LOGW(TAG, "Retry wait... %ds/30s", (i + 1) * 500 / 1000);
        }
        vTaskDelay(pdMS_TO_TICKS(500));
    }
    ESP_LOGW(TAG, "No IP after retry. Check password for '%s'", WIFI_STA_SSID);
}

int get_device_ip_string(char *buf, size_t size) {
    if (!buf || size < 8 || !s_sta_netif) return -1;
    esp_netif_ip_info_t info;
    if (esp_netif_get_ip_info(s_sta_netif, &info) != ESP_OK || info.ip.addr == 0)
        return -1;
    uint32_t ip = ntohl(info.ip.addr);
    int n = snprintf(buf, size, "%lu.%lu.%lu.%lu",
                     (unsigned long)((ip >> 24) & 0xff), (unsigned long)((ip >> 16) & 0xff),
                     (unsigned long)((ip >> 8) & 0xff), (unsigned long)(ip & 0xff));
    return (n > 0 && (size_t)n < size) ? 0 : -1;
}

void app_main(void) {
    ESP_LOGI(TAG, "=== SmartBall ESP32-C6 WiFi binary protocol (STA) ===");
    ESP_LOGI(TAG, "Debug: USB serial 115200 baud, idf.py -p /dev/ttyACM0 monitor");
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGW(TAG, "NVS: erasing flash (no free pages or new version)");
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_LOGI(TAG, "NVS: init OK");

    wifi_sta_start();
    wait_for_ip();
    http_server_start();

    ESP_LOGI(TAG, "Ready. POST http://<ip>/api/cmd | GET http://<ip>/api/ip");
}
