/* ============================================================
 * TurboKeyProcess   @ 0x002b58c0   size=224B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void TurboKeyProcess(void)

{
  gh_uint uVar1;
  int *piVar2;
  gh_uint uVar3;
  gh_uint *puVar4;
  gh_uint uVar5;
  gh_u1 *puVar6;
  gh_u1 *puVar7;
  gh_uint *puVar8;
  gh_uint uVar9;
  
  uVar1 = turbo_delay;
  puVar6 = game_joy_key;
  puVar7 = user_joy_key_trubo;
  puVar8 = (gh_uint *)joy_key;
  do {
    uVar9 = *puVar8;
    uVar3 = 0x400;
    *(gh_uint *)puVar6 = uVar9;
    piVar2 = (int *)STD_index;
    puVar4 = (gh_uint *)puVar7;
    while( true ) {
      if ((uVar9 & uVar3) == 0) {
        if (*puVar4 != 0) {
          *puVar4 = 1;
        }
      }
      else {
        uVar5 = *puVar4 + 1;
        if ((*puVar4 != 0) && (*puVar4 = uVar5, (uVar5 & uVar1) != 0)) {
          *(gh_uint *)puVar6 = uVar3 ^ *(gh_uint *)puVar6;
        }
      }
      if (puVar4 + 1 == (gh_uint *)((int)puVar7 + 0x18)) break;
      puVar4 = puVar4 + 1;
      piVar2 = piVar2 + 1;
      uVar3 = *(gh_uint *)(joy_key_mask + *piVar2 * 4);
    }
    puVar6 = (gh_u1 *)((int)puVar6 + 4);
    puVar7 = (gh_u1 *)((int)puVar7 + 0x40);
    puVar8 = puVar8 + 1;
  } while (puVar6 != joy_key);
  return;
}
