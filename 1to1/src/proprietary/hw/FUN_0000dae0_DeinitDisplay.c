/* ============================================================
 * DeinitDisplay   @ 0x0000dae0   size=32B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DeinitDisplay(void)

{
  run_process_constprop_0("video_driver_deinit");
  dlclose(handle);
  return;
}
