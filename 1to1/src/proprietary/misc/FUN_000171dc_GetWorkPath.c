/* ============================================================
 * GetWorkPath   @ 0x000171dc   size=20B   callers=18
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined1 * GetWorkPath(void)

{
  return work_path;
}
