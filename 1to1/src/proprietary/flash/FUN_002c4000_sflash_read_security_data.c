/* ============================================================
 * sflash_read_security_data   @ 0x002c4000   size=68B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void sflash_read_security_data(undefined4 param_1,undefined4 param_2)

{
  undefined4 local_10;
  undefined4 local_c;
  
  local_c = 0;
  local_10 = 0x4848;
  sfc_request(&local_10,param_2,param_1,0x100);
  return;
}
