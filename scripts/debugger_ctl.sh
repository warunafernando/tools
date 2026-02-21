#!/bin/bash
# Debugger lifecycle helper for XIAO (OpenOCD + GDB)
# Kills stray OpenOCD/GDB so CMSIS-DAP is free; ensures cleanup when done.

kill_debugger() {
  local killed=0
  local PKILL=pkill
  command -v sudo >/dev/null 2>&1 && PKILL="sudo pkill"
  if pgrep -x openocd >/dev/null 2>&1; then
    echo "Stopping existing OpenOCD..."
    $PKILL -x openocd 2>/dev/null || true
    sleep 0.5
    $PKILL -9 -x openocd 2>/dev/null || true
    killed=1
  fi
  if pgrep -f "gdb.*3333\|gdb-multiarch.*3333" >/dev/null 2>&1; then
    echo "Stopping existing GDB (attached to debugger)..."
    pkill -f "gdb.*3333\|gdb-multiarch.*3333" 2>/dev/null || true
    killed=1
  fi
  if [ "$killed" = 1 ]; then
    sleep 0.3
    echo "Debugger released."
  fi
}

# Call before flash/debug to ensure probe is free
ensure_debugger_free() {
  kill_debugger
}

# Trap to run on script exit (cleanup)
cleanup_on_exit() {
  echo "Closing debugger..."
  kill_debugger
}

# Export for use in other scripts
export -f kill_debugger ensure_debugger_free cleanup_on_exit
