/* ============================================================
 * main   @ 0x00009b58   size=440B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 main(void)

{
  char *pcVar1;
  int iVar2;
  pthread_t pStack_51c;
  char acStack_518 [256];
  gh_u1 auStack_418 [1024];
  
  puts("rkgame v1.42");
  get_executable_path(work_path,auStack_418,0x1000);
  printf("directory:%s\nappname:%s\n",work_path,auStack_418);
  pcVar1 = stpcpy(resource_path,work_path);
  builtin_strncpy(pcVar1,"resource",9);
  autorunfile[0] = '\0';
  autorundriver[0] = 0;
  GetConfig();
  dispmeninfo();
  InitDisplay();
  InitSound();
  InitJoystick();
  sfc_init();
  iVar2 = spi_driver_init();
  if (iVar2 == 0) {
    sfc_uninit();
  }
  else {
    pcVar1 = stpcpy(acStack_518,work_path);
    builtin_strncpy(pcVar1,"update/firmware.upk",0x14);
    UpdateROM(acStack_518);
    sfc_uninit();
    ShareMemCreat();
    iVar2 = pthread_create(&pStack_51c,(pthread_attr_t *)0x0,(void *(*)(void *))XintiaoThread,(void *)0x0);
    if (iVar2 != 0) {
      puts("can\'t create XintiaoThread process thread \r");
    }
    if (autorunfile[0] == '\0') {
      main_Menu();
    }
    else {
      iVar2 = strcmp(autorunfile,"/USBJoystickTest");
      if (iVar2 == 0) {
        TestUSBJoy();
      }
      else {
        iVar2 = strcmp(autorunfile,"/JoystickTest");
        if (iVar2 == 0) {
          JoystickTest();
        }
        else {
          autorun(autorunfile,autorundriver);
        }
      }
    }
  }
  DeinitSound();
  DeinitDisplay();
  return 0;
}
