/* ============================================================
 * ui_deinit   @ 0x00022480   size=144B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

void ui_deinit(void)

{
  Soundplayflag = Soundplayflag & 0xfe;
  while (Soundplayflag != 0) {
    usleep(1000);
  }
  SoundClose(0);
  DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
  SoundPlayer._0_4_ = 0;
  SoundPlayer._36_4_ = 0;
  if (DisplayThumbnailflag == 0) {
    return;
  }
  do {
    usleep(1000);
  } while (DisplayThumbnailflag != 0);
  return;
}
