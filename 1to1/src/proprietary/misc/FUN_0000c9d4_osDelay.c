/* ============================================================
 * osDelay   @ 0x0000c9d4   size=12B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void osDelay(int param_1)

{
  usleep(param_1 * 1000);
  return;
}
