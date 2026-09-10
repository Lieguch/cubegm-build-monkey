/* ============================================================
 * joystick_input   @ 0x002b4f48   size=68B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

bool joystick_input(uint param_1,undefined4 param_2,undefined4 param_3,int param_4)

{
  if (3 < param_1) {
    return false;
  }
  return (*(uint *)(game_joy_key + param_1 * 4) &
         *(uint *)(user_joy_key_mask + (param_4 + param_1 * 0x10) * 4)) != 0;
}
