/* ============================================================
 * InitScr   @ 0x00029ce8   size=80B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void InitScr(void)

{
  scr_h_size = 0x1e0;
  scr_v_size = 0x110;
  if (scr_buf != (void *)0x0) {
    return;
  }
  scr_buf = malloc(0x3fc00);
  return;
}
