/* ============================================================
 * popwindows   @ 0x00027398   size=536B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void popwindows(gh_u4 *param_1)

{
  void *__dest;
  int iVar1;
  int iVar2;
  int iVar3;
  int iVar4;
  void *__src;
  int iVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  int iVar9;
  gh_u4 local_58;
  gh_u4 local_54;
  gh_u4 local_50;
  int local_4c;
  int local_48;
  int local_44;
  int local_40;
  int local_3c;
  int local_38;
  int local_34;
  int local_30;
  int local_2c;
  
  iVar4 = param_1[2];
  iVar2 = param_1[1];
  iVar7 = param_1[4] - iVar4;
  iVar6 = param_1[3] - iVar2;
  __dest = malloc(iVar6 * iVar7 * 2);
  local_40 = (int)DAT_003af29c;
  scrbuf = __dest;
  if (iVar7 < 1) {
    iVar9 = DAT_003af2a0 << 1;
  }
  else {
    iVar5 = 0;
    iVar9 = DAT_003af2a0 * 2;
    __src = (void *)(DAT_003af29c + (DAT_003af2a0 * iVar4 + iVar2) * 2);
    do {
      iVar5 = iVar5 + 1;
      memcpy(__dest,__src,iVar6 * 2);
      __src = (void *)((int)__src + iVar9);
      __dest = (void *)((int)__dest + iVar6 * 2);
    } while (iVar7 != iVar5);
  }
  local_44 = iVar6 * 2;
  local_58 = *param_1;
  iVar5 = 1;
  local_54 = 0;
  local_50 = 0;
  local_4c = iVar6;
  local_48 = iVar7;
  while( true ) {
    iVar3 = 5 - iVar5;
    iVar1 = iVar6 * iVar5;
    iVar8 = iVar7 * iVar5;
    iVar5 = iVar5 + 1;
    local_3c = (iVar3 * iVar6) / 10 + iVar2;
    local_38 = (iVar3 * iVar7) / 10 + iVar4;
    local_34 = iVar1 / 5 + local_3c;
    local_30 = iVar8 / 5 + local_38;
    local_2c = iVar9;
    blockadaptive((int *)&local_40,(int *)&local_58);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    usleep(18000);
    if (iVar5 == 6) break;
    iVar2 = param_1[1];
    iVar4 = param_1[2];
    iVar9 = DAT_003af2a0 << 1;
    iVar6 = param_1[3] - iVar2;
    iVar7 = param_1[4] - iVar4;
    local_40 = (int)DAT_003af29c;
  }
  return;
}
