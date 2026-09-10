/* ============================================================
 * sflash_write_security_data   @ 0x002c3f40   size=92B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void sflash_write_security_data(undefined4 param_1,undefined4 param_2)

{
  int iVar1;
  undefined4 local_18;
  undefined4 local_14;
  
  local_14 = 0;
  local_18 = 0x5042;
  snor_write_en();
  iVar1 = sfc_request(&local_18,param_2,param_1,0x100);
  if (iVar1 == 0) {
    snor_wait_busy(10000);
  }
  return;
}
