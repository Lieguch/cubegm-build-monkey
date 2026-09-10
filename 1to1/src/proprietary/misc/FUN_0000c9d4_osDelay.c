/* ============================================================
 * osDelay   @ 0x0000c9d4   size=12B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

void osDelay(int param_1)

{
  usleep(param_1 * 1000);
  return;
}
