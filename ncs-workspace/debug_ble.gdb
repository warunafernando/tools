# Debug BLE/SMP on SmartBall
target extended-remote :3333
load build/app/zephyr/zephyr.elf
break main
break bt_ready
commands 2
  silent
  printf "bt_ready called, err=%d\n", err
  continue
end
break smp_bt_register
commands 3
  silent
  printf "smp_bt_register called - SMP GATT service registering\n"
  continue
end
continue
