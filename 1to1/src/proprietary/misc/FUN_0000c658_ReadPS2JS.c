/* ============================================================
 * ReadPS2JS   @ 0x0000c658   size=384B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void ReadPS2JS(gh_uint param_1,gh_byte *param_2,gh_byte *param_3)

{
  gh_uint uVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  int local_38;
  int local_30;
  int local_28;
  
  iVar3 = 8;
  do {
    uVar1 = param_1 & 1;
    param_1 = param_1 >> 1;
    iVar4 = 5;
    sunxi_gpio_output(0xc9,uVar1 != 0);
    do {
      local_30 = 0;
      do {
        local_30 = local_30 + 1;
      } while (local_30 < 0x27);
      iVar4 = iVar4 + -1;
    } while (iVar4 != 0);
    *param_2 = *param_2 >> 1;
    *param_3 = *param_3 >> 1;
    sunxi_gpio_output(0xc6,0);
    iVar4 = 5;
    do {
      local_38 = 0;
      do {
        local_38 = local_38 + 1;
      } while (local_38 < 0x27);
      iVar4 = iVar4 + -1;
    } while (iVar4 != 0);
    iVar4 = sunxi_gpio_input(200);
    if (iVar4 != 0) {
      *param_2 = ~((gh_byte)~(gh_byte)(((gh_uint)*param_2 << 0x19) >> 0x18) >> 1);
    }
    iVar4 = sunxi_gpio_input(0xc5);
    iVar2 = 5;
    if (iVar4 != 0) {
      *param_3 = ~((gh_byte)~(gh_byte)(((gh_uint)*param_3 << 0x19) >> 0x18) >> 1);
    }
    do {
      local_28 = 0;
      do {
        local_28 = local_28 + 1;
      } while (local_28 < 0x27);
      iVar2 = iVar2 + -1;
    } while (iVar2 != 0);
    sunxi_gpio_output(0xc6,1);
    iVar3 = iVar3 + -1;
  } while (iVar3 != 0);
  return;
}
