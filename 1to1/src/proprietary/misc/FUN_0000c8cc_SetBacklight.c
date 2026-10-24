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
    
  /* ★ 2026-10-23（R262）实参修复：工厂 c8d4-c8d8：`subs r1,r0,#0`（相等支 r1=0）`mov r0,#203` ⇒ output(0xcb,**0**) ⇒ 必须写全两个实参。
   *   少参数会用到 r1 的残留值（C 里是未定义行为）⇒ CS/CLK/MOSI 电平随机
   *   ⇒ RF 按键芯片不回话 ⇒ InitRFJoystick 自检 SPI_Read(5)!=0xa5
   *   ⇒ 按键线程不创建 ⇒ 画面静止、无任何操作（真机第 4 轮实证）。 */
  sunxi_gpio_output(0xcb,0);
    return;
  }
  sunxi_gpio_output(0xcb,1);
  return;
}
