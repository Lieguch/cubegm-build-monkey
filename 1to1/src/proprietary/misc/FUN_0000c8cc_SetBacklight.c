/* ============================================================
 * SetBacklight   @ 0x0000c8cc   size=28B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SetBacklight(int param_1)

{
  if (param_1 == 0) {
    sunxi_gpio_output(0xcb);
    return;
  }
  sunxi_gpio_output(0xcb,1);
  return;
}
