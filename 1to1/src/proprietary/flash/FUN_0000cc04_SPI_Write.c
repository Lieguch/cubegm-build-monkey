/* ============================================================
 * SPI_Write   @ 0x0000cc04   size=80B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SPI_Write(undefined4 param_1,undefined4 param_2)

{
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(0);
  SPI_WW(param_1);
  SPI_WW(param_2);
  sunxi_gpio_output(0,1);
  sunxi_gpio_output(2,1);
  return;
}
