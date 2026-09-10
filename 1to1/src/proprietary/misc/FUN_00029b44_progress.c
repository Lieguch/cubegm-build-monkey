/* ============================================================
 * progress   @ 0x00029b44   size=368B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void progress(char *param_1,gh_u4 param_2)

{
  gh_u4 uVar1;
  double in_d0;
  char acStack_120 [260];
  
  progress_stepcount = in_d0 + progress_stepcount;
  uVar1 = (gh_u4)((gh_ulonglong)progress_stepcount >> 0x20);
  if (*param_1 == '\0') {
    RARCH_LOG("    %2.2f%%\n",param_2,SUB84(progress_stepcount,0),uVar1);
    sprintf(acStack_120,"    %2.2f%%",progress_stepcount._0_4_,progress_stepcount._4_4_);
  }
  else if (in_d0 == 0.0) {
    RARCH_LOG("00 Loading %s\n",param_1);
    sprintf(acStack_120,"Loading %s        ",param_1);
  }
  else {
    RARCH_LOG("01 %s: %2.2f%%\n",param_1,SUB84(progress_stepcount,0),uVar1);
    sprintf(acStack_120,"Loading: %2.2f%%",progress_stepcount._0_4_,progress_stepcount._4_4_);
  }
  OutRect._16_4_ = 0x500;
  OutRect._20_4_ = 0x2d0;
  OutRect._8_4_ = 0;
  OutRect._12_4_ = 0;
  memset((void *)(scr_h_size * (scr_v_size + -0x30) + DAT_003af29c),0,scr_h_size * 0xc0);
  mui_outputxy_t(DAT_003af29c,scr_h_size / 3,scr_v_size / 2,0x28,0xffff,acStack_120);
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  return;
}
