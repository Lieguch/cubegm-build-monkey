/* ============================================================
 * DeinitDisplay   @ 0x0000dae0   size=32B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void DeinitDisplay(void)

{
  run_process_constprop_0("video_driver_deinit");
  dlclose(handle);
  return;
}
