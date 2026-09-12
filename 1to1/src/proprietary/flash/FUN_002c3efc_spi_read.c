/* ============================================================
 * spi_read   @ 0x002c3efc   size=68B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 spi_read(gh_u4 param_1,gh_u4 param_2,gh_u4 param_3) /* 原厂 r0 = sfc_request 返回值 */

{
  gh_u4 local_10;
  gh_u4 local_c;
  
  local_c = 0;
  local_10 = 0x4003;
  return sfc_request(&local_10,param_1,(gh_uint *)param_2,param_3);
}
