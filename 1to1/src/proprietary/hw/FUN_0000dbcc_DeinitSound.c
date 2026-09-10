/* ============================================================
 * DeinitSound   @ 0x0000dbcc   size=12B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void DeinitSound(void)

{
  run_process_constprop_0("sound_driver_deinit");
  return;
}
