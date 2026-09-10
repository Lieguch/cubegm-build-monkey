/* ============================================================
 * snor_write_en   @ 0x002c3e00   size=56B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

void snor_write_en(void)

{
  undefined4 local_10;
  undefined4 local_c;
  
  local_c = 0;
  local_10 = 6;
  sfc_request(&local_10,0,0,0);
  return;
}
