/* ============================================================
 * LoadDefaultState   @ 0x00026c5c   size=112B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void LoadDefaultState(void)

{
  undefined4 uVar1;
  undefined4 uVar2;
  int iVar3;
  char acStack_1010 [4100];
  
  uVar1 = GetWorkPath();
  uVar2 = gameType();
  sprintf(acStack_1010,"%ssaves/%03d/%s.sav",uVar1,uVar2,RomName);
  iVar3 = access(acStack_1010,0);
  if (iVar3 == 0) {
    retro_load_state(acStack_1010);
  }
  return;
}
