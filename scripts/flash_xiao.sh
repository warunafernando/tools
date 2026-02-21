#!/bin/bash
# Flash XIAO via debugger (OpenOCD). Kills any stray OpenOCD first so probe is free.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/debugger_ctl.sh"

cd /home/mini/tools/ncs-workspace
export PATH="/home/mini/tools/.venv/bin:$PATH"

ensure_debugger_free
# Build dir already has board/app from last west build
west flash --runner openocd
