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
  char *uVar2;
  
  /* 证据：2b5a50 vmov.i32 q8,#0 + 2b5a7c vst1.8 {d16-d17},[lr]（lr=*(0x3B1EA0)=&fpsbuf）
     → 一次 16 字节零写，即 fpsbuf._0_4_.._12_4_ 四字清零；原 3 行系 Ghidra 对 NEON 存储的误还原 */
  (fpsbuf_blob)._4_4_ = 0;
  (fpsbuf_blob)._8_4_ = 0;
  (fpsbuf_blob)._12_4_ = 0;
  (fpsbuf_blob)._0_4_ = 0;
  fps_ptr = 0;
  overtime = 0;
  overtime1 = 0;
  errorcount = 0;
  InitKeyMapping0fEmuType();
  if (*param_1 != '\0') {
    handle_emurun = dlopen(param_1,2);
  }
  if (handle_emurun != 0) {
    iVar1 = run_process("retro_set_video_refresh",(gh_code *)DrawFrame);
    if ((((iVar1 != 0) &&
         (iVar1 = run_process("retro_set_audio_sample_batch",(gh_code *)PlayFrame), iVar1 != 0)) &&
        (iVar1 = run_process("retro_set_input_state",(gh_code *)joystick_input), iVar1 != 0)) &&
       ((iVar1 = run_process("retro_set_environment",(gh_code *)environment), iVar1 != 0 &&
        (iVar1 = run_process("retro_set_input_poll",(gh_code *)joystick_poll), iVar1 != 0)))) {
      iVar1 = run_process("retro_init",0);
      return iVar1 != 0;
    }
    return false;
  }
  uVar2 = dlerror();
  RARCH_LOG("open %s fail,%s \n",param_1,uVar2);
  return false;
}
