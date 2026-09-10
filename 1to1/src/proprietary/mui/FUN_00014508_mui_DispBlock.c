/* ============================================================
 * mui_DispBlock   @ 0x00014508   size=124B   callers=13
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_DispBlock(int param_1,int param_2,int param_3,int param_4)

{
  int iVar1;
  int iVar2;
  int *piVar3;
  int iVar4;
  gh_uint uVar5;
  int iVar6;
  
  piVar3 = (int *)(param_3 + param_4 * 0x10);
  uVar5 = (gh_uint)*(gh_ushort *)((int)piVar3 + 10);
  if ((int)(*(gh_ushort *)((int)piVar3 + 0xe) - uVar5) < 1) {
    return;
  }
  iVar4 = 0;
  do {
    iVar6 = iVar4 + uVar5;
    iVar1 = (gh_uint)*(gh_ushort *)(piVar3 + 3) - (gh_uint)*(gh_ushort *)(piVar3 + 2);
    iVar2 = iVar4 * iVar1;
    iVar4 = iVar4 + 1;
    memcpy((void *)(param_1 + param_2 * iVar6 + (gh_uint)*(gh_ushort *)(piVar3 + 2) * 2),
           (void *)(param_3 + *piVar3 + iVar2 * 2),iVar1 * 2);
    uVar5 = (gh_uint)*(gh_ushort *)((int)piVar3 + 10);
  } while (iVar4 < (int)(*(gh_ushort *)((int)piVar3 + 0xe) - uVar5));
  return;
}
