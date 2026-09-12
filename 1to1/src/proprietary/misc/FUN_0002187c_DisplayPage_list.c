/* ============================================================
 * DisplayPage_list   @ 0x0002187c   size=248B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DisplayPage_list(int param_1,gh_u4 param_2,int param_3)

{
  int iVar1;
  int iVar2;
  int local_48;
  int local_44;
  int local_40;
  int local_3c;
  int local_38;
  int local_34;
  gh_u4 local_30;
  int local_2c;
  int local_28;
  int local_24;
  int local_20;
  int local_1c;
  
  local_40 = DAT_003af724;
  OutRect._16_4_ = DAT_003af720 + DAT_003af728;
  local_3c = OutRect._16_4_ + 8;
  local_48 = (int)DAT_003af294 + *DAT_003af294;
  OutRect._8_4_ = DAT_003af720;
  local_38 = DAT_003af724 + DAT_003af72c;
  OutRect._12_4_ = DAT_003af724;
  local_30 = (int)DAT_003af29c;
  local_34 = DAT_003af2a0 << 1;
  local_44 = DAT_003af720 + -8;
  local_2c = local_44;
  local_28 = local_40;
  local_24 = local_3c;
  local_20 = local_38;
  local_1c = local_34;
  OutRect._20_4_ = local_38;
  mui_blockcopy((int *)&local_30,(int *)&local_48);
  if ((0 < DAT_003af394) && (param_1 != param_3)) {
    iVar1 = 0;
    do {
      iVar2 = iVar1 + 1;
      DisplayLine_list(param_1,iVar1,param_2);
      if (DAT_003af394 <= iVar2) {
        return;
      }
      iVar1 = iVar2;
    } while (param_3 != iVar2 + param_1);
  }
  return;
}
