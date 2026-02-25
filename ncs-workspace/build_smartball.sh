#!/usr/bin/env bash
# Build SmartBall app (xiao_ble_sense) with sysbuild. Requires:
# - Zephyr env: source zephyr/zephyr-env.sh
# - imgtool on PATH (e.g. venv: export PATH=".venv/bin:$PATH")
set -e
cd "$(dirname "$0")"
source zephyr/zephyr-env.sh 2>/dev/null || true
export PATH="${TOOLS_VENV:-/home/mini/tools/.venv}/bin:$PATH"
west build -b xiao_ble_sense nrf/app --sysbuild "$@"
