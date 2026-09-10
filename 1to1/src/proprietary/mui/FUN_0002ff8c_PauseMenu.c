/* ============================================================
 * PauseMenu   @ 0x0002ff8c   size=1564B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

undefined4 PauseMenu(void)

{
  undefined4 uVar1;
  undefined4 uVar2;
  int iVar3;
  undefined2 *puVar4;
  undefined2 *puVar5;
  undefined2 *puVar6;
  undefined2 *puVar7;
  undefined2 *puVar8;
  undefined2 *__ptr;
  undefined2 *puVar9;
  void *local_70;
  undefined2 *local_58;
  undefined4 local_54;
  undefined4 local_50;
  int local_4c;
  int local_48;
  int local_44;
  undefined2 *local_40;
  int local_3c;
  int local_38;
  int local_34;
  int local_30;
  int local_2c;
  
  ChangeSeting = 0;
  if (use_rgb_8888 == 0) {
    local_70 = (void *)0x0;
  }
  else {
    video_driver_set_colormode();
    iVar3 = this_frame._8_4_ * this_frame._4_4_;
    local_70 = malloc(iVar3 * 2);
    rgb8888_to_rgb565(local_70,this_frame._0_4_,iVar3 * 4);
    this_frame._12_4_ = (uint)this_frame._12_4_ >> 1;
    this_frame._0_4_ = local_70;
  }
  __ptr = (undefined2 *)0x0;
  video_driver_set_rotation(0x1ff);
  usleep(20000);
  video_driver_set_rotation(0xff00);
  do {
    if (bimapFilebuffer == (undefined2 *)0x0) {
      bimapFilebuffer = malloc(DAT_003af828 * DAT_003af828 * 2);
    }
    if (DAT_003af2b8 == (int *)0x0) {
      mui_LoadUIResource(&DAT_003af2b8,"game.raw");
    }
    memcpy(DAT_003af29c,(void *)((int)DAT_003af2b8 + *DAT_003af2b8),
           (uint)*(ushort *)((int)DAT_003af2b8 + 6) * (uint)*(ushort *)(DAT_003af2b8 + 1) * 2);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8);
    if (__ptr == (undefined2 *)0x0) {
      __ptr = malloc(0x96000);
    }
    uVar2 = this_frame._8_4_;
    uVar1 = this_frame._4_4_;
    local_3c = 0;
    local_38 = 0;
    local_34 = DAT_003af828;
    local_30 = DAT_003af82c;
    local_40 = bimapFilebuffer;
    local_2c = DAT_003af828 << 1;
    local_54 = 0;
    local_50 = 0;
    if (rotation == 0) {
      local_4c = this_frame._4_4_;
      local_48 = this_frame._8_4_;
      local_44 = this_frame._12_4_;
      local_58 = (undefined2 *)this_frame._0_4_;
    }
    else if (rotation == 1) {
      local_48 = this_frame._4_4_;
      local_4c = this_frame._8_4_;
      if (this_frame._4_4_ == 0) {
        local_44 = this_frame._8_4_ << 1;
        local_58 = __ptr;
      }
      else {
        local_44 = this_frame._8_4_ * 2;
        puVar5 = (undefined2 *)(this_frame._0_4_ + this_frame._4_4_ * 2 + -2);
        puVar9 = (undefined2 *)(this_frame._0_4_ + -2);
        puVar7 = __ptr;
        do {
          if (uVar2 != 0) {
            puVar4 = puVar7 + uVar2;
            puVar6 = puVar5;
            puVar8 = puVar7;
            do {
              puVar7 = puVar8 + 1;
              *puVar8 = *puVar6;
              puVar6 = puVar6 + uVar1;
              puVar8 = puVar7;
            } while (puVar7 != puVar4);
          }
          puVar5 = puVar5 + -1;
          local_58 = __ptr;
        } while (puVar9 != puVar5);
      }
    }
    else if (rotation == 3) {
      local_48 = this_frame._4_4_;
      local_4c = this_frame._8_4_;
      if (this_frame._4_4_ == 0) {
        local_44 = this_frame._8_4_ << 1;
        local_58 = __ptr;
      }
      else {
        local_44 = this_frame._8_4_ * 2;
        iVar3 = this_frame._4_4_ * (this_frame._8_4_ + 0x7fffffff);
        puVar9 = (undefined2 *)(this_frame._0_4_ + iVar3 * 2);
        puVar5 = (undefined2 *)(this_frame._0_4_ + (this_frame._4_4_ + iVar3) * 2);
        puVar7 = __ptr;
        do {
          if (uVar2 != 0) {
            puVar4 = puVar7 + uVar2;
            puVar6 = puVar9;
            puVar8 = puVar7;
            do {
              puVar7 = puVar8 + 1;
              *puVar8 = *puVar6;
              puVar6 = puVar6 + -uVar1;
              puVar8 = puVar7;
            } while (puVar4 != puVar7);
          }
          puVar9 = puVar9 + 1;
          local_58 = __ptr;
        } while (puVar5 != puVar9);
      }
    }
    else if (rotation == 2) {
      local_4c = this_frame._4_4_;
      local_48 = this_frame._8_4_;
      iVar3 = this_frame._8_4_ * this_frame._4_4_;
      if (iVar3 != 0) {
        puVar5 = (undefined2 *)(this_frame._0_4_ + (iVar3 + 0x7fffffff) * 2 + 2);
        puVar7 = __ptr;
        do {
          puVar5 = puVar5 + -1;
          puVar9 = puVar7 + 1;
          *puVar7 = *puVar5;
          puVar7 = puVar9;
        } while (puVar9 != __ptr + iVar3 + -0x80000000);
      }
      local_44 = uVar1 << 1;
      local_58 = __ptr;
    }
    blockadaptive(&local_40,&local_58);
    local_58 = bimapFilebuffer;
    local_3c = DAT_003af820;
    local_4c = DAT_003af828;
    local_38 = DAT_003af824;
    local_34 = DAT_003af820 + DAT_003af828;
    local_48 = DAT_003af82c;
    local_44 = DAT_003af828 << 1;
    local_30 = DAT_003af824 + DAT_003af82c;
    local_40 = DAT_003af29c;
    local_2c = DAT_003af2a0 << 1;
    local_54 = 0;
    local_50 = 0;
    blockcopy(&local_40,&local_58);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    iVar3 = mui_ReadJoystick();
    while (iVar3 != 0x40) {
      if (iVar3 == 0x2000) {
        if (bimapFilebuffer != (undefined2 *)0x0) {
          free(bimapFilebuffer);
          bimapFilebuffer = (undefined2 *)0x0;
        }
        if (__ptr != (undefined2 *)0x0) {
          free(__ptr);
        }
        if (DAT_003af2b8 != (int *)0x0) {
          free(DAT_003af2b8);
          DAT_003af2b8 = (int *)0x0;
        }
        if (ChangeSeting != 0) {
          SaveKeyMappingConfigFile();
        }
        video_driver_set_rotation(DisplayZoomFlag);
        usleep(20000);
        video_driver_set_rotation(rotation | 0xff00);
        if (use_rgb_8888 != 0) {
          video_driver_set_colormode(1);
        }
        if (local_70 != (void *)0x0) {
          free(local_70);
          return 0;
        }
        return 0;
      }
      if (iVar3 == 0x10) {
        SoundPlay(1,mui_Effect0);
      }
      mui_WaitNMI();
      iVar3 = mui_ReadJoystick();
    }
    iVar3 = mui_game_exit();
    if (iVar3 == 0) {
      if (bimapFilebuffer != (undefined2 *)0x0) {
        free(bimapFilebuffer);
        bimapFilebuffer = (undefined2 *)0x0;
      }
      if (__ptr != (undefined2 *)0x0) {
        free(__ptr);
      }
      if (DAT_003af2b8 != (int *)0x0) {
        free(DAT_003af2b8);
        DAT_003af2b8 = (int *)0x0;
      }
      if (ChangeSeting != 0) {
        SaveKeyMappingConfigFile();
      }
      if (use_rgb_8888 != 0) {
        video_driver_set_colormode(1);
      }
      if (local_70 != (void *)0x0) {
        free(local_70);
      }
      video_driver_set_rotation(0x1ff);
      usleep(20000);
      video_driver_set_rotation(0xff00);
      return pause_ret;
    }
  } while( true );
}
