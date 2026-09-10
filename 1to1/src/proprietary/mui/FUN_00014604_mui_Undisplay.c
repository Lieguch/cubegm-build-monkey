/* ============================================================
 * mui_Undisplay   @ 0x00014604   size=116B   callers=3
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_Undisplay(int param_1,int param_2,int param_3,int param_4)

{
  int iVar1;
  int iVar2;
  int iVar3;
  
  if (param_4 - param_2 < 1) {
    return;
  }
  iVar3 = (param_4 - param_2) + param_2;
  do {
    iVar1 = param_2 * DAT_003af2a0 * 2;
    iVar2 = param_2 * (uint)*(ushort *)(DAT_003af28c + 1) * 2;
    param_2 = param_2 + 1;
    memcpy((void *)(DAT_003af29c + iVar1 + param_1 * 2),
           (void *)((int)DAT_003af28c + iVar2 + param_1 * 2 + *DAT_003af28c),(param_3 - param_1) * 2
          );
  } while (iVar3 != param_2);
  return;
}
