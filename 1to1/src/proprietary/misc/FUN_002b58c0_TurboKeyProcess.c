/* ============================================================
 * TurboKeyProcess   @ 0x002b58c0   size=224B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

void TurboKeyProcess(void)

{
  uint uVar1;
  int *piVar2;
  uint uVar3;
  uint *puVar4;
  uint uVar5;
  undefined1 *puVar6;
  undefined1 *puVar7;
  uint *puVar8;
  uint uVar9;
  
  uVar1 = turbo_delay;
  puVar6 = game_joy_key;
  puVar7 = user_joy_key_trubo;
  puVar8 = (uint *)joy_key;
  do {
    uVar9 = *puVar8;
    uVar3 = 0x400;
    *(uint *)puVar6 = uVar9;
    piVar2 = (int *)STD_index;
    puVar4 = (uint *)puVar7;
    while( true ) {
      if ((uVar9 & uVar3) == 0) {
        if (*puVar4 != 0) {
          *puVar4 = 1;
        }
      }
      else {
        uVar5 = *puVar4 + 1;
        if ((*puVar4 != 0) && (*puVar4 = uVar5, (uVar5 & uVar1) != 0)) {
          *(uint *)puVar6 = uVar3 ^ *(uint *)puVar6;
        }
      }
      if (puVar4 + 1 == (uint *)((int)puVar7 + 0x18)) break;
      puVar4 = puVar4 + 1;
      piVar2 = piVar2 + 1;
      uVar3 = *(uint *)(joy_key_mask + *piVar2 * 4);
    }
    puVar6 = (undefined1 *)((int)puVar6 + 4);
    puVar7 = (undefined1 *)((int)puVar7 + 0x40);
    puVar8 = puVar8 + 1;
  } while (puVar6 != joy_key);
  return;
}
