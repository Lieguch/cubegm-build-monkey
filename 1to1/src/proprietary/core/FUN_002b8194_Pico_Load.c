/* ============================================================
 * Pico_Load   @ 0x002b8194   size=516B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 Pico_Load(char *param_1,int param_2)

{
  int iVar1;
  gh_code *pcVar2;
  long lVar3;
  void *__ptr;
  gh_uint __n;
  char acStack_120 [260];
  
  n_input_width = 0x140;
  n_input_height = 0xe0;
  n_input_visible_width = 0x100;
  n_input_visible_height = 0xe0;
  screen_w = 0x100;
  screen_x = 0;
  sprintf(acStack_120,"%s/cores/libemu_md.so",work_path);
  iVar1 = Load_Proc1(acStack_120);
  if (iVar1 != 0) {
    strcpy(fileName,param_1);
    __n = ZIP_BUF_SIZE;
    __ptr = ZIP_BUF;
    if (param_2 < 0x10000) {
      RARCH_LOG("Loading %s ... \r\n",param_1);
      romfile = fopen(param_1,"rb");
      if (romfile == (FILE *)0x0) {
        RARCH_LOG("%s open fail\r\n",param_1);
        return 0xffffffff;
      }
      fseek(romfile,0,2);
      lVar3 = ftell(romfile);
      __n = lVar3 + 3U & 0xfffffffc;
      fseek(romfile,0,0);
      __ptr = malloc(__n + 4);
      if (__ptr == (void *)0x0) {
        fclose(romfile);
        return 1;
      }
      fread(__ptr,1,__n,romfile);
      fclose(romfile);
    }
    game_blob._0_4_ = fileName;
    game_blob._4_4_ = __ptr;
    game_blob._8_4_ = __n;
    pcVar2 = (gh_code *)dlsym(handle_emurun,"retro_load_game");
    if (pcVar2 == (gh_code *)0x0) {
      RARCH_LOG("find retro_load_game process fail \n");
      return 0;
    }
    iVar1 = (*pcVar2)(game);
    if (iVar1 != 0) {
      Load_Proc2();
    }
    if (__ptr != (void *)0x0) {
      free(__ptr);
    }
  }
  return 0;
}
