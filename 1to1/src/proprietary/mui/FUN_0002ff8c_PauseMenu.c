/* ============================================================
 * PauseMenu   @ 0x0002ff8c   size=1564B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 PauseMenu(void)

{
  gh_u4 uVar1;
  gh_u4 uVar2;
  int iVar3;
  gh_u2 *puVar4;
  gh_u2 *puVar5;
  gh_u2 *puVar6;
  gh_u2 *puVar7;
  gh_u2 *puVar8;
  gh_u2 *__ptr;
  gh_u2 *puVar9;
  void *local_70;
  /* R179 根修：-0x58..-0x2c 是 blockadaptive/blockcopy 共用的 12 个连续 int 参数槽。
   * Ghidra 拆成 12 独立标量 ⇒ &local_40/&local_58 跨对象块读 = UB ⇒ -Os 消除 af820/24/2c 写入。
   * 数组化让两个块读调用(&blk[6],&blk[0])的地址逃逸覆盖整段，活槽被保留。
   * 物理布局由工厂反汇编 str 序列逐槽锁定（sp+32..sp+76，见 R179 段）：
   *   [0]=local_58 [1]=local_54 [2]=local_50 [3]=local_4c [4]=local_48 [5]=local_44
   *   [6]=local_40 [7]=local_3c [8]=local_38 [9]=local_34 [10]=local_30 [11]=local_2c */
  int blk[12];
  
  ChangeSeting = 0;
  if (use_rgb_8888 == 0) {
    local_70 = (void *)0x0;
  }
  else {
    video_driver_set_colormode();
    iVar3 = this_frame._8_4_ * this_frame._4_4_;
    local_70 = malloc(iVar3 * 2);
    rgb8888_to_rgb565(local_70,this_frame._0_4_,iVar3 * 4);
    this_frame._12_4_ = (gh_uint)this_frame._12_4_ >> 1;
    this_frame._0_4_ = (gh_u4)local_70;
  }
  __ptr = (gh_u2 *)0x0;
  video_driver_set_rotation(0x1ff);
  usleep(20000);
  video_driver_set_rotation(0xff00);
  do {
    if (bimapFilebuffer == (gh_u2 *)0x0) {
      bimapFilebuffer = malloc(DAT_003af828 * DAT_003af828 * 2);
    }
    if (DAT_003af2b8 == (int *)0x0) {
      mui_LoadUIResource(&DAT_003af2b8,"game.raw");
    }
    memcpy(DAT_003af29c,(void *)((int)DAT_003af2b8 + *DAT_003af2b8),
           (gh_uint)*(gh_ushort *)((int)DAT_003af2b8 + 6) * (gh_uint)*(gh_ushort *)(DAT_003af2b8 + 1) * 2);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8);
    if (__ptr == (gh_u2 *)0x0) {
      __ptr = malloc(0x96000);
    }
    uVar2 = this_frame._8_4_;
    uVar1 = this_frame._4_4_;
    blk[7] = 0;                            /* local_3c = param_1[1]（blockadaptive 段）*/
    blk[8] = 0;                            /* local_38 = param_1[2]（blockadaptive 段）*/
    blk[9] = DAT_003af828;                 /* local_34 = param_1[3]（blockadaptive 段）*/
    blk[10] = DAT_003af82c;                /* local_30 = param_1[4]（blockadaptive 段）*/
    blk[6] = (int)bimapFilebuffer;         /* local_40 = param_1[0]（目标基址）*/
    blk[11] = DAT_003af828 << 1;           /* local_2c = param_1[5]（stride）*/
    blk[1] = 0;                            /* local_54 = param_2[1] */
    blk[2] = 0;                            /* local_50 = param_2[2] */
    if (rotation == 0) {
      blk[3] = this_frame._4_4_;
      blk[4] = this_frame._8_4_;
      blk[5] = this_frame._12_4_;
      blk[0] = (int)(gh_u2 *)this_frame._0_4_;
    }
    else if (rotation == 1) {
      blk[4] = this_frame._4_4_;
      blk[3] = this_frame._8_4_;
      if (this_frame._4_4_ == 0) {
        blk[5] = this_frame._8_4_ << 1;
        blk[0] = (int)__ptr;
      }
      else {
        blk[5] = this_frame._8_4_ * 2;
        puVar5 = (gh_u2 *)(this_frame._0_4_ + this_frame._4_4_ * 2 + -2);
        puVar9 = (gh_u2 *)(this_frame._0_4_ + -2);
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
          blk[0] = (int)__ptr;
        } while (puVar9 != puVar5);
      }
    }
    else if (rotation == 3) {
      blk[4] = this_frame._4_4_;
      blk[3] = this_frame._8_4_;
      if (this_frame._4_4_ == 0) {
        blk[5] = this_frame._8_4_ << 1;
        blk[0] = (int)__ptr;
      }
      else {
        blk[5] = this_frame._8_4_ * 2;
        iVar3 = this_frame._4_4_ * (this_frame._8_4_ + 0x7fffffff);
        puVar9 = (gh_u2 *)(this_frame._0_4_ + iVar3 * 2);
        puVar5 = (gh_u2 *)(this_frame._0_4_ + (this_frame._4_4_ + iVar3) * 2);
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
          blk[0] = (int)__ptr;
        } while (puVar5 != puVar9);
      }
    }
    else if (rotation == 2) {
      blk[3] = this_frame._4_4_;
      blk[4] = this_frame._8_4_;
      iVar3 = this_frame._8_4_ * this_frame._4_4_;
      if (iVar3 != 0) {
        puVar5 = (gh_u2 *)(this_frame._0_4_ + (iVar3 + 0x7fffffff) * 2 + 2);
        puVar7 = __ptr;
        do {
          puVar5 = puVar5 + -1;
          puVar9 = puVar7 + 1;
          *puVar7 = *puVar5;
          puVar7 = puVar9;
        } while (puVar9 != __ptr + iVar3 + -0x80000000);
      }
      blk[5] = uVar1 << 1;
      blk[0] = (int)__ptr;
    }
    blockadaptive((int *)&blk[6],(int *)&blk[0]);
    blk[0] = (int)bimapFilebuffer;
    blk[7] = DAT_003af820;
    blk[3] = DAT_003af828;
    blk[8] = DAT_003af824;
    blk[9] = DAT_003af820 + DAT_003af828;
    blk[4] = DAT_003af82c;
    blk[5] = DAT_003af828 << 1;
    blk[10] = DAT_003af824 + DAT_003af82c;
    blk[6] = (int)DAT_003af29c;
    blk[11] = DAT_003af2a0 << 1;
    blk[1] = 0;
    blk[2] = 0;
    blockcopy((int *)&blk[6],(int *)&blk[0]);
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    iVar3 = mui_ReadJoystick();
    while (iVar3 != 0x40) {
      if (iVar3 == 0x2000) {
        if (bimapFilebuffer != (gh_u2 *)0x0) {
          free(bimapFilebuffer);
          bimapFilebuffer = (gh_u2 *)0x0;
        }
        if (__ptr != (gh_u2 *)0x0) {
          free(__ptr);
        }
        if (DAT_003af2b8 != (int *)0x0) {
          free(DAT_003af2b8);
          DAT_003af2b8 = (gh_u4 *)0x0;
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
        SoundPlay(1,(int *)mui_Effect0);
      }
      mui_WaitNMI();
      iVar3 = mui_ReadJoystick();
    }
    iVar3 = mui_game_exit();
    if (iVar3 == 0) {
      if (bimapFilebuffer != (gh_u2 *)0x0) {
        free(bimapFilebuffer);
        bimapFilebuffer = (gh_u2 *)0x0;
      }
      if (__ptr != (gh_u2 *)0x0) {
        free(__ptr);
      }
      if (DAT_003af2b8 != (int *)0x0) {
        free(DAT_003af2b8);
        DAT_003af2b8 = (gh_u4 *)0x0;
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
