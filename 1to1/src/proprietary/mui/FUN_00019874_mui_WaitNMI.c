/* ============================================================
 * mui_WaitNMI   @ 0x00019874   size=144B   callers=14
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_WaitNMI(void)

{
  int iVar1;
  int iVar2;
  int iVar3;
  
  if (ForceFlashCount < 0x40) {
    ForceFlashCount = ForceFlashCount + 1;
  }
  else {
    ForceFlashCount = 0;
  }
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  iVar2 = m_time0;
  iVar1 = diff_prev;
  diff_prev = diff_prev + 1;
  iVar3 = GetTicks();
  iVar3 = ((iVar1 * 1000) / 0x3c + iVar2) - iVar3;
  if (0 < iVar3) {
    usleep(iVar3 * 1000);
    return;
  }
  return;
}
