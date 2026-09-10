/* ============================================================
 * Convert_Mono   @ 0x002b8cbc   size=44B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void Convert_Mono(gh_u2 *param_1)

{
  gh_u2 *puVar1;
  gh_u2 *puVar2;
  
  puVar1 = param_1 + 0x480;
  puVar2 = param_1 + 0x8fe;
  do {
    *puVar2 = puVar1[-1];
    puVar1 = puVar1 + -1;
    puVar2[1] = *puVar1;
    puVar2 = puVar2 + -2;
  } while (puVar1 != param_1);
  return;
}
