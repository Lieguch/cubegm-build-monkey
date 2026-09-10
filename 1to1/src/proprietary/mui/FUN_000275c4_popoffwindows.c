/* ============================================================
 * popoffwindows   @ 0x000275c4   size=484B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

void popoffwindows(undefined4 *param_1)

{
  void *pvVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  int iVar9;
  undefined4 local_58;
  undefined4 local_54;
  undefined4 local_50;
  int local_4c;
  int local_48;
  int local_44;
  int local_40;
  int local_3c;
  int local_38;
  int local_34;
  int local_30;
  int local_2c;
  
  iVar5 = param_1[2];
  iVar2 = param_1[1];
  local_58 = *param_1;
  iVar4 = param_1[3] - iVar2;
  local_54 = 0;
  local_50 = 0;
  iVar7 = 5;
  iVar3 = param_1[4] - iVar5;
  local_44 = iVar4 * 2;
  local_4c = iVar4;
  local_48 = iVar3;
  while( true ) {
    pvVar1 = scrbuf;
    if (0 < iVar3) {
      iVar6 = 0;
      do {
        iVar5 = iVar6 + iVar5;
        iVar3 = iVar4 * iVar6;
        iVar6 = iVar6 + 1;
        memcpy((void *)(DAT_003af29c + (DAT_003af2a0 * iVar5 + iVar2) * 2),
               (void *)((int)pvVar1 + iVar3 * 2),iVar4 << 1);
        iVar5 = param_1[2];
        iVar2 = param_1[1];
        iVar3 = param_1[4] - iVar5;
        iVar4 = param_1[3] - iVar2;
      } while (iVar6 < iVar3);
    }
    iVar9 = 5 - iVar7;
    iVar8 = iVar7 * iVar4;
    iVar6 = iVar7 * iVar3;
    iVar7 = iVar7 + -1;
    local_2c = DAT_003af2a0 << 1;
    local_38 = (iVar9 * iVar3) / 10 + iVar5;
    local_40 = DAT_003af29c;
    local_3c = (iVar9 * iVar4) / 10 + iVar2;
    local_30 = iVar6 / 5 + local_38;
    local_34 = iVar8 / 5 + local_3c;
    blockadaptive(&local_40,&local_58);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    usleep(18000);
    if (iVar7 == -1) break;
    iVar2 = param_1[1];
    iVar5 = param_1[2];
    iVar3 = param_1[4] - iVar5;
    iVar4 = param_1[3] - iVar2;
  }
  free(scrbuf);
  return;
}
