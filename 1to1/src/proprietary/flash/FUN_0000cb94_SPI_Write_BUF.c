/* ============================================================
 * SPI_Write_BUF   @ 0x0000cb94   size=112B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SPI_Write_BUF(gh_u4 param_1,int param_2,gh_u1 *param_3)

{
  gh_u1 *puVar1;
  
  sunxi_gpio_set_cfgpin(2,1);
  
  /* ★ 2026-10-23（R262）实参修复：工厂 cbb0-cbb4：`mov r1,#0 ; mov r0,r1` ⇒ output(0,**0**) ⇒ 必须写全两个实参。
   *   少参数会用到 r1 的残留值（C 里是未定义行为）⇒ CS/CLK/MOSI 电平随机
   *   ⇒ RF 按键芯片不回话 ⇒ InitRFJoystick 自检 SPI_Read(5)!=0xa5
   *   ⇒ 按键线程不创建 ⇒ 画面静止、无任何操作（真机第 4 轮实证）。 */
  sunxi_gpio_output(0,0);
  SPI_WW(param_1);
  if (param_2 != 0) {
    puVar1 = (gh_u1 *)(param_3 + -1);
    do {
      puVar1 = puVar1 + 1;
      SPI_WW(*puVar1);
    } while (puVar1 != (gh_u1 *)(param_3 + (param_2 - 1U & 0xff)));
  }
  sunxi_gpio_output(0,1);
  sunxi_gpio_output(2,1);
  return;
}
