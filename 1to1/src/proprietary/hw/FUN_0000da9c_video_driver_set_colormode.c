/* ============================================================
 * video_driver_set_colormode   @ 0x0000da9c   size=60B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void video_driver_set_colormode(gh_u4 param_1)

{
  gh_u4 local_14;
  gh_u4 local_10;
  gh_u4 local_c;
  
  local_10 = 1;
  local_c = 1;
  local_14 = param_1;
  (*video_driver_setting)(&local_14);
  return;
}
