/* ============================================================
 * EmuCore_Blank   @ 0x00021a2c   size=116B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void EmuCore_Blank(int param_1,int param_2,int param_3,int param_4)

{
  int iVar1;
  undefined2 *puVar2;
  int iVar4;
  undefined2 *puVar5;
  undefined2 *puVar3;
  
  iVar1 = DAT_003af2a0;
  if (0 < param_4) {
    iVar4 = 0;
    puVar5 = (undefined2 *)(DAT_003af29c + (DAT_003af2a0 * param_2 + param_1 + 0x7ffffff8) * 2);
    do {
      if (-0x10 < param_3) {
        puVar2 = puVar5;
        do {
          puVar3 = puVar2 + 1;
          *puVar2 = 0x8410;
          puVar2 = puVar3;
        } while (puVar3 != puVar5 + param_3 + 0x10);
      }
      iVar4 = iVar4 + 1;
      puVar5 = puVar5 + iVar1;
    } while (param_4 != iVar4);
    return;
  }
  return;
}
