/* ============================================================
 * DisplayLine_list   @ 0x00021774   size=248B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void DisplayLine_list(gh_u4 param_1,int param_2,int param_3)

{
  int iVar1;
  char acStack_110 [256];
  
  if ((&DAT_003b2320)[param_2 * 0x101] == 4) {
    sprintf(acStack_110,"[%s]",&file_info_list + param_2 * 0x404);
  }
  else {
    strcpy(acStack_110,&file_info_list + param_2 * 0x404);
  }
  if (param_2 != param_3) {
    mui_outputxy_t(DAT_003af29c,DAT_003af720,DAT_003af744 * param_2 + DAT_003af724,
                   (gh_u1)DAT_003af730,DAT_003af734,acStack_110);
    return;
  }
  iVar1 = mui_outputxy_length_isra_19(DAT_003af720,(gh_u1)DAT_003af738,acStack_110);
  outputblankxy(DAT_003af720,DAT_003af744 * param_2 + DAT_003af724,iVar1 - DAT_003af720);
  mui_outputxy_t(DAT_003af29c,DAT_003af720,DAT_003af744 * param_2 + DAT_003af724,
                 (gh_u1)DAT_003af738,DAT_003af73c,acStack_110);
  return;
}
