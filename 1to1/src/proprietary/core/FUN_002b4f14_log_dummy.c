/* ============================================================
 * log_dummy   @ 0x002b4f14   size=52B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void log_dummy(uint param_1,undefined4 param_2)

{
  if (param_1 < 2) {
    return;
  }
  RARCH_LOG_V(param_2);
  return;
}
