/* ============================================================
 * mui_DisplayGameSum   @ 0x0001bf80   size=232B   callers=5
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_DisplayGameSum(void)

{
  undefined4 uVar1;
  int iVar2;
  int iVar3;
  undefined4 uStack_98;
  undefined *puStack_94;
  
  iVar3 = DAT_003af318;
  iVar2 = DAT_003af314;
  OutRect._16_4_ = DAT_003af31c;
  OutRect._8_4_ = DAT_003af314;
  OutRect._12_4_ = DAT_003af318;
  OutRect._20_4_ = DAT_003af320;
  mui_Undisplay(DAT_003af314,DAT_003af318,DAT_003af31c,DAT_003af320);
  uVar1 = DAT_003af394;
  if (DAT_003af288 == 0) {
    uStack_98 = 0x2f2d2020;
    puStack_94 = &DAT_0020202d;
  }
  else {
    iVar2 = __aeabi_idiv(DAT_003af288,DAT_003af394);
    iVar3 = __aeabi_idiv(DAT_003af278 + DAT_003af27c,uVar1);
    sprintf((char *)&uStack_98,"%3d/%3d",iVar3 + 1,iVar2 + 1);
    iVar2 = OutRect._8_4_;
    iVar3 = OutRect._12_4_;
  }
  mui_outputxy_t(DAT_003af29c,iVar2 + 8,iVar3 + 6,(undefined1)DAT_003af324,DAT_003af328,&uStack_98);
  return;
}
