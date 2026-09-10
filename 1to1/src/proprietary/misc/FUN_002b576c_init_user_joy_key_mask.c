/* ============================================================
 * init_user_joy_key_mask   @ 0x002b576c   size=316B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void init_user_joy_key_mask(int param_1,undefined4 param_2)

{
  uint uVar1;
  int iVar2;
  uint uVar3;
  uint *puVar4;
  uint *puVar5;
  uint *puVar6;
  undefined1 *puVar7;
  uint *puVar8;
  int iVar9;
  undefined4 *puVar10;
  int *piVar11;
  uint local_88 [24];
  uint uStack_28;
  
  if (param_1 != 0) {
    puVar8 = local_88;
    puVar5 = (uint *)(param_1 + -4);
    puVar6 = puVar8;
    do {
      puVar5 = puVar5 + 1;
      uVar1 = *puVar5;
      uVar3 = 10;
      puVar4 = (uint *)STD_index;
      while( true ) {
        if ((uVar1 & 0xffff) == uVar3) {
          *puVar6 = uVar1 & 0x10000 | *puVar4;
        }
        if (puVar4 == (uint *)(STD_index + 0x14)) break;
        puVar4 = puVar4 + 1;
        uVar3 = *puVar4;
      }
      puVar6 = puVar6 + 1;
    } while (puVar6 != &uStack_28);
    iVar9 = 0;
    puVar7 = user_joy_key_mask;
    do {
      *(undefined4 *)((int)puVar7 + 0x28) = 0;
      uVar1 = 0x400;
      *(undefined4 *)((int)puVar7 + 0x2c) = 0;
      *(undefined4 *)((int)puVar7 + 0x24) = 0;
      *(undefined4 *)((int)puVar7 + 0x20) = 0;
      *(undefined4 *)puVar7 = 0;
      *(undefined4 *)((int)puVar7 + 4) = 0;
      puVar6 = puVar8;
      puVar10 = (undefined4 *)(user_joy_key_trubo + iVar9 * 0x40);
      piVar11 = (int *)STD_index;
      while( true ) {
        uVar3 = *puVar6;
        if ((int)uVar3 < 0x10000) {
          *puVar10 = 0;
        }
        iVar2 = iVar9 * 0x10 + (uVar3 & 0xffff);
        *(uint *)(user_joy_key_mask + iVar2 * 4) = *(uint *)(user_joy_key_mask + iVar2 * 4) | uVar1;
        if (0xffff < (int)uVar3) {
          *puVar10 = 1;
        }
        if (piVar11 == (int *)(STD_index + 0x14)) break;
        piVar11 = piVar11 + 1;
        uVar1 = *(uint *)(joy_key_mask + *piVar11 * 4);
        puVar6 = puVar6 + 1;
        puVar10 = puVar10 + 1;
      }
      iVar9 = iVar9 + 1;
      puVar7 = (undefined1 *)((int)puVar7 + 0x40);
      puVar8 = puVar8 + 6;
      turbo_delay = param_2;
    } while (iVar9 != 4);
  }
  return;
}
