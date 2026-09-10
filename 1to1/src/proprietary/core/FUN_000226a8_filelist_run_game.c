/* ============================================================
 * filelist_run_game   @ 0x000226a8   size=756B   callers=6
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 filelist_run_game(char *param_1)

{
  FILE *__stream;
  undefined4 uVar1;
  int iVar2;
  pthread_t pStack_124;
  char acStack_120 [260];
  
  RARCH_LOG("filelist_run_game:%s\n",param_1);
  mui_extract_basename(RomName,param_1,0x100);
  strcpy(acStack_120,param_1);
  __stream = fopen(acStack_120,"rb");
  if (__stream == (FILE *)0x0) {
    RARCH_LOG("find %s miss\n",param_1);
    return 0;
  }
  fclose(__stream);
  Soundplayflag = Soundplayflag & 0xfe;
  while (Soundplayflag != 0) {
    usleep(1000);
  }
  SoundClose(0);
  DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
  SoundPlayer._0_4_ = 0;
  SoundPlayer._36_4_ = 0;
  while (DisplayThumbnailflag != 0) {
    usleep(1000);
  }
  memset(DAT_003af29c,0,DAT_003af2a4 * DAT_003af2a0 * 2);
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  if (DAT_003af28c != (void *)0x0) {
    free(DAT_003af28c);
    DAT_003af28c = (void *)0x0;
  }
  if (DAT_003af290 != (void *)0x0) {
    free(DAT_003af290);
    DAT_003af290 = (void *)0x0;
  }
  if (DAT_003af294 != (void *)0x0) {
    free(DAT_003af294);
    DAT_003af294 = (void *)0x0;
  }
  if (DAT_003af298 != (void *)0x0) {
    free(DAT_003af298);
    DAT_003af298 = (void *)0x0;
  }
  if (DAT_003af2a8 != (void *)0x0) {
    free(DAT_003af2a8);
    DAT_003af2a8 = (void *)0x0;
  }
  if (DAT_003af2ac != (void *)0x0) {
    free(DAT_003af2ac);
    DAT_003af2ac = (void *)0x0;
  }
  if (DAT_003af2b0 != (void *)0x0) {
    free(DAT_003af2b0);
    DAT_003af2b0 = (void *)0x0;
  }
  file_info_list_ext[0x80] = 0;
  if (param_1[0x304] == '\0') {
    uVar1 = run_game(acStack_120);
  }
  else {
    uVar1 = Core_Load(acStack_120,param_1 + 0x304);
  }
  Soundplayflag = 3;
  iVar2 = pthread_create(&pStack_124,(pthread_attr_t *)0x0,mui_SoundplayThread,(void *)0x0);
  if (iVar2 != 0) {
    RARCH_LOG("can\'t create mui_SoundplayThread process thread \r\n");
  }
  DisplayThumbnailflag = 1;
  iVar2 = pthread_create(&pStack_124,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
  if (iVar2 != 0) {
    RARCH_LOG("can\'t create mui_DisplayThread process thread \r\n");
  }
  usleep(1000);
  SoundPlay(0,mui_MenuMusic);
  return uVar1;
}
