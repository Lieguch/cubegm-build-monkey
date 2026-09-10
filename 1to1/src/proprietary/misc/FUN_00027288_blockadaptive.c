/* ============================================================
 * blockadaptive   @ 0x00027288   size=272B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

void blockadaptive(int *param_1,int *param_2)

{
  int iVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  int iVar9;
  int iVar10;
  int iVar11;
  int iVar12;
  int iVar13;
  undefined2 *puVar14;
  undefined2 *puVar15;
  int iVar16;
  int iVar17;
  int iVar18;
  int local_48;
  
  iVar12 = param_1[2];
  iVar5 = param_1[1];
  iVar3 = param_1[4] - iVar12;
  iVar11 = param_2[3];
  iVar9 = param_1[3] - iVar5;
  iVar18 = param_2[1];
  iVar16 = param_2[4];
  iVar4 = param_2[2];
  if (0 < iVar3) {
    iVar6 = iVar3 + iVar12;
    local_48 = 0;
    do {
      if (0 < iVar9) {
        iVar7 = *param_1;
        iVar8 = param_1[5];
        iVar1 = __aeabi_idiv(local_48,iVar3);
        iVar17 = param_2[5];
        iVar10 = *param_2;
        iVar13 = 0;
        puVar14 = (undefined2 *)(iVar7 + iVar5 * 2 + iVar8 * iVar12);
        do {
          iVar2 = __aeabi_idiv(iVar13,iVar9);
          puVar15 = puVar14 + 1;
          *puVar14 = *(undefined2 *)(iVar10 + iVar2 * 2 + iVar17 * iVar1);
          iVar13 = iVar13 + (iVar11 - iVar18);
          puVar14 = puVar15;
        } while (puVar15 != (undefined2 *)(iVar7 + (iVar9 + iVar5) * 2 + iVar8 * iVar12));
      }
      iVar12 = iVar12 + 1;
      local_48 = (iVar16 - iVar4) + local_48;
    } while (iVar6 != iVar12);
  }
  return;
}
