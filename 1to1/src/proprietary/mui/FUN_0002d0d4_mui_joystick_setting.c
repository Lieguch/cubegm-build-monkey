/* ============================================================
 * mui_joystick_setting   @ 0x0002d0d4   size=3684B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 mui_joystick_setting(void)

{
  uint uVar1;
  char *pcVar2;
  uint uVar3;
  int iVar4;
  uint uVar5;
  int iVar6;
  undefined1 *puVar7;
  uint *puVar8;
  undefined *puVar9;
  int iVar10;
  uint local_194;
  uint local_190;
  undefined4 local_158;
  undefined4 local_154;
  undefined4 local_150;
  int local_14c;
  int local_148;
  int local_144;
  void *local_140;
  int local_13c;
  int local_138;
  int local_134;
  int local_130;
  int local_12c;
  char local_128 [260];
  
  DAT_003af27c = 0;
  local_194 = 0;
  iVar10 = 0;
  puVar9 = &DAT_002dd88c;
  local_190 = 0;
LAB_0002d16c:
  if (DAT_003af2b8 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af2b8,"game.raw");
  }
  memcpy(DAT_003af29c,(void *)((int)DAT_003af2b8 + *DAT_003af2b8),
         (uint)*(ushort *)((int)DAT_003af2b8 + 6) * (uint)*(ushort *)(DAT_003af2b8 + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,6);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,8);
  local_14c = DAT_003af828;
  local_13c = DAT_003af820;
  local_138 = DAT_003af824;
  local_134 = DAT_003af820 + DAT_003af828;
  local_144 = DAT_003af828 << 1;
  local_148 = DAT_003af82c;
  local_130 = DAT_003af824 + DAT_003af82c;
  local_140 = DAT_003af29c;
  local_12c = DAT_003af2a0 << 1;
  local_158 = bimapFilebuffer;
  puVar8 = (uint *)(InputDeviceInfo + 0x6c);
  local_154 = 0;
  local_150 = 0;
  blockcopy(&local_140,&local_158);
  OutRect._8_4_ = 0;
  OutRect._12_4_ = 0;
  iVar6 = 1;
  OutRect._16_4_ = 0x500;
  OutRect._20_4_ = 0x2d0;
  mui_outputxy_t(DAT_003af29c,m_joysticktab._100_4_ + 0xf,m_joysticktab._104_4_,0x2a,0xffff,puVar9);
  puVar7 = m_joysticktab;
  do {
    while( true ) {
      puVar8 = puVar8 + 1;
      uVar3 = *puVar8;
      if ((uVar3 & 0xffff0000) != 0) break;
      iVar6 = iVar6 + 1;
      strcpy(local_128,*(char **)(KayName + uVar3 * 4));
      mui_outputxy_t(DAT_003af29c,*(int *)(puVar7 + 0xe8) + 0x14,*(int *)(puVar7 + 0xec) + 4,0x20,
                     0xffff,local_128);
      puVar7 = puVar7 + 0x84;
      if (iVar6 == 7) goto LAB_0002d38c;
    }
    local_128[0] = 'T';
    local_128[1] = '\0';
    iVar6 = iVar6 + 1;
    strcpy(local_128 + 1,*(char **)(KayName + (uVar3 & 0xffff) * 4));
    mui_outputxy_t(DAT_003af29c,*(int *)(puVar7 + 0xe8) + 0x14,*(int *)(puVar7 + 0xec) + 4,0x20,
                   0xffff,local_128);
    puVar7 = puVar7 + 0x84;
  } while (iVar6 != 7);
LAB_0002d38c:
  uVar3 = 0xffffffff;
  DAT_003af27c = 0xffffffff;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  do {
    uVar1 = ReadJoystick();
    uVar5 = DAT_003af27c;
    uVar1 = uVar1 & 0xefffffff;
    if (uVar1 == 0x400) {
      if ((local_190 != 0) && (0 < (int)uVar3)) {
        iVar6 = 0x1000a;
        if (Joy1_Delay < 0x1e) {
          iVar6 = 10;
        }
        goto LAB_0002d57c;
      }
      goto LAB_0002d454;
    }
    if (uVar1 < 0x401) {
      if (uVar1 == 0x40) {
        if (local_190 == 0) {
          SoundPlay(1,mui_Effect0);
          goto LAB_0002d454;
        }
        if (uVar3 != 0) {
          uVar3 = *(uint *)(m_joysticktab + uVar3 * 0x84 + 0x78);
          SoundPlay(1,mui_Effect0);
          goto LAB_0002d454;
        }
        if (iVar10 < 3) {
          iVar10 = iVar10 + 1;
          SoundPlay(1,mui_Effect0);
          iVar6 = iVar10 * 6;
          puVar9 = *(undefined **)(p_name + iVar10 * 4);
        }
        else {
          SoundPlay(1,mui_Effect0);
          iVar6 = iVar10 * 6;
          puVar9 = *(undefined **)(p_name + iVar10 * 4);
        }
LAB_0002dbb4:
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af2b8,8);
        if ((local_194 & 0x10) == 0) {
          DrawSelectBar(0x3afc44);
        }
        iVar4 = 1;
        mui_outputxy_t(DAT_003af29c,m_joysticktab._100_4_ + 0xf,m_joysticktab._104_4_,0x2a,0x871c,
                       puVar9);
        puVar8 = (uint *)(InputDeviceInfo + iVar6 * 4 + 0x6c);
        puVar7 = m_joysticktab;
        do {
          puVar8 = puVar8 + 1;
          uVar3 = *puVar8;
          if ((uVar3 & 0xffff0000) == 0) {
            strcpy(local_128,*(char **)(KayName + uVar3 * 4));
            mui_outputxy_t(DAT_003af29c,*(int *)(puVar7 + 0xe8) + 0x14,*(int *)(puVar7 + 0xec) + 4,
                           0x20,0xffff,local_128);
          }
          else {
            local_128[0] = 'T';
            local_128[1] = '\0';
            strcpy(local_128 + 1,*(char **)(KayName + (uVar3 & 0xffff) * 4));
            mui_outputxy_t(DAT_003af29c,*(int *)(puVar7 + 0xe8) + 0x14,*(int *)(puVar7 + 0xec) + 4,
                           0x20,0xffff,local_128);
          }
          iVar4 = iVar4 + 1;
          puVar7 = puVar7 + 0x84;
        } while (iVar4 != 7);
        if (DAT_003af27c == 0) {
          uVar5 = 0;
          uVar3 = local_194 + 1;
          if ((local_194 + 1 & 0xf) == 0) {
LAB_0002da14:
            local_194 = local_194 + 1;
            if ((local_194 & 0x10) == 0) {
              DrawSelectBar(0x3afc44);
            }
            else {
              UnDrawSelectBar(0x3afc44,DAT_003af2b8,8);
            }
            mui_outputxy_t(DAT_003af29c,m_joysticktab._100_4_ + 0xf,m_joysticktab._104_4_,0x2a,
                           0x871c,*(undefined4 *)(p_name + iVar10 * 4));
            uVar3 = local_194;
          }
          goto LAB_0002d4e0;
        }
        if (0 < (int)DAT_003af27c) {
          uVar3 = 0;
          goto LAB_0002d6ac;
        }
LAB_0002d9bc:
        DAT_003af27c = 0;
        DrawSelectBar(0x3afc44);
        mui_outputxy_t(DAT_003af29c,m_joysticktab._100_4_ + 0xf,m_joysticktab._104_4_,0x2a,0x871c,
                       *(undefined4 *)(p_name + iVar10 * 4));
        uVar5 = 0;
LAB_0002d4cc:
        local_194 = 2;
        uVar3 = local_194;
        DAT_003af27c = uVar5;
        goto LAB_0002d4e0;
      }
      if (uVar1 < 0x41) {
        if (uVar1 == 0x10) {
          if (local_190 == 0) {
            return 1;
          }
          if (uVar3 == 0) {
            if (iVar10 == 0) {
              puVar9 = &DAT_002dd88c;
              SoundPlay(1,mui_Effect0);
              iVar6 = 0;
            }
            else {
              iVar10 = iVar10 + -1;
              SoundPlay(1,mui_Effect0);
              iVar6 = iVar10 * 6;
              puVar9 = *(undefined **)(p_name + iVar10 * 4);
            }
            goto LAB_0002dbb4;
          }
          uVar3 = *(uint *)(m_joysticktab + uVar3 * 0x84 + 0x74);
          SoundPlay(1,mui_Effect0);
        }
        else if (uVar1 == 0x20) {
          if (local_190 == 0) {
            if (*(ushort *)(DAT_003af2b8 + 0x1a) < *(ushort *)(DAT_003af2b8 + 0x22)) {
              local_190 = 1;
              DAT_003af27c = 0xffffffff;
              uVar3 = 0;
            }
          }
          else {
            uVar3 = *(uint *)(m_joysticktab + uVar3 * 0x84 + 0x80);
            local_190 = ~uVar3 >> 0x1f;
          }
          goto LAB_0002d444;
        }
      }
      else {
        if (uVar1 == 0x41) break;
        if (uVar1 == 0x80) {
          if (local_190 == 0) {
            if (*(ushort *)(DAT_003af2b8 + 0x22) < *(ushort *)(DAT_003af2b8 + 0x1a)) {
              uVar3 = 3;
              local_190 = 1;
              DAT_003af27c = 0xffffffff;
            }
          }
          else {
            uVar3 = *(uint *)(m_joysticktab + uVar3 * 0x84 + 0x7c);
            local_190 = ~uVar3 >> 0x1f;
          }
LAB_0002d444:
          SoundPlay(1,mui_Effect1);
        }
      }
LAB_0002d454:
      if (DAT_003af27c != uVar3) {
LAB_0002d468:
        if ((int)DAT_003af27c < 1) {
          if (DAT_003af27c == 0) {
            UnDrawSelectBar(0x3afc44,DAT_003af2b8,8);
            mui_outputxy_t(DAT_003af29c,m_joysticktab._100_4_ + 0xf,m_joysticktab._104_4_,0x2a,
                           0xffff,*(undefined4 *)(p_name + iVar10 * 4));
          }
        }
        else {
          iVar6 = iVar10 * 6;
LAB_0002d6ac:
          UnDrawSelectBar(DAT_003af27c * 0x84 + 0x3afc44,DAT_003af2b8,8);
          uVar5 = *(uint *)(keyMapping + (DAT_003af27c + iVar6 + -1) * 4);
          if ((uVar5 & 0xffff0000) == 0) {
            iVar6 = DAT_003af27c * 0x84;
            strcpy(local_128,*(char **)(KayName + uVar5 * 4));
            mui_outputxy_t(DAT_003af29c,*(int *)(m_joysticktab + iVar6 + 100) + 0x14,
                           *(int *)(m_joysticktab + iVar6 + 0x68) + 4,0x20,0xffff,local_128);
          }
          else {
            iVar6 = DAT_003af27c * 0x84;
            local_128[0] = 'T';
            local_128[1] = '\0';
            strcpy(local_128 + 1,*(char **)(KayName + (uVar5 & 0xffff) * 4));
            mui_outputxy_t(DAT_003af29c,*(int *)(m_joysticktab + iVar6 + 100) + 0x14,
                           *(int *)(m_joysticktab + iVar6 + 0x68) + 4,0x20,0xffff,local_128);
          }
        }
        goto LAB_0002d4c0;
      }
      if ((local_194 + 1 & 0xf) == 0) {
        if (0 < (int)uVar3) goto LAB_0002d848;
        uVar5 = DAT_003af27c;
        if (uVar3 == 0) goto LAB_0002da14;
      }
LAB_0002d5f4:
      local_194 = local_194 + 1;
      if (DAT_003af274 != 0) goto LAB_0002d4f0;
    }
    else {
      if (uVar1 == 0x2000) {
        if (local_190 == 0) goto LAB_0002d454;
        if (0 < (int)uVar3) {
          iVar6 = 0x10008;
          if (Joy1_Delay < 0x1e) {
            iVar6 = 8;
          }
          goto LAB_0002d57c;
        }
        if (iVar10 < 3) {
          iVar10 = iVar10 + 1;
        }
        else {
          iVar10 = 0;
        }
        if (uVar3 == 0) {
          iVar6 = iVar10 * 6;
          puVar9 = *(undefined **)(p_name + iVar10 * 4);
          goto LAB_0002dbb4;
        }
        if (uVar3 != DAT_003af27c) goto LAB_0002d468;
        goto LAB_0002d5f4;
      }
      if (uVar1 < 0x2001) {
        if (uVar1 == 0x800) {
          if ((local_190 == 0) || ((int)uVar3 < 1)) goto LAB_0002d454;
          iVar6 = 0x1000b;
          if (Joy1_Delay < 0x1e) {
            iVar6 = 0xb;
          }
        }
        else {
          if (((uVar1 != 0x1000) || (local_190 == 0)) || ((int)uVar3 < 1)) goto LAB_0002d454;
          iVar6 = 0x10009;
          if (Joy1_Delay < 0x1e) {
            iVar6 = 9;
          }
        }
      }
      else if (uVar1 == 0x4000) {
        if ((local_190 == 0) || ((int)uVar3 < 1)) goto LAB_0002d454;
        if (Joy1_Delay < 0x1e) {
          iVar6 = 0;
        }
        else {
          iVar6 = 0x10000;
        }
      }
      else {
        if (((uVar1 != 0x8000) || (local_190 == 0)) || ((int)uVar3 < 1)) goto LAB_0002d454;
        iVar6 = 0x10001;
        if (Joy1_Delay < 0x1e) {
          iVar6 = 1;
        }
      }
LAB_0002d57c:
      iVar4 = uVar3 + iVar10 * 6 + -1;
      if (*(int *)(keyMapping + iVar4 * 4) != iVar6) {
        *(int *)(keyMapping + iVar4 * 4) = iVar6;
        UnDrawSelectBar(uVar5 * 0x84 + 0x3afc44,DAT_003af2b8,8);
        DAT_003af27c = 0xffffffff;
        ChangeSeting = 1;
        if (uVar3 == 0xffffffff) goto LAB_0002d5f4;
LAB_0002d4c0:
        uVar5 = uVar3;
        if ((int)uVar3 < 1) {
          if (uVar3 == 0) goto LAB_0002d9bc;
        }
        else {
          DAT_003af27c = uVar3;
          DrawSelectBar(uVar3 * 0x84 + 0x3afc44);
          uVar3 = *(uint *)(keyMapping + (iVar10 * 6 + DAT_003af27c + -1) * 4);
          pcVar2 = local_128;
          if ((uVar3 & 0xffff0000) != 0) {
            uVar3 = uVar3 & 0xffff;
            local_128[0] = 'T';
            local_128[1] = '\0';
            pcVar2 = local_128 + 1;
          }
          iVar6 = DAT_003af27c * 0x84;
          strcpy(pcVar2,*(char **)(KayName + uVar3 * 4));
          mui_outputxy_t(DAT_003af29c,*(int *)(m_joysticktab + iVar6 + 100) + 0x14,
                         *(int *)(m_joysticktab + iVar6 + 0x68) + 4,0x20,0x871c,local_128);
        }
        goto LAB_0002d4cc;
      }
      if (uVar3 != DAT_003af27c) goto LAB_0002d468;
      if ((local_194 + 1 & 0xf) != 0) goto LAB_0002d5f4;
LAB_0002d848:
      uVar5 = DAT_003af27c;
      local_194 = local_194 + 1;
      if ((local_194 & 0x10) == 0) {
        DrawSelectBar(uVar3 * 0x84 + 0x3afc44);
        uVar3 = DAT_003af27c;
        uVar1 = *(uint *)(keyMapping + (DAT_003af27c + iVar10 * 6 + -1) * 4);
        pcVar2 = local_128;
        if ((uVar1 & 0xffff0000) != 0) {
          uVar1 = uVar1 & 0xffff;
          local_128[0] = 'T';
          local_128[1] = '\0';
          pcVar2 = local_128 + 1;
        }
        strcpy(pcVar2,*(char **)(KayName + uVar1 * 4));
      }
      else {
        UnDrawSelectBar(uVar3 * 0x84 + 0x3afc44,DAT_003af2b8,8);
        uVar3 = DAT_003af27c;
        uVar1 = *(uint *)(keyMapping + (DAT_003af27c + iVar10 * 6 + -1) * 4);
        pcVar2 = local_128;
        if ((uVar1 & 0xffff0000) != 0) {
          uVar1 = uVar1 & 0xffff;
          local_128[0] = 'T';
          local_128[1] = '\0';
          pcVar2 = local_128 + 1;
        }
        strcpy(pcVar2,*(char **)(KayName + uVar1 * 4));
      }
      mui_outputxy_t(DAT_003af29c,*(int *)(m_joysticktab + uVar3 * 0x84 + 100) + 0x14,
                     *(int *)(m_joysticktab + uVar3 * 0x84 + 0x68) + 4,0x20,0x871c,local_128);
      uVar3 = local_194;
LAB_0002d4e0:
      local_194 = uVar3;
      DAT_003af274 = 1;
      uVar3 = uVar5;
LAB_0002d4f0:
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      DAT_003af274 = 0;
    }
    mui_WaitNMI();
  } while( true );
  JoystickTest(1);
  puVar9 = *(undefined **)(p_name + iVar10 * 4);
  goto LAB_0002d16c;
}
