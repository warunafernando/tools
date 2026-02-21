# Line-by-Line Debugging with GDB

## Quick start

```bash
/home/mini/tools/scripts/debug_xiao.sh
```

This script:
- Kills any stray OpenOCD/GDB so the debug probe (CMSIS-DAP) is free
- Builds, flashes, and starts GDB
- **Closes the debugger when you quit GDB** (`quit` or Ctrl+D) so the probe is released for next flash

## Debugger lifecycle

If you get "Resource busy" when flashing:
- Another OpenOCD or GDB may be holding the probe
- Run `source scripts/debugger_ctl.sh && ensure_debugger_free` first, or use `./scripts/flash_xiao.sh`

## Manual

```bash
cd /home/mini/tools/ncs-workspace
# Build with debug (no optimizations)
west build -b xiao_ble_sense nrf/app -- -DEXTRA_CONF_FILE=prj_debug.conf

# Flash and open GDB
sudo west debug --runner openocd -- --gdb /usr/bin/gdb-multiarch
```

## Useful GDB commands

After GDB attaches, set breakpoints and run:

```
(gdb) break main
(gdb) break bt_enable
(gdb) break bt_thread_fn
(gdb) break z_arm_hard_fault    # catches hard fault
(gdb) continue                  # run to next breakpoint
(gdb) step                      # step into
(gdb) next                      # step over
(gdb) bt                        # backtrace (on crash)
(gdb) info locals               # show local variables
```

## If it crashes

When you hit `z_arm_hard_fault`:
- `bt` shows the call stack
- `info locals` in main/bt_thread_fn shows variable state
- `frame N` then `info locals` to inspect a specific frame
