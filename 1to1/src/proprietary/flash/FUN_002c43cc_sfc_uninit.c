/* ============================================================
 * sfc_uninit   @ 0x002c43cc   size=40B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 sfc_uninit(void)

{
  munmap(g_sfc_reg,0x400);
  g_sfc_reg = (void *)0x0;
  return 0;
}
