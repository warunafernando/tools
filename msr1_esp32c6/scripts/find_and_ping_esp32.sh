#!/bin/bash
# Find SmartBall ESP32 on local subnet by probing GET /api/ip (returns device IP as text).
# Usage: ./scripts/find_and_ping_esp32.sh [subnet_prefix e.g. 192.168.68]
set -e
PREFIX="${1:-192.168.68}"
echo "Probing $PREFIX.0/24 for SmartBall ESP32 (GET /api/ip)..."
for i in $(seq 2 254); do
  ip="${PREFIX}.${i}"
  rsp=$(curl -s --connect-timeout 1 -m 2 "http://${ip}/api/ip" 2>/dev/null || true)
  if [ -n "$rsp" ] && [[ "$rsp" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "FOUND: $ip (device reports IP: $rsp)"
    if command -v ping >/dev/null 2>&1; then
      echo "  Ping: $(ping -c 1 -W 1 "$ip" 2>/dev/null | grep 'time=' || echo 'ping failed (try: sudo ping')"
    fi
  fi
done
echo "Done."
