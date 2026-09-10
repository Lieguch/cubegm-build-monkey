/* ============================================================
 * Convert_Stereo   @ 0x002b8c84   size=56B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void Convert_Stereo(gh_u2 *param_1)

{
  gh_u2 *puVar1;
  gh_u2 *puVar2;
  gh_u2 *puVar3;
  
  puVar3 = param_1 + 0x900;
  do {
    puVar1 = param_1 + 0x20;
    puVar2 = param_1;
    do {
      puVar2[0x3f] = puVar1[-1];
      puVar1 = puVar1 + -1;
      puVar2[0x3e] = *puVar1;
      puVar2 = puVar2 + -2;
    } while (param_1 != puVar1);
    param_1 = param_1 + 0x40;
  } while (puVar3 != param_1);
  return;
}
