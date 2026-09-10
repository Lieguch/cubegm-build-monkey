/* ============================================================
 * spi_read   @ 0x002c3efc   size=68B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void spi_read(undefined4 param_1,undefined4 param_2,undefined4 param_3)

{
  undefined4 local_10;
  undefined4 local_c;
  
  local_c = 0;
  local_10 = 0x4003;
  sfc_request(&local_10,param_1,param_2,param_3);
  return;
}
