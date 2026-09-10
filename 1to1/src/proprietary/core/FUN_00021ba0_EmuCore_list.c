/* ============================================================
 * EmuCore_list   @ 0x00021ba0   size=100B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void EmuCore_list(int param_1,undefined4 param_2,int param_3)

{
  int iVar1;
  int iVar2;
  
  OutRect._12_4_ = 0xda;
  OutRect._8_4_ = 0x182;
  OutRect._20_4_ = 0x23a;
  OutRect._16_4_ = 0x38e;
  iVar1 = 0;
  do {
    iVar2 = iVar1 + 1;
    if (iVar1 == param_3 - param_1) {
      return;
    }
    EmuCore_Line(param_1,iVar1,param_2);
    iVar1 = iVar2;
  } while (iVar2 != 7);
  return;
}
