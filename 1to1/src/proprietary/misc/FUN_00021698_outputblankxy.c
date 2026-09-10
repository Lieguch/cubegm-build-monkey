/* ============================================================
 * outputblankxy   @ 0x00021698   size=212B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void outputblankxy(int param_1,int param_2,int param_3,int param_4)

{
  int iVar1;
  gh_ushort *puVar2;
  gh_ushort *puVar3;
  gh_uint uVar4;
  gh_ushort *puVar5;
  gh_u2 *puVar6;
  int iVar7;
  gh_u2 *puVar8;
  
  iVar1 = DAT_003af2a0;
  if (DAT_003af720 + DAT_003af728 < param_1 + param_3) {
    param_3 = (DAT_003af720 + DAT_003af728) - param_1;
  }
  if (0 < param_4) {
    iVar7 = 0;
    puVar6 = (gh_u2 *)
             ((int)DAT_003af294 + (*DAT_003af294 + -9 + DAT_003af2a0 * param_2 + param_1) * 2);
    puVar5 = (gh_ushort *)(DAT_003af29c + (DAT_003af2a0 * param_2 + 0x7ffffff8 + param_1) * 2);
    do {
      if (-0x10 < param_3) {
        puVar2 = puVar5;
        puVar8 = puVar6;
        do {
          puVar8 = puVar8 + 1;
          uVar4 = CONCAT22(*puVar8,*puVar8) & 0x7e0f81f;
          uVar4 = uVar4 + ((int)(uVar4 * -0xc) >> 5) & 0x7e0f81f;
          puVar3 = puVar2 + 1;
          *puVar2 = (gh_ushort)uVar4 | (gh_ushort)(uVar4 >> 0x10);
          puVar2 = puVar3;
        } while (puVar5 + param_3 + 0x10 != puVar3);
      }
      iVar7 = iVar7 + 1;
      puVar5 = puVar5 + iVar1;
      puVar6 = puVar6 + iVar1;
    } while (param_4 != iVar7);
    return;
  }
  return;
}
