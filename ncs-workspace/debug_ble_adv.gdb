target extended-remote :3333
load build/app/zephyr/zephyr.elf
break bt_ready
commands 1
  printf "bt_ready: err=%d\n", err
  if err != 0
    printf "ERROR: bt_ready failed - BLE init error!\n"
  end
  continue
end
break bt_le_adv_start
commands 2
  printf "bt_le_adv_start called from app\n"
  finish
  printf "bt_le_adv_start returned %d (0=OK)\n", (int)$r0
  if (int)$r0 != 0
    printf "ERROR: Advertising failed to start!\n"
  end
  continue
end
continue
