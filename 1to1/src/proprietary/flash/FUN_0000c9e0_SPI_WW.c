/* ============================================================
 * SPI_WW   @ 0x0000c9e0   size=104B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SPI_WW(gh_uint param_1)

{
  char cVar1;
  
  cVar1 = '\b';
  do {
    sunxi_gpio_output(1,0);
    sunxi_gpio_output(2,(param_1 & 0x80) != 0);
    param_1 = (param_1 & 0x7f) << 1;
    
  /* ★ 2026-10-23（R262）实参修复：工厂 ca10-ca14：`mov r1,#1 ; mov r0,r1` ⇒ output(1,**1**)。Ghidra 把该常量丢了 ⇒ 必须写全两个实参。
   *   少参数会用到 r1 的残留值（C 里是未定义行为）⇒ CS/CLK/MOSI 电平随机
   *   ⇒ RF 按键芯片不回话 ⇒ InitRFJoystick 自检 SPI_Read(5)!=0xa5
   *   ⇒ 按键线程不创建 ⇒ 画面静止、无任何操作（真机第 4 轮实证）。 */
  sunxi_gpio_output(1,1);
    cVar1 = cVar1 + -1;
  } while (cVar1 != '\0');
  sunxi_gpio_output(1,0);
  sunxi_gpio_output(2,1);
  return;
}
