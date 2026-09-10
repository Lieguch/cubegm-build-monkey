/* ============================================================
 * SPI_Read   @ 0x0000caa4   size=104B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 SPI_Read(gh_u4 param_1)

{
  gh_u4 uVar1;
  
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(0);
  SPI_WW(param_1);
  sunxi_gpio_set_cfgpin(2,0);
  uVar1 = SPI_RR();
  sunxi_gpio_output(0,1);
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(2,1);
  return uVar1;
}
