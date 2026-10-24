/* ============================================================
 * SPI_Read   @ 0x0000caa4   size=104B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

#ifdef CGM_DIAG_TRACE_INPUT
extern void cgm_probe_io(int tag, unsigned a, unsigned b);
#endif

gh_u4 SPI_Read(gh_u4 param_1)

{
  gh_u4 uVar1;
  
  sunxi_gpio_set_cfgpin(2,1);
  
  /* ★ 2026-10-23（R262）实参修复：工厂 cab8-cabc：`mov r1,#0 ; mov r0,r1` ⇒ output(0,**0**)（CS 拉低） ⇒ 必须写全两个实参。
   *   少参数会用到 r1 的残留值（C 里是未定义行为）⇒ CS/CLK/MOSI 电平随机
   *   ⇒ RF 按键芯片不回话 ⇒ InitRFJoystick 自检 SPI_Read(5)!=0xa5
   *   ⇒ 按键线程不创建 ⇒ 画面静止、无任何操作（真机第 4 轮实证）。 */
  sunxi_gpio_output(0,0);
  SPI_WW(param_1);
  sunxi_gpio_set_cfgpin(2,0);
  uVar1 = SPI_RR();
  sunxi_gpio_output(0,1);
  sunxi_gpio_set_cfgpin(2,1);
#ifdef CGM_DIAG_TRACE_INPUT
  cgm_probe_io('R', (unsigned)param_1, (unsigned)uVar1);
#endif
  sunxi_gpio_output(2,1);
  return uVar1;
}
