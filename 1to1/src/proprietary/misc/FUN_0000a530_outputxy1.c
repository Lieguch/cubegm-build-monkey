/* ============================================================
 * outputxy1   @ 0x0000a530   size=416B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void outputxy1(byte *param_1)

{
  uint uVar1;
  int iVar2;
  int iVar3;
  undefined2 *puVar4;
  undefined2 *puVar5;
  uint uVar6;
  byte *pbVar7;
  int iVar8;
  byte *pbVar9;
  undefined2 *puVar10;
  undefined2 *puVar11;
  
  iVar8 = output_x;
  do {
    iVar2 = output_y;
    uVar6 = (uint)*param_1;
    if (uVar6 == 0) {
      output_x = iVar8;
      return;
    }
    while (iVar3 = scr_h_size, param_1 = param_1 + 1, uVar6 != 10) {
      if ((uVar6 & 0x80) == 0) {
        pbVar9 = &asc2_1608 + (uVar6 - 0x20) * 0x10;
      }
      else {
        pbVar9 = &DAT_002e0d18;
      }
      pbVar7 = pbVar9 + 0x10;
      puVar10 = (undefined2 *)(scr_data + (scr_h_size * iVar2 + iVar8) * 2);
      puVar11 = puVar10;
      do {
        uVar6 = 7;
        puVar4 = puVar10;
        puVar5 = puVar11;
        do {
          uVar1 = uVar6 & 0xff;
          uVar6 = uVar6 - 1;
          if (((int)(uint)*pbVar9 >> uVar1 & 1U) == 0) {
            *puVar4 = 0;
          }
          else {
            *puVar5 = 0x7fff;
          }
          puVar4 = puVar4 + 1;
          puVar5 = puVar5 + 1;
        } while (uVar6 != 0xffffffff);
        pbVar9 = pbVar9 + 1;
        puVar11 = puVar11 + iVar3;
        puVar10 = puVar10 + iVar3;
      } while (pbVar9 != pbVar7);
      uVar6 = (uint)*param_1;
      iVar8 = iVar8 + 8;
      if (uVar6 == 0) {
        output_x = iVar8;
        return;
      }
    }
    output_y = Rowspacing + output_y;
    if (scr_v_size + Rowspacing * -2 < output_y) {
      iVar8 = Rowspacing * 2 + 0x12;
      memcpy((void *)(scr_data + scr_h_size * (Rowspacing + 0x12) * 2),
             (void *)(scr_data + iVar8 * scr_h_size * 2),scr_h_size * (scr_v_size - iVar8) * 2);
      output_y = output_y - Rowspacing;
    }
    iVar8 = 0x14;
  } while( true );
}
