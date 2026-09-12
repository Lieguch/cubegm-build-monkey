/* ============================================================
 * WaitNMI   @ 0x0000b430   size=116B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void WaitNMI(void)

{
  gh_longlong lVar1;
  gh_uint uVar2;
  int iVar3;
  gh_longlong lVar4;
  
  while( true ) {
    lVar4 = GetTick();
    lVar1 = lVar4 + CONCAT44(((int)diff_prev >> 0x1f) -
                             (frame_time_last_blob._4_4_ + (gh_uint)(diff_prev < (gh_uint)frame_time_last)),
                             diff_prev - (gh_uint)frame_time_last);
    uVar2 = (gh_uint)lVar1;
    iVar3 = (int)((gh_ulonglong)lVar1 >> 0x20);
    if ((int)-(iVar3 + (gh_uint)(16000 < uVar2)) < 0 !=
        (SBORROW4(0,iVar3) != SBORROW4(-iVar3,(gh_uint)(16000 < uVar2)))) break;
    usleep(1000);
  }
  frame_time_last = lVar4;
  diff_prev = uVar2 - 0x411b;
  return;
}
