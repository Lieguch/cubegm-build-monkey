/* ============================================================
 * Load_Proc1   @ 0x002b5a4c   size=364B   callers=12
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_bool Load_Proc1(char *param_1)

{
  int iVar1;
  gh_u4 uVar2;
  
  fpsbuf._4_4_ = *(gh_u4 *)((gh_u1  [16])0x0 + (gh_u1  [16])0x4);
  fpsbuf._8_4_ = *(gh_u4 *)((gh_u1  [16])0x0 + (gh_u1  [16])0x8);
  fpsbuf._12_4_ = *(gh_u4 *)((gh_u1  [16])0x0 + (gh_u1  [16])0xc);
  fpsbuf._0_4_ = 0;
  fps_ptr = 0;
  overtime = 0;
  overtime1 = 0;
  errorcount = 0;
  InitKeyMapping0fEmuType();
  if (*param_1 != '\0') {
    handle = dlopen(param_1,2);
  }
  if (handle != 0) {
    iVar1 = run_process("retro_set_video_refresh",DrawFrame);
    if ((((iVar1 != 0) &&
         (iVar1 = run_process("retro_set_audio_sample_batch",PlayFrame), iVar1 != 0)) &&
        (iVar1 = run_process("retro_set_input_state",joystick_input), iVar1 != 0)) &&
       ((iVar1 = run_process("retro_set_environment",environment), iVar1 != 0 &&
        (iVar1 = run_process("retro_set_input_poll",joystick_poll), iVar1 != 0)))) {
      iVar1 = run_process("retro_init",0);
      return iVar1 != 0;
    }
    return false;
  }
  uVar2 = dlerror();
  RARCH_LOG("open %s fail,%s \n",param_1,uVar2);
  return false;
}
