/* ============================================================
 * SPI_Read_BUF   @ 0x0000cb0c   size=136B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SPI_Read_BUF(gh_u4 param_1,int param_2,int param_3)

{
  gh_u1 uVar1;
  gh_u1 *puVar2;
  
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(0);
  SPI_WW(param_1);
  sunxi_gpio_set_cfgpin(2,0);
  if (param_2 != 0) {
    puVar2 = (gh_u1 *)(param_3 + -1);
    do {
      uVar1 = SPI_RR();
      puVar2 = puVar2 + 1;
      *puVar2 = uVar1;
    } while (puVar2 != (gh_u1 *)(param_3 + (param_2 - 1U & 0xff)));
  }
  sunxi_gpio_output(0,1);
  sunxi_gpio_set_cfgpin(2,1);
  sunxi_gpio_output(2,1);
  return;
}
