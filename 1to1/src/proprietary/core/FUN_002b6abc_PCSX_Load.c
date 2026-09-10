/* ============================================================
 * PCSX_Load   @ 0x002b6abc   size=284B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 PCSX_Load(char *param_1)

{
  int iVar1;
  code *pcVar2;
  char acStack_118 [260];
  
  n_input_width = 0x140;
  n_input_height = 0xe0;
  n_input_visible_width = 0x100;
  n_input_visible_height = 0xe0;
  screen_w = 0x100;
  screen_x = 0;
  sprintf(acStack_118,"%s/cores/libemu_pcsx.so",work_path);
  iVar1 = Load_Proc1(acStack_118);
  if (iVar1 != 0) {
    strcpy(fileName,param_1);
    RARCH_LOG("\nLoading %s ... \r\n",param_1);
    game._0_4_ = fileName;
    game._4_4_ = 0;
    game._8_4_ = 0;
    pcVar2 = (code *)dlsym(handle,"retro_load_game");
    if (pcVar2 == (code *)0x0) {
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
