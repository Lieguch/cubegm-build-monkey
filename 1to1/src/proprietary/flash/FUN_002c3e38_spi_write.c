/* ============================================================
 * spi_write   @ 0x002c3e38   size=96B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void spi_write(gh_u4 param_1,gh_u4 param_2,gh_u4 param_3)

{
  int iVar1;
  gh_u4 local_18;
  gh_u4 local_14;
  
  local_18 = 0x5002;
  local_14 = 0;
  snor_write_en();
  iVar1 = sfc_request(&local_18,param_1,param_2,param_3);
  if (iVar1 == 0) {
    snor_wait_busy(10000);
  }
  return;
}
