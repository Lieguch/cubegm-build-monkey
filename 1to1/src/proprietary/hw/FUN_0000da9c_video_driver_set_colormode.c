/* ============================================================
 * video_driver_set_colormode   @ 0x0000da9c   size=60B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

void video_driver_set_colormode(undefined4 param_1)

{
  undefined4 local_14;
  undefined4 local_10;
  undefined4 local_c;
  
  local_10 = 1;
  local_c = 1;
  local_14 = param_1;
  (*video_driver_setting)(&local_14);
  return;
}
