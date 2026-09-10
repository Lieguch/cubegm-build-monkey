/* ============================================================
 * gameType   @ 0x000211bc   size=52B   callers=6
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void gameType(void)

{
  uint uVar1;
  
  uVar1 = 0;
  do {
    if ((ushort)Filetype >> (uVar1 & 0xff) == 1) {
      return;
    }
    uVar1 = uVar1 + 1;
  } while (uVar1 != 0x10);
  return;
}
