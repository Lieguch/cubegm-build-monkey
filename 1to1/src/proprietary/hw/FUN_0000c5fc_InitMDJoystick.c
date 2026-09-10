/* ============================================================
 * InitMDJoystick   @ 0x0000c5fc   size=92B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void InitMDJoystick(void)

{
  sunxi_gpio_set_cfgpin(0x109,0);
  sunxi_gpio_set_cfgpin(0x84,0);
  sunxi_gpio_set_cfgpin(0x85,0);
  sunxi_gpio_set_cfgpin(0x86,0);
  sunxi_gpio_set_cfgpin(0x89,0);
  sunxi_gpio_set_cfgpin(0x88,1);
  sunxi_gpio_set_cfgpin(0x87,0);
  return;
}
