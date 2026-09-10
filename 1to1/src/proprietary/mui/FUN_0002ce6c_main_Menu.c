/* ============================================================
 * main_Menu   @ 0x0002ce6c   size=540B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void main_Menu(void)

{
  int iVar1;
  undefined4 uVar2;
  pthread_t apStack_1c [2];
  
  strcpy(root_path,work_path);
  myStrrstr(root_path,&DAT_002dd64c);
  myStrrstr(root_path,&DAT_002dd64c);
  RARCH_LOG("root_path:%s\n",root_path);
  mui_LoadSetting();
  mui_LoadConfig();
  mui_InitFont();
  Soundplayflag = 3;
  iVar1 = pthread_create(apStack_1c,(pthread_attr_t *)0x0,mui_SoundplayThread,(void *)0x0);
  if (iVar1 != 0) {
    RARCH_LOG("can\'t create mui_SoundplayThread process thread \r\n");
  }
  DisplayThumbnailflag = 1;
  iVar1 = pthread_create(apStack_1c,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
  if (iVar1 != 0) {
    RARCH_LOG("can\'t create mui_DisplayThread process thread \r\n");
  }
  usleep(1000);
  DAT_003af284 = 0;
  DAT_003af2ac = 0;
  DAT_003af288 = 0;
  DAT_003af28c = 0;
  DAT_003af290 = 0;
  DAT_003af298 = 0;
  DAT_003af294 = 0;
  SoundPlayer._0_4_ = 0;
  SoundPlayer._36_4_ = 0;
  scr_h_size = 0x500;
  DAT_003af2a0 = 0x500;
  DAT_003af274 = 0;
  scr_v_size = 0x2d0;
  DAT_003af2a4 = 0x2d0;
  OutRect._20_4_ = 0x2d0;
  OutRect._0_4_ = 0x500;
  OutRect._4_4_ = 0;
  OutRect._8_4_ = 0;
  OutRect._12_4_ = 0;
  OutRect._16_4_ = 0x500;
  if (DAT_003af29c == (void *)0x0) {
    DAT_003af29c = malloc(0x1c2000);
  }
  SoundPlay(0,mui_MenuMusic);
  LoadMenuLog();
  DAT_003af26c = m_menulog._0_4_;
  uVar2 = m_menulog._0_4_;
  do {
    switch(uVar2) {
    case 0:
      mui_menu();
      uVar2 = DAT_003af26c;
      break;
    case 1:
      mui_type();
      uVar2 = DAT_003af26c;
      break;
    case 2:
      mui_recent();
      uVar2 = DAT_003af26c;
      break;
    case 3:
      mui_shoucang();
      uVar2 = DAT_003af26c;
      break;
    case 4:
      mui_search();
      uVar2 = DAT_003af26c;
      break;
    case 5:
      mui_setting();
      uVar2 = DAT_003af26c;
    }
  } while( true );
}
