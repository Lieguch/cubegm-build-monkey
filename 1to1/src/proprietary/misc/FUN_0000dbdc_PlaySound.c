/* ============================================================
 * PlaySound   @ 0x0000dbdc   size=32B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

void PlaySound(void)

{
  if (sound_driver_playframe == (code *)0x0) {
    return;
  }
                    /* WARNING: Could not recover jumptable at 0x0000dbf8. Too many branches */
                    /* WARNING: Treating indirect jump as call */
  (*sound_driver_playframe)();
  return;
}
