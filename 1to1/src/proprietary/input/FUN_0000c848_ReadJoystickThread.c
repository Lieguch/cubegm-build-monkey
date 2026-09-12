/* ============================================================
 * ReadJoystickThread   @ 0x0000c848   size=100B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void ReadJoystickThread(void)

{
  do {
    ReadJoystickProc();
    if ((joy_key_blob._0_4_ != joytemp0) || (joy_key_blob._4_4_ != joytemp1)) {
      joytemp0 = joy_key_blob._0_4_;
      joytemp1 = joy_key_blob._4_4_;
    }
    processvblank();
    usleep(15000);
  } while( true );
}
