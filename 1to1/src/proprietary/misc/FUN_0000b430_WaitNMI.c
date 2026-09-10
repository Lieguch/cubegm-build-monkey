/* ============================================================
 * WaitNMI   @ 0x0000b430   size=116B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

void WaitNMI(void)

{
  longlong lVar1;
  uint uVar2;
  int iVar3;
  longlong lVar4;
  
  while( true ) {
    lVar4 = GetTick();
    lVar1 = lVar4 + CONCAT44(((int)diff_prev >> 0x1f) -
                             (frame_time_last._4_4_ + (uint)(diff_prev < (uint)frame_time_last)),
                             diff_prev - (uint)frame_time_last);
    uVar2 = (uint)lVar1;
    iVar3 = (int)((ulonglong)lVar1 >> 0x20);
    if ((int)-(iVar3 + (uint)(16000 < uVar2)) < 0 !=
        (SBORROW4(0,iVar3) != SBORROW4(-iVar3,(uint)(16000 < uVar2)))) break;
    usleep(1000);
  }
  frame_time_last = lVar4;
  diff_prev = uVar2 - 0x411b;
  return;
}
