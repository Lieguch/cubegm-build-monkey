/* ============================================================
 * ReadJoystick   @ 0x0000c8f0   size=204B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 ReadJoystick(void)

{
  gh_u4 uVar1;
  
  ReadJoystickProc();
  if ((joy_key_blob._0_4_ != joytemp0) || (joy_key_blob._4_4_ != joytemp1)) {
    joytemp0 = joy_key_blob._0_4_;
    joytemp1 = joy_key_blob._4_4_;
  }
  if (joy_key_blob._0_4_ != 0) {
    if (joy_key_blob._0_4_ != Joy1_Press) {
      Joy1_Press = joy_key_blob._0_4_;
      Joy1_Delay = 0;
      return joy_key_blob._0_4_;
    }
    Joy1_Delay = Joy1_Delay + 1;
    if (Joy1_Delay < 0x27) {
      uVar1 = 0;
    }
    else {
      Joy1_Delay = 0x1e;
      uVar1 = joy_key_blob._0_4_;
    }
    return uVar1;
  }
  Joy1_Delay = 0;
  Joy1_Press = 0;
  return 0;
}
