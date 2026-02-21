# Debug BLE advertising EINVAL - find which check fails
target extended-remote :3333
load build/app/zephyr/zephyr.elf

# Break at the two EINVAL return points in bt_le_adv_start_legacy
break adv.c:979
commands
  printf "\n=== At valid_adv_param check ===\n"
  next
  set $valid = (int)$r0
  printf "valid_adv_param returned %d (0=invalid->EINVAL, 1=valid)\n", $valid
  if $valid == 0
    printf "*** EINVAL: valid_adv_param FAILED ***\n"
    printf "Check: param->id=%d bt_dev.id_count=%d\n", param->id, bt_dev.id_count
  end
  continue
end

break adv.c:983
commands
  printf "\n=== At bt_id_adv_random_addr_check ===\n"
  next
  set $check = (int)$r0
  printf "bt_id_adv_random_addr_check returned %d (0=fail->EINVAL, 1=ok)\n", $check
  if $check == 0
    printf "*** EINVAL: bt_id_adv_random_addr_check FAILED ***\n"
  end
  continue
end

break bt_le_adv_start
commands
  finish
  printf "\nbt_le_adv_start returned %d (0=OK, -22=EINVAL)\n", (int)$r0
  continue
end

run
