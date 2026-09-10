/* ============================================================
 * sfc_uninit   @ 0x002c43cc   size=40B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 sfc_uninit(void)

{
  munmap(g_sfc_reg,0x400);
  g_sfc_reg = (void *)0x0;
  return 0;
}
