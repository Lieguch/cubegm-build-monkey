/* ============================================================
 * DrawFrame   @ 0x002b53a8   size=520B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DrawFrame(undefined2 *param_1,int param_2,int param_3,int param_4)

{
  undefined2 *puVar1;
  undefined2 *puVar2;
  undefined2 *puVar3;
  undefined2 *puVar4;
  int iVar5;
  int iVar6;
  undefined2 *puVar7;
  int iVar8;
  undefined2 *puVar9;
  
  puVar1 = rotation_buff;
  if (param_1 == (undefined2 *)0x0) {
    return;
  }
  if (FrameSkip != 0) {
    return;
  }
  DispFrameCount = DispFrameCount + 1;
  iVar5 = param_3;
  iVar6 = param_2;
  puVar2 = param_1;
  this_frame._0_4_ = param_1;
  this_frame._4_4_ = param_2;
  this_frame._8_4_ = param_3;
  this_frame._12_4_ = param_4;
  if (soft_rotation == 0) goto LAB_002b5440;
  iVar6 = param_3;
  if (rotation == 1) {
    if (param_2 != 0) {
      param_4 = param_3 * 2;
      puVar7 = param_1 + param_2 + -1;
      puVar4 = rotation_buff;
      do {
        if (param_3 != 0) {
          puVar9 = puVar4 + param_3;
          puVar2 = puVar7;
          puVar3 = puVar4;
          do {
            puVar4 = puVar3 + 1;
            *puVar3 = *puVar2;
            puVar2 = puVar2 + param_2;
            puVar3 = puVar4;
          } while (puVar4 != puVar9);
        }
        puVar7 = puVar7 + -1;
        iVar5 = param_2;
        puVar2 = puVar1;
      } while (puVar7 != param_1 + -1);
      goto LAB_002b5440;
    }
  }
  else {
    if (rotation != 3) {
      iVar6 = param_2;
      if (rotation == 2) {
        param_3 = param_3 * param_2;
        if (param_3 != 0) {
          param_1 = param_1 + param_3 + -0x80000000;
          puVar4 = rotation_buff + param_3 + -0x80000000;
          puVar2 = rotation_buff;
          do {
            param_1 = param_1 + -1;
            puVar7 = puVar2 + 1;
            *puVar2 = *param_1;
            puVar2 = puVar7;
          } while (puVar7 != puVar4);
        }
        param_4 = param_2 << 1;
        puVar2 = puVar1;
      }
      goto LAB_002b5440;
    }
    if (param_2 != 0) {
      param_4 = param_3 * 2;
      iVar8 = param_2 * (param_3 + 0x7fffffff);
      puVar7 = param_1 + iVar8;
      puVar4 = rotation_buff;
      do {
        if (param_3 != 0) {
          puVar9 = puVar4 + param_3;
          puVar2 = puVar7;
          puVar3 = puVar4;
          do {
            puVar4 = puVar3 + 1;
            *puVar3 = *puVar2;
            puVar2 = puVar2 + -param_2;
            puVar3 = puVar4;
          } while (puVar4 != puVar9);
        }
        puVar7 = puVar7 + 1;
        iVar5 = param_2;
        puVar2 = puVar1;
      } while (param_1 + param_2 + iVar8 != puVar7);
      goto LAB_002b5440;
    }
  }
  param_4 = param_3 << 1;
  iVar5 = param_2;
  puVar2 = puVar1;
LAB_002b5440:
  if (displayfps != 0) {
    UIDebug(puVar2,iVar6,iVar5,param_4);
  }
  dispFlip(puVar2,iVar6,iVar5,param_4);
  return;
}
