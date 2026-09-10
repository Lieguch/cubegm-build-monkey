/* ============================================================
 * InitDisplay   @ 0x0000d678   size=524B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* WARNING: Type propagation algorithm not settling */

undefined4 InitDisplay(void)

{
  int iVar1;
  undefined4 uVar2;
  int iVar3;
  pthread_t apStack_428 [4];
  char acStack_418 [1028];
  
  sprintf(acStack_418,"%s/driver.so",work_path);
  handle = dlopen(acStack_418,2);
  if (handle == 0) {
    uVar2 = dlerror();
    printf("open driver.so fail, %s.\n",uVar2);
    return 0;
  }
  puts("open driver.so sucess");
  video_driver_setting = (code *)dlsym(handle,"video_driver_setting");
  if (video_driver_setting == (code *)0x0) {
    puts("can\'t find video_driver_setting proc");
  }
  else {
    apStack_428[2] = 1;
    apStack_428[1] = 0;
    apStack_428[3] = 1;
    (*video_driver_setting)(apStack_428 + 1);
    iVar1 = run_process_constprop_0("video_drivers_init");
    iVar3 = handle;
    if (iVar1 != 0) {
      video_driver_frame = dlsym(handle,"video_driver_disp_frame");
      if (video_driver_frame == 0) {
        puts("can\'t find video_driver_disp_frame proc");
      }
      else {
        set_rotation = dlsym(iVar3,"video_driver_setmode");
        if (set_rotation == 0) {
          puts("can\'t find video_driver_setmode proc");
        }
        else {
          video_driver_get_size = dlsym(iVar3,"video_driver_get_size");
          if (video_driver_get_size != 0) {
            if (DisplayThread != 0) {
              DisplayThreadflag = 1;
              iVar3 = pthread_create(apStack_428,(pthread_attr_t *)0x0,ScaleDisplayThread,
                                     (void *)0x0);
              if (iVar3 != 0) {
                puts("can\'t create DoubleFrame Display thread \r");
              }
            }
            USE_HDMI_OUT = 1;
            return 1;
          }
          puts("can\'t find video_driver_get_size proc");
        }
      }
    }
  }
  return 0;
}
