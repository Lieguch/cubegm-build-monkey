/* ============================================================
 * InitScr   @ 0x00029ce8   size=80B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void InitScr(void)

{
  scr_h_size = 0x1e0;
  scr_v_size = 0x110;
  if (scr_buf != (void *)0x0) {
    return;
  }
  scr_buf = malloc(0x3fc00);
  return;
}
