/* ============================================================
 * DrawSelectBar   @ 0x00014340   size=164B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

void DrawSelectBar(int *param_1)

{
  int iVar1;
  ushort *puVar2;
  ushort *puVar3;
  uint uVar4;
  int iVar5;
  int iVar6;
  ushort *puVar7;
  int iVar8;
  
  iVar1 = DAT_003af2a0;
  iVar6 = param_1[3] - param_1[1];
  iVar5 = param_1[2] - *param_1;
  if (0 < iVar6) {
    puVar7 = (ushort *)(DAT_003af29c + (DAT_003af2a0 * param_1[1] + *param_1) * 2);
    iVar8 = 0;
    do {
      if (0 < iVar5) {
        puVar2 = puVar7;
        do {
          uVar4 = CONCAT22(*puVar2,*puVar2) & 0x7e0f81f;
          uVar4 = uVar4 + ((int)((0x7e0f81f - uVar4) * 5) >> 5) & 0x7e0f81f;
          puVar3 = puVar2 + 1;
          *puVar2 = (ushort)uVar4 | (ushort)(uVar4 >> 0x10);
          puVar2 = puVar3;
        } while (puVar7 + iVar5 != puVar3);
      }
      iVar8 = iVar8 + 1;
      puVar7 = puVar7 + iVar1;
    } while (iVar6 != iVar8);
    return;
  }
  return;
}
