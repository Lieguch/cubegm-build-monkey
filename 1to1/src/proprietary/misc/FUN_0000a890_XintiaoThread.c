/* ============================================================
 * XintiaoThread   @ 0x0000a890   size=20B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

void XintiaoThread(void)

{
  do {
    xintiao();
    usleep(20000);
  } while( true );
}
