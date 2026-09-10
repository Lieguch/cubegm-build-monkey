/* ============================================================
 * SPI_RR   @ 0x0000ca48   size=92B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_uint SPI_RR(void)

{
  int iVar1;
  char cVar2;
  gh_uint uVar3;
  
  cVar2 = '\b';
  uVar3 = 0;
  do {
    sunxi_gpio_output(1,0);
    sunxi_gpio_output(1);
    iVar1 = sunxi_gpio_input(2);
    uVar3 = (uVar3 & 0x7f) << 1;
    cVar2 = cVar2 + -1;
    if (iVar1 != 0) {
      uVar3 = uVar3 | 1;
    }
  } while (cVar2 != '\0');
  sunxi_gpio_output(1,0);
  return uVar3;
}
