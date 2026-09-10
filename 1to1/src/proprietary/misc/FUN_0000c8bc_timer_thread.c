/* ============================================================
 * timer_thread   @ 0x0000c8bc   size=16B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void timer_thread(void)

{
  ReadJoystickProc();
  processvblank();
  return;
}
