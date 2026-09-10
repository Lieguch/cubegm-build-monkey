/* ============================================================
 * mui_UnDispBlock   @ 0x00014584   size=128B   callers=6
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_UnDispBlock(int param_1,int param_2,int *param_3,int param_4)

{
  int iVar1;
  uint uVar2;
  int iVar3;
  uint uVar4;
  
  uVar2 = (uint)*(ushort *)((int)param_3 + param_4 * 0x10 + 10);
  if ((int)(*(ushort *)((int)param_3 + param_4 * 0x10 + 0xe) - uVar2) < 1) {
    return;
  }
  iVar1 = 0;
  do {
    uVar4 = (uint)*(ushort *)(param_3 + param_4 * 4 + 2);
    iVar3 = iVar1 + uVar2;
    iVar1 = iVar1 + 1;
    memcpy((void *)(param_1 + param_2 * iVar3 + uVar4 * 2),
           (void *)((int)param_3 + *param_3 + (iVar3 * (uint)*(ushort *)(param_3 + 1) + uVar4) * 2),
           (*(ushort *)(param_3 + param_4 * 4 + 3) - uVar4) * 2);
    uVar2 = (uint)*(ushort *)((int)param_3 + param_4 * 0x10 + 10);
  } while (iVar1 < (int)(*(ushort *)((int)param_3 + param_4 * 0x10 + 0xe) - uVar2));
  return;
}
