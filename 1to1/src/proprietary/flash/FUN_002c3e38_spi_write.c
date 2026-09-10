/* ============================================================
 * spi_write   @ 0x002c3e38   size=96B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void spi_write(undefined4 param_1,undefined4 param_2,undefined4 param_3)

{
  int iVar1;
  undefined4 local_18;
  undefined4 local_14;
  
  local_18 = 0x5002;
  local_14 = 0;
  snor_write_en();
  iVar1 = sfc_request(&local_18,param_1,param_2,param_3);
  if (iVar1 == 0) {
    snor_wait_busy(10000);
  }
  return;
}
