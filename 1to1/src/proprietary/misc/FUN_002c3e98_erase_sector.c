/* ============================================================
 * erase_sector   @ 0x002c3e98   size=100B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void erase_sector(gh_u4 param_1)

{
  int iVar1;
  gh_u4 local_18;
  gh_u4 local_14;
  
  local_14 = 0;
  local_18 = 0x40d8;
  snor_write_en();
  iVar1 = sfc_request(&local_18,param_1,0,0);
  if (iVar1 == 0) {
    snor_wait_busy(&DAT_00061a80);
  }
  return;
}
