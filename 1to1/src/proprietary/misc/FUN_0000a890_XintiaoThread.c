/* ============================================================
 * XintiaoThread   @ 0x0000a890   size=20B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void XintiaoThread(void)

{
  do {
    xintiao();
    usleep(20000);
  } while( true );
}
