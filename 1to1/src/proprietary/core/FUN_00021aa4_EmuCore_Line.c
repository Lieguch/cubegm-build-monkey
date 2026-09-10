/* ============================================================
 * EmuCore_Line   @ 0x00021aa4   size=232B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void EmuCore_Line(int param_1,int param_2,int param_3)

{
  int iVar1;
  char acStack_118 [260];
  
  strcpy(acStack_118,core_info_list + (param_1 + param_2) * 0x200);
  if (param_2 != param_3) {
    mui_outputxy_t(DAT_003af29c,OutRect._8_4_,DAT_003af744 * param_2 + OutRect._12_4_,
                   (gh_u1)DAT_003af730,DAT_003af734,acStack_118);
    return;
  }
  iVar1 = mui_outputxy_length_isra_19(OutRect._8_4_,(gh_u1)DAT_003af738,acStack_118);
  EmuCore_Blank(OutRect._8_4_,DAT_003af744 * param_2 + OutRect._12_4_,iVar1 - OutRect._8_4_);
  mui_outputxy_t(DAT_003af29c,OutRect._8_4_,DAT_003af744 * param_2 + OutRect._12_4_,
                 (gh_u1)DAT_003af738,DAT_003af73c,acStack_118);
  return;
}
