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
  /* ★★ 2026-09-20 修复（GAP 16.39）：**延时计数器必须是 volatile**。
   *   源码里这三段是 Ghidra 从工厂反编译出来的**忙等延时**：
   *       do { local_30 = 0; do { local_30 = local_30 + 1; } while (local_30 < 0x27); iVar4--; } while (iVar4);
   *   工厂侧（GCC 6.2.0）**完整保留**了这三段（"str r8,[sp,#8] / mov r3,#39 / ldr-cmp-bge / add-str /
   *   ldr-cmp-blt" 的嵌套循环，每段外层 5 次、内层 39 次）—— 那是 GPIO 位敲的**时序延时**，
   *   少了它 PS/2 读时序就变了。
   *   但**现代编译器（clang 与 GCC 14 实测均如此）把它整体判定为死代码并删除**：
   *     · 计数器是普通局部变量 ⇒ 被提升到寄存器 ⇒ 循环无任何可观察副作用 ⇒ 删除；
   *     · 实测：我们产物 `ReadPS2JS` 只剩 144 B / 36 条，**三段延时循环一条不剩**
   *       （工厂 384 B / 96 条）；换 GCC 14 更小（88 B）。
   *   ⇒ 加 `volatile` 强制每轮迭代做一次真实的存取，与工厂的"每次迭代写栈"行为一致。
   *   ★ 这是**语义修复**（时序/副作用），不是为了让体积数字好看。*/
  /* 下面三个 volatile 计数器对应上面三段延时循环的"必须真实执行"语义 */
  volatile int delay_a;
  volatile int delay_b;
  volatile int delay_c;
  
  iVar3 = 8;
  do {
    uVar1 = param_1 & 1;
    param_1 = param_1 >> 1;
    iVar4 = 5;
    sunxi_gpio_output(0xc9,uVar1 != 0);
    do {
      delay_a = 0;
      do {
        delay_a = delay_a + 1;
      } while (delay_a < 0x27);
      iVar4 = iVar4 + -1;
    } while (iVar4 != 0);
    *param_2 = *param_2 >> 1;
    *param_3 = *param_3 >> 1;
    sunxi_gpio_output(0xc6,0);
    iVar4 = 5;
    do {
      delay_b = 0;
      do {
        delay_b = delay_b + 1;
      } while (delay_b < 0x27);
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
      delay_c = 0;
      do {
        delay_c = delay_c + 1;
      } while (delay_c < 0x27);
      iVar2 = iVar2 + -1;
    } while (iVar2 != 0);
    sunxi_gpio_output(0xc6,1);
    iVar3 = iVar3 + -1;
  } while (iVar3 != 0);
  return;
}
