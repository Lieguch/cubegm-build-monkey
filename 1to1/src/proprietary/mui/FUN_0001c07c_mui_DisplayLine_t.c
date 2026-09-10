/* ============================================================
 * mui_DisplayLine_t   @ 0x0001c07c   size=660B   callers=5
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_DisplayLine_t(int param_1,int param_2,int param_3)

{
  undefined4 uVar1;
  int iVar2;
  char acStack_a8 [132];
  
  sprintf(acStack_a8,"%04d.%s",param_1 + DAT_003af278 + 1,
          &DAT_003b2324 + *(int *)((&m_ui)[m_ui + 0x16] + 0x40) * 0x80 + param_1 * 0x404);
  if (param_1 == param_2) {
    OutRect._8_4_ = (&DAT_003af398)[param_1 * 6];
    OutRect._20_4_ = (&DAT_003af3a4)[param_1 * 6];
    OutRect._16_4_ = (&DAT_003af3a0)[param_1 * 6];
    OutRect._12_4_ = (&DAT_003af39c)[param_1 * 6];
    iVar2 = mui_outputxy_t(DAT_003af29c,OutRect._8_4_ + param_3,OutRect._12_4_ + 7,
                           (undefined1)DAT_003af698,DAT_003af69c,acStack_a8);
    DAT_003af284 = OutRect._16_4_ - iVar2;
    if (((&DAT_003b2320)[param_1 * 0x101] & 0x80) != 0) {
      OutRect._8_4_ = (&DAT_003af398)[param_1 * 6] + DAT_003af6a0;
      OutRect._16_4_ = (&DAT_003af3a0)[param_1 * 6];
      OutRect._12_4_ = (&DAT_003af39c)[param_1 * 6] + DAT_003af6a4;
      OutRect._20_4_ = (&DAT_003af3a4)[param_1 * 6];
      mui_outputxy_t(DAT_003af29c,OutRect._8_4_,OutRect._12_4_,(undefined1)DAT_003af6a8,DAT_003af6ac
                     ,&DAT_003af6b0);
    }
    iVar2 = DAT_003af380;
    uVar1 = DAT_003af37c;
    OutRect._20_4_ = DAT_003af388;
    OutRect._8_4_ = DAT_003af37c;
    OutRect._16_4_ = DAT_003af384;
    OutRect._12_4_ = DAT_003af380;
    mui_Undisplay(DAT_003af37c,DAT_003af380,DAT_003af384,DAT_003af388);
    strcpy(acStack_a8,(char *)(&m_ui)[((&DAT_003b2320)[param_1 * 0x101] & 0x7f) + 0x32]);
    mui_outputxy_t(DAT_003af29c,uVar1,iVar2 + 4,(undefined1)DAT_003af38c,DAT_003af390,acStack_a8);
    return;
  }
  OutRect._8_4_ = (&DAT_003af398)[param_1 * 6];
  OutRect._20_4_ = (&DAT_003af3a4)[param_1 * 6];
  OutRect._12_4_ = (&DAT_003af39c)[param_1 * 6];
  OutRect._16_4_ = (&DAT_003af3a0)[param_1 * 6];
  mui_outputxy_t(DAT_003af29c,param_3 + OutRect._8_4_,OutRect._12_4_ + 7,
                 *(undefined1 *)(&DAT_003af3a8 + param_1 * 6),(&DAT_003af3ac)[param_1 * 6],
                 acStack_a8);
  if (((&DAT_003b2320)[param_1 * 0x101] & 0x80) == 0) {
    return;
  }
  OutRect._16_4_ = (&DAT_003af3a0)[param_1 * 6];
  OutRect._8_4_ = (&DAT_003af398)[param_1 * 6] + DAT_003af6a0;
  OutRect._12_4_ = (&DAT_003af39c)[param_1 * 6] + DAT_003af6a4;
  OutRect._20_4_ = (&DAT_003af3a4)[param_1 * 6];
  mui_outputxy_t(DAT_003af29c,OutRect._8_4_,OutRect._12_4_,(undefined1)DAT_003af6a8,DAT_003af6ac,
                 &DAT_003af6b0);
  return;
}
