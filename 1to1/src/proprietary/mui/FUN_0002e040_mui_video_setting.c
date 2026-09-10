/* ============================================================
 * mui_video_setting   @ 0x0002e040   size=2552B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 mui_video_setting(void)

{
  uint uVar1;
  int iVar2;
  undefined4 uVar3;
  undefined4 uVar4;
  undefined4 uVar5;
  uint uVar6;
  undefined4 *puVar7;
  uint uVar8;
  uint uVar9;
  uint uVar10;
  char *pcVar11;
  char *pcVar12;
  undefined4 local_b8;
  undefined4 local_b4;
  undefined4 local_b0;
  int local_ac;
  int local_a8;
  int local_a4;
  void *local_a0;
  int local_9c;
  int local_98;
  int local_94;
  int local_90;
  int local_8c;
  int local_88 [4];
  int local_78;
  int local_74;
  int local_70;
  int local_6c;
  undefined4 local_68 [8];
  undefined1 auStack_48 [36];
  
  puVar7 = local_68;
  pcVar11 = "FULL SCREEN";
  do {
    pcVar12 = pcVar11 + 0x10;
    uVar3 = *(undefined4 *)(pcVar11 + 4);
    uVar4 = *(undefined4 *)(pcVar11 + 8);
    uVar5 = *(undefined4 *)(pcVar11 + 0xc);
    *puVar7 = *(undefined4 *)pcVar11;
    puVar7[1] = uVar3;
    puVar7[2] = uVar4;
    puVar7[3] = uVar5;
    puVar7 = puVar7 + 4;
    pcVar11 = pcVar12;
  } while (pcVar12 != "\x01");
  DAT_003af27c = 0;
  uVar10 = DisplayZoomFlag >> 8;
  while ((DisplayThumbnailflag & 8) != 0) {
    usleep(1000);
  }
  local_88[1] = DAT_003af834;
  local_88[0] = DAT_003af830;
  local_74 = DAT_003af83c + 10 + DAT_003af834;
  local_6c = local_74 + DAT_003af83c;
  local_88[3] = DAT_003af83c + DAT_003af834;
  local_88[2] = DAT_003af830 + DAT_003af838;
  DisplayThumbnailflag = 1;
  local_78 = local_88[0];
  local_70 = local_88[2];
LAB_0002e19c:
  if (DAT_003af2b8 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af2b8,"game.raw");
  }
  memcpy(DAT_003af29c,(void *)((int)DAT_003af2b8 + *DAT_003af2b8),
         (uint)*(ushort *)((int)DAT_003af2b8 + 6) * (uint)*(ushort *)(DAT_003af2b8 + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,5);
  local_a8 = DAT_003af82c;
  local_9c = DAT_003af820;
  local_ac = DAT_003af828;
  local_98 = DAT_003af824;
  local_94 = DAT_003af820 + DAT_003af828;
  local_90 = DAT_003af824 + DAT_003af82c;
  local_a4 = DAT_003af828 << 1;
  local_b8 = bimapFilebuffer;
  local_a0 = DAT_003af29c;
  local_8c = DAT_003af2a0 << 1;
  local_b4 = 0;
  local_b0 = 0;
  blockcopy(&local_a0,&local_b8);
  OutRect._8_4_ = 0;
  OutRect._16_4_ = 0x500;
  OutRect._12_4_ = 0;
  OutRect._20_4_ = 0x2d0;
  mui_outputxy_t(DAT_003af29c,local_88[0] + 8,local_88[1] + 6,(undefined1)DAT_003af840,DAT_003af844,
                 local_68);
  if (uVar10 == 0) {
    mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -10,(undefined1)DAT_003af71c,
                   DAT_003af718,&DAT_003af70f);
    mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(undefined1)DAT_003af840,DAT_003af844,
                   auStack_48);
    mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -6,(undefined1)DAT_003af71c,DAT_003af718
                   ,&DAT_003af708);
  }
  else {
    mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -6,(undefined1)DAT_003af71c,
                   DAT_003af718,&DAT_003af708);
    mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(undefined1)DAT_003af840,DAT_003af844,
                   auStack_48);
    mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -10,(undefined1)DAT_003af71c,
                   DAT_003af718,&DAT_003af70f);
  }
  uVar8 = 0;
  uVar6 = 0xffffffff;
  DAT_003af27c = 0xffffffff;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  do {
    uVar1 = mui_ReadJoystick();
    uVar9 = DAT_003af27c;
    if (uVar1 == 0x40) {
      if (uVar8 == 0) break;
      if ((int)uVar6 < 1) {
        uVar6 = uVar6 + 1;
      }
      SoundPlay(1,mui_Effect0);
      if (uVar6 == DAT_003af27c) goto LAB_0002e5ac;
LAB_0002e400:
      if (-1 < (int)DAT_003af27c) {
        UnDrawSelectBar(local_88 + DAT_003af27c * 4,DAT_003af2b8,0);
        mui_outputxy_t(DAT_003af29c,local_88[DAT_003af27c * 4] + 8,
                       local_88[DAT_003af27c * 4 + 1] + 6,(undefined1)DAT_003af840,DAT_003af844,
                       local_68 + DAT_003af27c * 8);
        if (DAT_003af27c == uVar10) {
          mui_outputxy_t(DAT_003af29c,local_88[uVar10 * 4] + 0x120,local_88[uVar10 * 4 + 1] + -10,
                         (undefined1)DAT_003af71c,DAT_003af718,&DAT_003af70f);
        }
        else {
          mui_outputxy_t(DAT_003af29c,local_88[DAT_003af27c * 4] + 0x120,
                         local_88[DAT_003af27c * 4 + 1] + -6,(undefined1)DAT_003af71c,DAT_003af718,
                         &DAT_003af708);
        }
      }
      uVar9 = uVar6;
      if (-1 < (int)uVar6) {
        DrawSelectBar(local_88 + uVar6 * 4);
        mui_outputxy_t(DAT_003af29c,local_88[uVar6 * 4] + 8,local_88[uVar6 * 4 + 1] + 6,
                       (undefined1)DAT_003af840,DAT_003af844,local_68 + uVar6 * 8);
        if (uVar6 == uVar10) {
          mui_outputxy_t(DAT_003af29c,local_88[uVar6 * 4] + 0x120,local_88[uVar6 * 4 + 1] + -10,
                         (undefined1)DAT_003af71c,DAT_003af718,&DAT_003af70f);
        }
        else {
          mui_outputxy_t(DAT_003af29c,local_88[uVar6 * 4] + 0x120,local_88[uVar6 * 4 + 1] + -6,
                         (undefined1)DAT_003af71c,DAT_003af718,&DAT_003af708);
        }
      }
LAB_0002e534:
      DAT_003af27c = uVar9;
      DAT_003af274 = 1;
LAB_0002e544:
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      DAT_003af274 = 0;
    }
    else {
      if (0x40 < uVar1) {
        if (uVar1 == 0x80) {
          uVar9 = uVar8;
          if (uVar8 == 0) {
            if (DAT_003af830 < (int)(uint)*(ushort *)(DAT_003af2b8 + 0x16)) {
              uVar9 = 1;
              DAT_003af27c = 0xffffffff;
              uVar6 = uVar8;
            }
          }
          else if ((int)(uint)*(ushort *)(DAT_003af2b8 + 0x16) < DAT_003af830) {
            uVar6 = 0xffffffff;
            uVar9 = 0;
          }
          SoundPlay(1,mui_Effect1);
          uVar8 = uVar9;
          if (uVar6 == DAT_003af27c) goto LAB_0002e5ac;
          goto LAB_0002e400;
        }
        if ((uVar1 != 0x2000) || (uVar8 == 0)) goto joined_r0x0002e5a8;
        UnDrawSelectBar(local_88,DAT_003af2b8,0);
        UnDrawSelectBar(local_88 + 4,DAT_003af2b8,0);
        uVar10 = (uint)(uVar9 == 0);
        DrawSelectBar(local_88 + DAT_003af27c * 4);
        mui_outputxy_t(DAT_003af29c,local_88[0] + 8,local_88[1] + 6,(undefined1)DAT_003af840,
                       DAT_003af844,local_68);
        if (uVar9 == 0) {
          mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -6,(undefined1)DAT_003af71c,
                         DAT_003af718,&DAT_003af708);
          mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(undefined1)DAT_003af840,
                         DAT_003af844,auStack_48);
          mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -10,(undefined1)DAT_003af71c,
                         DAT_003af718,&DAT_003af70f);
        }
        else {
          mui_outputxy_t(DAT_003af29c,local_88[0] + 0x120,local_88[1] + -10,(undefined1)DAT_003af71c
                         ,DAT_003af718,&DAT_003af70f);
          mui_outputxy_t(DAT_003af29c,local_78 + 8,local_74 + 6,(undefined1)DAT_003af840,
                         DAT_003af844,auStack_48);
          mui_outputxy_t(DAT_003af29c,local_78 + 0x120,local_74 + -6,(undefined1)DAT_003af71c,
                         DAT_003af718,&DAT_003af708);
        }
        RARCH_LOG("VideoFull:%d\n",uVar10);
        uVar9 = DAT_003af27c;
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
        goto LAB_0002e534;
      }
      if (uVar1 == 0x10) {
        if (uVar8 == 0) {
          if (uVar10 != DisplayZoomFlag >> 8) {
            if (uVar10 == 0) {
              DisplayZoomFlag = DisplayZoomFlag & 0xfeff;
            }
            else {
              DisplayZoomFlag = DisplayZoomFlag | 0x100;
            }
            ChangeSeting = 1;
            return 1;
          }
          return 1;
        }
        if (uVar6 != 0) {
          uVar6 = uVar6 - 1;
        }
        SoundPlay(1,mui_Effect0);
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
      }
      else if (uVar1 == 0x20) {
        if (uVar8 == 0) {
          if ((int)(uint)*(ushort *)(DAT_003af2b8 + 0x16) < DAT_003af830) {
            DAT_003af27c = 0xffffffff;
            uVar6 = uVar8;
            uVar8 = 1;
          }
        }
        else if (DAT_003af830 < (int)(uint)*(ushort *)(DAT_003af2b8 + 0x16)) {
          uVar8 = 0;
          uVar6 = 0xffffffff;
        }
        SoundPlay(1,mui_Effect1);
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
      }
      else {
joined_r0x0002e5a8:
        if (uVar6 != DAT_003af27c) goto LAB_0002e400;
      }
LAB_0002e5ac:
      if (DAT_003af274 != 0) goto LAB_0002e544;
    }
    mui_WaitNMI();
  } while( true );
  iVar2 = mui_joystick_setting();
  if (iVar2 == 0) {
    if (uVar10 != DisplayZoomFlag >> 8) {
      if (uVar10 == 0) {
        DisplayZoomFlag = DisplayZoomFlag & 0xfeff;
      }
      else {
        DisplayZoomFlag = DisplayZoomFlag | 0x100;
      }
      ChangeSeting = 1;
    }
    return 0;
  }
  goto LAB_0002e19c;
}
