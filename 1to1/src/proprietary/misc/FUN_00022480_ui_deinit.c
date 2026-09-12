/* ============================================================
 * ui_deinit   @ 0x00022480   size=144B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void ui_deinit(void)

{
  Soundplayflag = Soundplayflag & 0xfe;
  while (Soundplayflag != 0) {
    usleep(1000);
  }
  SoundClose(0);
  DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
  (SoundPlayer_blob)._0_4_ = 0;
  (SoundPlayer_blob)._36_4_ = 0;
  if (DisplayThumbnailflag == 0) {
    return;
  }
  do {
    usleep(1000);
  } while (DisplayThumbnailflag != 0);
  return;
}
