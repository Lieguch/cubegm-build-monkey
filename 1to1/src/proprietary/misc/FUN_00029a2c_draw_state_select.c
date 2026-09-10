/* ============================================================
 * draw_state_select   @ 0x00029a2c   size=272B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void draw_state_select(int param_1,int param_2,int param_3)

{
  int iVar1;
  int iVar2;
  gh_u2 *puVar3;
  int iVar4;
  gh_uint uVar5;
  gh_uint uVar6;
  int iVar7;
  gh_u2 *puVar8;
  gh_uint uVar9;
  
  iVar2 = DAT_003af2b8;
  iVar1 = DAT_003af2a0;
  if (param_3 == 0) {
    puVar8 = (gh_u2 *)(DAT_003af29c + (DAT_003af2a0 * param_2 + param_1) * 2);
    iVar7 = 0;
    do {
      iVar4 = 0;
      puVar3 = puVar8;
      do {
        if ((0x9f < iVar4 - 4U) || (0x9f < iVar7 - 4U)) {
          *puVar3 = *(gh_u2 *)
                     (iVar2 + (((gh_uint)*(gh_ushort *)(iVar2 + 0x7c) - (gh_uint)*(gh_ushort *)(iVar2 + 0x78)) *
                               ((param_2 - (gh_uint)*(gh_ushort *)(iVar2 + 0x7a)) + iVar7) +
                              (param_1 - (gh_uint)*(gh_ushort *)(iVar2 + 0x78)) + iVar4) * 2 +
                     *(int *)(iVar2 + 0x70));
        }
        iVar4 = iVar4 + 1;
        puVar3 = puVar3 + 1;
      } while (iVar4 != 0xa8);
      iVar7 = iVar7 + 1;
      puVar8 = puVar8 + iVar1;
    } while (iVar7 != 0xa8);
    return;
  }
  uVar9 = 0xfffffffc;
  puVar8 = (gh_u2 *)(DAT_003af29c + (DAT_003af2a0 * param_2 + param_1) * 2);
  do {
    puVar3 = puVar8;
    uVar5 = 0xfffffffc;
    do {
      uVar6 = uVar5 + 1;
      if ((0x9f < uVar5) || (0x9f < uVar9)) {
        *puVar3 = (short)param_3;
      }
      puVar3 = puVar3 + 1;
      uVar5 = uVar6;
    } while (uVar6 != 0xa4);
    uVar9 = uVar9 + 1;
    puVar8 = puVar8 + iVar1;
  } while (uVar9 != 0xa4);
  return;
}
