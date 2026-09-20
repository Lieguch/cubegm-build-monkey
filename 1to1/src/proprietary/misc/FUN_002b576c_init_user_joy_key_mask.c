/* ============================================================
 * init_user_joy_key_mask   @ 0x002b576c   size=316B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void init_user_joy_key_mask(void *param_1,gh_u4 param_2)

{
  gh_uint uVar1;
  int iVar2;
  gh_uint uVar3;
  gh_uint *puVar4;
  gh_uint *puVar5;
  gh_uint *puVar6;
  gh_u1 *puVar7;
  gh_uint *puVar8;
  int iVar9;
  gh_u4 *puVar10;
  int *piVar11;
  gh_uint local_88 [24];
  /* ★★ 2026-09-20 修复（GAP 16.36）：删除 `gh_uint uStack_28;`。
   *   它是 Ghidra 把「数组末尾那个栈槽的**地址**」渲染成一个**独立局部对象**的产物。
   *   作为独立 C 对象，它的地址由编译器自行摆放 ⇒ `puVar6 != &uStack_28` 变成
   *   **静态可判**的条件：编译器把它放在 local_88 之下时条件恒真 ⇒ 循环后续全被判为
   *   **不可达而整段删除**。
   *   ── 实测（zig -Os，目标 arm-linux-gnueabihf.2.29）：
   *        修复前 .text=108 B(27 槽)、**整个目标文件只有 1 条重定位(STD_index)**；
   *        而源码引用的 user_joy_key_mask / user_joy_key_trubo / joy_key_mask /
   *        turbo_delay **一次也没被引用** —— 第二段循环 + 函数尾声被删光，
   *        第一段循环还失去终止测试变成**死循环**。
   *        修复后 .text=348 B(87 槽)、**6 条重定位**（5 个全局全部引用到），
   *        与工厂 316 B 之比 = *1.10x*（进入 OK 区）。
   *   ⇒ 改为与数组同源的下标式边界，使循环边界不依赖局部变量布局。
   *   ★ 判据依据：`tools/scan_dead_loop.py`（产物里出现**无出口循环**而源码无 `for(;;)`）。*/
  
  if (param_1 != 0) {
    puVar8 = local_88;
    puVar5 = (gh_uint *)(param_1 + -4);
    puVar6 = puVar8;
    do {
      puVar5 = puVar5 + 1;
      uVar1 = *puVar5;
      uVar3 = 10;
      puVar4 = (gh_uint *)STD_index;
      while( true ) {
        if ((uVar1 & 0xffff) == uVar3) {
          *puVar6 = uVar1 & 0x10000 | *puVar4;
        }
        if (puVar4 == (gh_uint *)(STD_index + 0x14)) break;
        puVar4 = puVar4 + 1;
        uVar3 = *puVar4;
      }
      puVar6 = puVar6 + 1;
    } while (puVar6 != local_88 + 24);
    iVar9 = 0;
    puVar7 = user_joy_key_mask;
    do {
      *(gh_u4 *)((int)puVar7 + 0x28) = 0;
      uVar1 = 0x400;
      *(gh_u4 *)((int)puVar7 + 0x2c) = 0;
      *(gh_u4 *)((int)puVar7 + 0x24) = 0;
      *(gh_u4 *)((int)puVar7 + 0x20) = 0;
      *(gh_u4 *)puVar7 = 0;
      *(gh_u4 *)((int)puVar7 + 4) = 0;
      puVar6 = puVar8;
      puVar10 = (gh_u4 *)(user_joy_key_trubo + iVar9 * 0x40);
      piVar11 = (int *)STD_index;
      while( true ) {
        uVar3 = *puVar6;
        if ((int)uVar3 < 0x10000) {
          *puVar10 = 0;
        }
        iVar2 = iVar9 * 0x10 + (uVar3 & 0xffff);
        *(gh_uint *)(user_joy_key_mask + iVar2 * 4) = *(gh_uint *)(user_joy_key_mask + iVar2 * 4) | uVar1;
        if (0xffff < (int)uVar3) {
          *puVar10 = 1;
        }
        if (piVar11 == (int *)(STD_index + 0x14)) break;
        piVar11 = piVar11 + 1;
        uVar1 = *(gh_uint *)(joy_key_mask + *piVar11 * 4);
        puVar6 = puVar6 + 1;
        puVar10 = puVar10 + 1;
      }
      iVar9 = iVar9 + 1;
      puVar7 = (gh_u1 *)((int)puVar7 + 0x40);
      puVar8 = puVar8 + 6;
      turbo_delay = param_2;
    } while (iVar9 != 4);
  }
  return;
}
