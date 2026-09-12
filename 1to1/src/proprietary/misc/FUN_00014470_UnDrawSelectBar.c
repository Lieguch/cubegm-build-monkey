/* ============================================================
 * UnDrawSelectBar   @ 0x00014470   size=148B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void UnDrawSelectBar(int *param_1,int param_2,int param_3)

{
  int iVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  int *piVar6;
  int iVar7;
  int iVar8;
  
  iVar2 = (int)DAT_003af29c;
  iVar7 = param_1[1];
  if (param_1[3] <= iVar7) {
    return;
  }
  iVar1 = DAT_003af2a0 * 2;
  piVar6 = (int *)(param_2 + param_3 * 0x10);
  iVar8 = iVar7 * iVar1;
  do {
    iVar3 = *param_1;
    iVar5 = iVar7 - (gh_uint)*(gh_ushort *)((int)piVar6 + 10);
    iVar4 = iVar8 + iVar3 * 2;
    iVar7 = iVar7 + 1;
    iVar8 = iVar8 + iVar1;
    memcpy((void *)(iVar2 + iVar4),
           (void *)(param_2 +
                   *piVar6 + (((gh_uint)*(gh_ushort *)(piVar6 + 3) - (gh_uint)*(gh_ushort *)(piVar6 + 2)) *
                              iVar5 + (iVar3 - (gh_uint)*(gh_ushort *)(piVar6 + 2))) * 2),
           (param_1[2] - iVar3) * 2);
  } while (iVar7 < param_1[3]);
  return;
}
