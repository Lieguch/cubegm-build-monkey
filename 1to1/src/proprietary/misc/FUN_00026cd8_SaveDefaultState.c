/* ============================================================
 * SaveDefaultState   @ 0x00026cd8   size=108B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void SaveDefaultState(void)

{
  gh_u4 uVar1;
  gh_u4 uVar2;
  char acStack_1008 [4096];
  
  uVar1 = (gh_u4)GetWorkPath();
  uVar2 = gameType();
  sprintf(acStack_1008,"%ssaves/%03d/%s.sav",uVar1,uVar2,RomName);
  RARCH_LOG("SaveDefaultState:%s\n",acStack_1008);
  retro_save_state(acStack_1008);
  return;
}
