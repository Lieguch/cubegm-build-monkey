/* ============================================================
 * Load_Proc2   @ 0x002b5c08   size=1256B   callers=12
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void Load_Proc2(void)

{
  gh_uint uVar1;
  bool bVar2;
  gh_u4 uVar3;
  gh_code *pcVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  gh_uint uVar8;
  int local_50;
  
  _retro_get_region = (gh_code *)dlsym(handle,"retro_get_region");
  if (_retro_get_region == (gh_code *)0x0) {
    RARCH_LOG("find retro_get_region process fail \n");
    return;
  }
  pal_ntsc = (*_retro_get_region)();
  RARCH_LOG("pal_ntsc:%d\n",pal_ntsc);
  uVar3 = handle;
  _retro_run = (gh_code *)dlsym(handle,"retro_run");
  _SetFrameSkip = (gh_code *)dlsym(uVar3,"SetFrameSkip");
  if (_SetFrameSkip != (gh_code *)0x0) {
    RARCH_LOG("find _SetFrameSkip process\n");
  }
  if (pal_ntsc == 0) {
    sound_len = 0xb7c;
  }
  else {
    sound_len = 0xdc8;
  }
  RetroInitSound();
  bVar2 = true;
  gettimeofday((timeval *)&outTimeVal,(__timezone_ptr_t)0x0);
  inTimeVal._0_4_ = (int)outTimeVal;
  inTimeVal._4_4_ = outTimeVal._4_4_;
  diff_prev = 0;
  local_50 = 0;
  initialTicks = (int)outTimeVal * 1000 + outTimeVal._4_4_ / 1000;
  if (pal_ntsc == 0) {
    fps = 0x3c;
  }
  else {
    fps = 0x32;
  }
  maxSkips = 2;
  FrameCount0 = 0;
  skipCounter = 0;
  FrameCount = 0;
  do {
    if (joy_key._0_4_ == GameMenuHotKey) {
      iVar6 = PauseMenu();
      if (iVar6 != 0) {
LAB_002b60a4:
        run_process("retro_unload_game",0);
        run_process("retro_deinit",0);
        dlclose(handle);
        return;
      }
      gettimeofday((timeval *)&outTimeVal,(__timezone_ptr_t)0x0);
      inTimeVal._0_4_ = (int)outTimeVal;
      inTimeVal._4_4_ = outTimeVal._4_4_;
      diff_prev = 0;
      FrameCount0 = 0;
      skipCounter = 0;
      FrameCount = 0;
      initialTicks = (int)outTimeVal * 1000 + outTimeVal._4_4_ / 1000;
      maxSkips = 2;
      if (pal_ntsc == 0) {
        fps = 0x3c;
      }
      else {
        fps = 0x32;
      }
    }
    else if ((int)joy_key._0_4_ < 0) goto LAB_002b60a4;
    if (SaveDefaultStateKey == joy_key._0_4_) {
      if (local_50 == 0) {
        SaveDefaultState();
        local_50 = 0xf;
      }
    }
    else if (local_50 != 0) {
      local_50 = local_50 + -1;
    }
    gettimeofday((timeval *)&outTimeVal,(__timezone_ptr_t)0x0);
    iVar6 = initialTicks;
    iVar7 = (int)outTimeVal * 1000 + outTimeVal._4_4_ / 1000;
    FrameCount0 = FrameCount0 + 1;
    uVar1 = (gh_uint)(fps * (iVar7 - initialTicks)) / 1000;
    if (uVar1 < FrameCount0) {
      iVar5 = __aeabi_uidiv(FrameCount0 * 1000 + -1000,fps);
      iVar6 = (iVar5 - iVar7) + iVar6;
      if (0 < iVar6) {
        usleep(iVar6 * 1000);
      }
LAB_002b5f64:
      FrameSkip = (gh_uint)(0 < skipCounter);
      uVar8 = (gh_uint)(0 >= skipCounter);
    }
    else {
      if ((uVar1 != FrameCount0) && (skipCounter < maxSkips)) {
        skipCounter = skipCounter + 1;
        goto LAB_002b5f64;
      }
      uVar8 = 1;
      FrameSkip = 0;
      skipCounter = 0;
      FrameCount0 = uVar1;
    }
    pcVar4 = _SetFrameSkip;
    iVar6 = fps_ptr + 1;
    *(gh_uint *)(fpsbuf + fps_ptr * 4) = uVar8;
    if (iVar6 == 0x10) {
      iVar6 = 0;
    }
    fps_ptr = iVar6;
    if (pcVar4 != (gh_code *)0x0) {
      (*pcVar4)();
    }
    ReadJoystickProc();
    TurboKeyProcess();
    (*_retro_run)();
    if (bVar2) {
      LoadDefaultState();
      gettimeofday((timeval *)&outTimeVal,(__timezone_ptr_t)0x0);
      inTimeVal._0_4_ = (int)outTimeVal;
      inTimeVal._4_4_ = outTimeVal._4_4_;
      diff_prev = 0;
      FrameCount0 = 0;
      skipCounter = 0;
      FrameCount = 0;
      initialTicks = (int)outTimeVal * 1000 + outTimeVal._4_4_ / 1000;
      maxSkips = 2;
      if (pal_ntsc == 0) {
        fps = 0x3c;
      }
      else {
        fps = 0x32;
      }
    }
    bVar2 = false;
  } while( true );
}
