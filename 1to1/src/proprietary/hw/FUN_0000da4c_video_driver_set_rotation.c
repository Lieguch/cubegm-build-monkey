/* ============================================================
 * video_driver_set_rotation   @ 0x0000da4c   size=68B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void video_driver_set_rotation(undefined4 param_1)

{
  printf("video_driver_set_rotation: %X\n",param_1);
  if (set_rotation == (code *)0x0) {
    return;
  }
                    /* WARNING: Could not recover jumptable at 0x0000da8c. Too many branches */
                    /* WARNING: Treating indirect jump as call */
  (*set_rotation)(param_1);
  return;
}
