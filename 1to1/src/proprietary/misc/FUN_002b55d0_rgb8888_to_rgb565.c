/* ============================================================
 * rgb8888_to_rgb565   @ 0x002b55d0   size=84B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void rgb8888_to_rgb565(ushort *param_1,int param_2,int param_3)

{
  int iVar1;
  int iVar2;
  
  if (param_3 < 4) {
    return;
  }
  iVar2 = param_2 + 4;
  do {
    iVar1 = iVar2 + 4;
    *param_1 = (*(byte *)(iVar2 + -3) & 0xfc) << 3 | (*(byte *)(iVar2 + -2) & 0xf8) << 8 |
               (ushort)(*(byte *)(iVar2 + -4) >> 3);
    param_1 = param_1 + 1;
    iVar2 = iVar1;
  } while (param_2 + (param_3 - 4U & 0xfffffffc) + 8 != iVar1);
  return;
}
