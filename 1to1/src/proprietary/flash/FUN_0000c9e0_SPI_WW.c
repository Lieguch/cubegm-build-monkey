/* ============================================================
 * SPI_WW   @ 0x0000c9e0   size=104B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SPI_WW(uint param_1)

{
  char cVar1;
  
  cVar1 = '\b';
  do {
    sunxi_gpio_output(1,0);
    sunxi_gpio_output(2,(param_1 & 0x80) != 0);
    param_1 = (param_1 & 0x7f) << 1;
    sunxi_gpio_output(1);
    cVar1 = cVar1 + -1;
  } while (cVar1 != '\0');
  sunxi_gpio_output(1,0);
  sunxi_gpio_output(2,1);
  return;
}
