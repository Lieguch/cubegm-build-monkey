/* ============================================================
 * FBA_Load   @ 0x002b6c14   size=704B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 FBA_Load(char *param_1)

{
  int iVar1;
  gh_u4 uVar2;
  gh_code *pcVar3;
  char **ppcVar4;
  char *local_150;
  char *local_14c [4];
  gh_u4 uStack_13c;
  gh_u4 uStack_138;
  gh_u4 uStack_134;
  gh_u4 uStack_130;
  gh_u4 uStack_12c;
  char acStack_128 [260];
  
  local_150 = DAT_003b012c;
  local_14c[0] = (char *)DAT_003b0130;
  local_14c[1] = (char *)DAT_003b0134;
  local_14c[2] = (char *)DAT_003b0138;
  ppcVar4 = &local_150;
  local_14c[3] = (char *)DAT_003b013c;
  uStack_13c = DAT_003b0140;
  uStack_138 = DAT_003b0144;
  uStack_134 = DAT_003b0148;
  uStack_130 = DAT_003b014c;
  uStack_12c = DAT_003b0150;
  n_input_width = 0x140;
  n_input_height = 0xf0;
  n_input_visible_width = 0x140;
  n_input_visible_height = 0xf0;
  screen_w = 0x140;
  screen_x = 0;
  strcpy(fileName,param_1);
  if (*local_150 != '\0') {
    do {
      while( true ) {
        sprintf(acStack_128,"%s/cores/%s",work_path);
        handle = dlopen(acStack_128,2);
        if (handle != 0) break;
        uVar2 = dlerror();
        RARCH_LOG("open %s fail,%s \n",acStack_128,uVar2);
        ppcVar4 = ppcVar4 + 1;
        if (**ppcVar4 == '\0') {
          return 0;
        }
      }
      _retro_is_support = (gh_code *)dlsym(handle,"retro_is_support");
      if (((_retro_is_support != (gh_code *)0x0) && (iVar1 = (*_retro_is_support)(param_1), -1 < iVar1)
          ) && (iVar1 = Load_Proc1(&DAT_002dbcb4), iVar1 != 0)) {
        run_process("retro_set_progress_callback",progress);
        game._0_4_ = fileName;
        game._4_4_ = 0;
        game._8_4_ = 0;
        progress_stepcount = 0;
        pcVar3 = (gh_code *)dlsym(handle,"retro_load_game");
        if ((pcVar3 != (gh_code *)0x0) && (iVar1 = (*pcVar3)(game), iVar1 != 0)) {
          RARCH_LOG("use %s to run %s\n",acStack_128,fileName);
          Load_Proc2();
          rotation = 0;
          if (soft_rotation == 0) {
            video_driver_set_rotation(0xff00);
          }
          else if (rotation_buff != (void *)0x0) {
            free(rotation_buff);
            rotation_buff = (void *)0x0;
          }
          video_driver_set_rotation(0xff00);
          RARCH_LOG("Exit fba here \n");
          return 0;
        }
        run_process("retro_unload_game",0);
        run_process("retro_deinit",0);
      }
      RARCH_LOG("%s unsupport.\n",acStack_128);
      dlclose(handle);
      ppcVar4 = ppcVar4 + 1;
    } while (**ppcVar4 != '\0');
  }
  return 0;
}
