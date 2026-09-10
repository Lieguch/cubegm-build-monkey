/* ============================================================
 * SoundClose   @ 0x00022404   size=116B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SoundClose(int param_1)

{
  int *__ptr;
  
  if (*(int *)(SoundPlayer + param_1 * 0x24 + 4) == 1) {
    __ptr = *(int **)(SoundPlayer + param_1 * 0x24);
    if (*__ptr != 0) {
      MP3FreeDecoder();
    }
    if ((void *)__ptr[3] != (void *)0x0) {
      free((void *)__ptr[3]);
    }
    free(__ptr);
  }
  *(undefined4 *)(SoundPlayer + param_1 * 0x24) = 0;
  return;
}
