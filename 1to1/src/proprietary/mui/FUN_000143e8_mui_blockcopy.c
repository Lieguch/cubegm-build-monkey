/* ============================================================
 * mui_blockcopy   @ 0x000143e8   size=136B   callers=3
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_blockcopy(int *param_1,int *param_2)

{
  int iVar1;
  int iVar2;
  int iVar3;
  
  iVar1 = param_2[2];
  if (param_2[4] - iVar1 < 1) {
    return;
  }
  iVar2 = 0;
  do {
    iVar1 = iVar2 + iVar1;
    iVar3 = iVar2 + param_1[2];
    iVar2 = iVar2 + 1;
    memcpy((void *)(*param_1 + param_1[5] * iVar3 + param_1[1] * 2),
           (void *)(*param_2 + param_2[5] * iVar1 + param_2[1] * 2),(param_2[3] - param_2[1]) * 2);
    iVar1 = param_2[2];
  } while (iVar2 < param_2[4] - iVar1);
  return;
}
