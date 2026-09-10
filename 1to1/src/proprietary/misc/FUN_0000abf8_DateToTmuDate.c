/* ============================================================
 * DateToTmuDate   @ 0x0000abf8   size=72B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DateToTmuDate(gh_uint param_1)

{
  printf("%d-%d-%d %d:%d:%d\n",(param_1 >> 0x19) + 0x7bc,(param_1 & 0x1ffffff) >> 0x15,
         (param_1 & 0x1fffff) >> 0x10,(param_1 & 0xffff) >> 0xb,(param_1 & 0x7ff) >> 5,
         (param_1 & 0x1f) << 1);
  return;
}
