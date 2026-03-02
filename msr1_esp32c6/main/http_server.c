#include "http_server.h"
#include "binary_protocol.h"
#include "main.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include <stdio.h>
#include <string.h>

static const char *TAG = "http";

#define IP_BUF_SIZE 20

#define RSP_BUF_SIZE 512

static esp_err_t api_cmd_post_handler(httpd_req_t *req) {
    if (req->content_len <= 0 || req->content_len > BIN_RX_BUF_SIZE) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid content length");
        return ESP_FAIL;
    }
    uint8_t rx_buf[BIN_RX_BUF_SIZE];
    int r = httpd_req_recv(req, (char *)rx_buf, (size_t)req->content_len);
    if (r <= 0 || (size_t)r != (size_t)req->content_len) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Recv failed");
        return ESP_FAIL;
    }
    uint8_t type;
    const uint8_t *payload;
    uint16_t plen;
    if (binary_parse_frame(rx_buf, (size_t)r, &type, &payload, &plen) != 0) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST, "Invalid frame");
        return ESP_FAIL;
    }
    uint8_t rsp_buf[RSP_BUF_SIZE];
    size_t rsp_len = binary_process_cmd(type, payload, plen, rsp_buf, sizeof(rsp_buf), BIN_MAX_PAYLOAD);
    if (rsp_len == 0) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Cmd failed");
        return ESP_FAIL;
    }
    httpd_resp_set_type(req, "application/octet-stream");
    char len_buf[12];
    snprintf(len_buf, sizeof(len_buf), "%u", (unsigned)rsp_len);
    httpd_resp_set_hdr(req, "Content-Length", len_buf);
    if (httpd_resp_send(req, (const char *)rsp_buf, rsp_len) != ESP_OK)
        return ESP_FAIL;
    return ESP_OK;
}

static esp_err_t api_ip_get_handler(httpd_req_t *req) {
    char ip_buf[IP_BUF_SIZE];
    if (get_device_ip_string(ip_buf, sizeof(ip_buf)) != 0) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "No IP");
        return ESP_FAIL;
    }
    httpd_resp_set_type(req, "text/plain");
    httpd_resp_send(req, ip_buf, strlen(ip_buf));
    return ESP_OK;
}

static httpd_uri_t api_cmd = {
    .uri       = "/api/cmd",
    .method    = HTTP_POST,
    .handler   = api_cmd_post_handler,
    .user_ctx  = NULL,
};

static httpd_uri_t api_ip = {
    .uri       = "/api/ip",
    .method    = HTTP_GET,
    .handler   = api_ip_get_handler,
    .user_ctx  = NULL,
};

static httpd_handle_t server = NULL;

void http_server_start(void) {
    if (server != NULL) return;
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.max_open_sockets = 4;   /* stay within LWIP_MAX_SOCKETS (8), 3 used internally */
    config.max_uri_handlers = 6;
    config.uri_match_fn = httpd_uri_match_wildcard;
    if (httpd_start(&server, &config) != ESP_OK) {
        ESP_LOGE(TAG, "httpd_start failed");
        return;
    }
    if (httpd_register_uri_handler(server, &api_cmd) != ESP_OK) {
        ESP_LOGE(TAG, "register /api/cmd failed");
        return;
    }
    if (httpd_register_uri_handler(server, &api_ip) != ESP_OK) {
        ESP_LOGE(TAG, "register /api/ip failed");
        return;
    }
    ESP_LOGI(TAG, "HTTP server on /api/cmd (POST binary), /api/ip (GET)");
}

void http_server_stop(void) {
    if (server) {
        httpd_stop(server);
        server = NULL;
    }
}
