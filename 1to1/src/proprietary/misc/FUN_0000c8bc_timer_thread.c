/* ============================================================
 * timer_thread   @ 0x0000c8bc   size=16B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

void timer_thread(void)

{
  ReadJoystickProc();
  processvblank();
  return;
}
