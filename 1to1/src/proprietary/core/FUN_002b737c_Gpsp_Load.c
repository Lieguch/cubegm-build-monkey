/* ============================================================
 * Gpsp_Load   @ 0x002b737c   size=332B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 Gpsp_Load(char *param_1,int param_2)

{
  int iVar1;
  gh_code *pcVar2;
  char acStack_118 [260];
  
  n_input_width = 0xf0;
  n_input_height = 0xa0;
  n_input_visible_width = 0xf0;
  n_input_visible_height = 0xa0;
  screen_w = 0xf0;
  screen_x = 0;
  RARCH_LOG("Gpsp_Load\n");
  sprintf(acStack_118,"%s/cores/libemu_gpsp.so",work_path);
  iVar1 = Load_Proc1(acStack_118);
  if (iVar1 != 0) {
    strcpy(fileName,param_1);
    if (param_2 < 0x10000) {
      run_process("retro_set_unzip",(gh_code *)0xffffffff);
    }
    else {
      run_process("retro_set_unzip",(gh_code *)gpsp_unzip);
    }
    game_blob._0_4_ = fileName;
    game_blob._4_4_ = 0;
    game_blob._8_4_ = 0;
    pcVar2 = (gh_code *)dlsym(handle_emurun,"retro_load_game");
    if (pcVar2 == (gh_code *)0x0) {
      RARCH_LOG("find retro_load_game process fail \n");
    }
    else {
      iVar1 = (*pcVar2)(game);
      if (iVar1 != 0) {
        Load_Proc2();
      }
    }
  }
  return 0;
}
