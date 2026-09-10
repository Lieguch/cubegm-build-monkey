/* ============================================================
 * DeinitSound   @ 0x0000dbcc   size=12B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DeinitSound(void)

{
  run_process_constprop_0("sound_driver_deinit");
  return;
}
