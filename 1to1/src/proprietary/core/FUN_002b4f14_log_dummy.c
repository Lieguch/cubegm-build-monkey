/* ============================================================
 * log_dummy   @ 0x002b4f14   size=52B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

void log_dummy(uint param_1,undefined4 param_2)

{
  if (param_1 < 2) {
    return;
  }
  RARCH_LOG_V(param_2);
  return;
}
