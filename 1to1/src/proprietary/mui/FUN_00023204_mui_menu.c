/* ============================================================
 * mui_menu   @ 0x00023204   size=2840B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_menu(void)

{
  bool bVar1;
  int iVar2;
  uint uVar3;
  char *pcVar4;
  int iVar5;
  int iVar6;
  int iVar7;
  int iVar8;
  int iVar9;
  uint uVar10;
  int iVar11;
  uint uVar12;
  uint local_4c0;
  int local_4bc;
  undefined4 local_498;
  pthread_t pStack_494;
  char acStack_490 [100];
  char acStack_42c [256];
  undefined4 local_32c;
  char acStack_128 [260];
  
  local_4bc = 0;
  Joy1_Press = 0;
  local_4c0 = 0;
  bVar1 = false;
  Joy1_Delay = 0;
  DAT_003af284 = 0;
  DAT_003af2ac = (void *)0x0;
  DAT_003af288 = 0;
  m_menulog._0_4_ = DAT_003af26c;
  DAT_003af278 = m_menulog._288_4_;
  DAT_003af27c = m_menulog._284_4_;
  scr_h_size = 0x500;
  DAT_003af274 = 0;
  DAT_003af2a0 = 0x500;
  scr_v_size = 0x2d0;
  OutRect._4_4_ = 0;
  OutRect._8_4_ = 0;
  OutRect._12_4_ = 0;
  DAT_003af2a4 = 0x2d0;
  OutRect._20_4_ = 0x2d0;
  OutRect._0_4_ = 0x500;
  OutRect._16_4_ = 0x500;
joined_r0x0002331c:
  iVar7 = DAT_003af27c;
  iVar11 = DAT_003af278;
  if (DAT_003af28c == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af28c,"menu.raw");
  }
  if (DAT_003af2ac == (void *)0x0) {
    sprintf(acStack_490,"%s/root.dat",root_path);
    hz = OpenZipU(acStack_490,0,2);
    if ((hz == 0) || (zr = FindZipItemA(hz,"fileinfo.txt",1,&local_498,ze), zr != 0)) {
      RARCH_LOG("find %s fail!\n",acStack_490);
    }
    else {
      DAT_003af2ac = malloc(ze._296_4_ + 1);
      zr = UnzipItem(hz,local_498,DAT_003af2ac,0,3);
      *(undefined1 *)((int)DAT_003af2ac + ze._296_4_) = 0;
    }
  }
  memcpy(DAT_003af29c,(void *)((int)DAT_003af28c + *DAT_003af28c),
         (uint)*(ushort *)((int)DAT_003af28c + 6) * (uint)*(ushort *)(DAT_003af28c + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
  mui_fast_lsit = 0;
  iVar2 = mui_do_file_list(iVar11,DAT_003af2ac);
  mui_fast_lsit = 1;
  DAT_003af288 = iVar2;
  mui_DisplayGameSum();
  iVar5 = DAT_003af27c;
  iVar6 = DAT_003af278;
  DisplayThumbnailflag = 3;
  if ((0 < DAT_003af394) && (iVar2 != DAT_003af278)) {
    iVar8 = 0;
    do {
      iVar9 = iVar8 + 1;
      mui_DisplayLine_t(iVar8,iVar5,0);
      if (DAT_003af394 <= iVar9) break;
      iVar8 = iVar9;
    } while (iVar2 != iVar9 + iVar6);
  }
  uVar10 = DAT_003af284;
  uVar12 = 0;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  uVar10 = uVar10 >> 0x1f;
  if ((joy_key._0_4_ & 0x8000) != 0) goto LAB_00023688;
LAB_0002348c:
  if (uVar12 != 0) {
    bVar1 = true;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
  }
  uVar12 = mui_ReadJoystick();
  if (uVar12 == 0x80) {
    if (iVar11 < DAT_003af394) {
      iVar7 = 0;
      mui_do_file_list(0,DAT_003af2ac);
      iVar11 = 0;
    }
    else {
      iVar11 = iVar11 - DAT_003af394;
      mui_do_file_list(iVar11,DAT_003af2ac);
    }
LAB_0002351c:
    SoundPlay(1,mui_Effect1);
  }
  else {
    if (0x80 < uVar12) {
      if (uVar12 == 0x800) {
LAB_00023978:
        DAT_003af26c = 1;
        SoundPlay(1,mui_Effect1);
        if ((AutoRestoreKey & 1) == 0) {
          return;
        }
        m_menulog._284_4_ = iVar7;
        m_menulog._288_4_ = iVar11;
        return;
      }
      if (uVar12 < 0x801) {
        if (uVar12 != 0x108) {
          if (uVar12 == 0x400) {
LAB_00023700:
            SoundPlay(1,mui_Effect1);
            if ((AutoRestoreKey & 1) == 0) {
              DAT_003af26c = 5;
              return;
            }
            DAT_003af26c = 5;
            m_menulog._284_4_ = iVar7;
            m_menulog._288_4_ = iVar11;
            return;
          }
          goto LAB_00023528;
        }
      }
      else {
        if (uVar12 == 0x2000) goto LAB_00023a80;
        if (uVar12 != 0x2100) goto LAB_00023528;
      }
      DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
      while (DisplayThumbnailflag != 0) {
        usleep(1000);
      }
      pcVar4 = stpcpy(acStack_42c,root_path);
      iVar5 = DAT_003af27c;
      iVar6 = DAT_003af27c * 0x404;
      pcVar4[0] = '/';
      pcVar4[1] = '\0';
      strcpy(pcVar4 + 1,&file_info_list + iVar6);
      local_32c = (&DAT_003b2320)[iVar5 * 0x101];
      pcVar4 = (char *)SeletEmuCore(acStack_42c);
      if (pcVar4 == (char *)0x0) {
        DisplayThumbnailflag = 1;
        pthread_create(&pStack_494,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
      }
      else {
        if ((AutoRestoreKey & 1) != 0) {
          m_menulog._284_4_ = iVar7;
          m_menulog._288_4_ = iVar11;
          SaveMenuLog();
        }
        strcpy(acStack_128,pcVar4);
        filelist_run_game(acStack_42c);
      }
      if (ZIP_BUF != (void *)0x0) {
        free(ZIP_BUF);
      }
      ZIP_BUF = (void *)0x0;
      ZIP_BUF_SIZE = 0;
      DAT_003af278 = iVar11;
      DAT_003af27c = iVar7;
      goto joined_r0x0002331c;
    }
    if (uVar12 == 0x10) {
      if (iVar7 < 1) {
        if (iVar11 != 0) {
          iVar11 = iVar11 + -1;
          iVar7 = 0;
          mui_do_file_list(iVar11,DAT_003af2ac);
        }
      }
      else {
        iVar7 = iVar7 + -1;
      }
    }
    else {
      if (uVar12 < 0x11) {
        if (uVar12 != 1) {
          if (uVar12 != 8) goto LAB_00023528;
          goto LAB_00023a80;
        }
        shoucang(&file_info_list + DAT_003af27c * 0x404);
        mui_do_file_list(iVar11,DAT_003af2ac);
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar7 + 1);
        mui_DisplayLine_t(iVar7,iVar7,0);
        bVar1 = true;
        goto LAB_00023528;
      }
      if (uVar12 == 0x20) {
        if (iVar11 + iVar7 + DAT_003af394 < iVar2) {
          iVar11 = iVar11 + DAT_003af394;
          mui_do_file_list(iVar11,DAT_003af2ac);
        }
        else {
          iVar6 = iVar11 + DAT_003af394;
          if (iVar6 < iVar2) {
            iVar7 = (iVar2 + -1) - iVar6;
            mui_do_file_list(iVar6,DAT_003af2ac);
            iVar11 = iVar6;
          }
        }
        goto LAB_0002351c;
      }
      if (uVar12 != 0x40) goto LAB_00023528;
      if (iVar7 < DAT_003af394 + -1) {
        if ((iVar2 < 0) || (iVar11 + iVar7 < iVar2 + -1)) {
          iVar7 = iVar7 + 1;
        }
      }
      else if (iVar11 + iVar7 < iVar2 + -1) {
        iVar11 = iVar11 + 1;
        mui_do_file_list(iVar11,DAT_003af2ac);
      }
    }
    SoundPlay(1,mui_Effect0);
  }
LAB_00023528:
  if (iVar11 == DAT_003af278) {
    if (iVar7 == DAT_003af27c) {
      local_4c0 = local_4c0 + 1;
      uVar3 = uVar10;
      if (((uVar10 == 0) || ((int)local_4c0 < 0x65)) || (uVar3 = local_4c0 & 1, uVar3 != 0)) {
        uVar12 = 0;
        uVar10 = uVar3;
        goto LAB_000237b4;
      }
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar7 + 1);
      mui_DisplayLine_t(iVar7,iVar7,local_4bc);
      if ((int)DAT_003af284 < 0x82) {
        local_4bc = local_4bc + -1;
      }
      else {
        local_4bc = 0;
      }
      uVar12 = 0;
    }
    else {
      uVar12 = 0;
      local_4bc = 0;
      mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
      mui_DisplayLine_t(DAT_003af27c,iVar7,0);
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar7 + 1);
      mui_DisplayLine_t(iVar7,iVar7,0);
      uVar10 = DAT_003af284 >> 0x1f;
      DisplayThumbnailflag = 3;
      local_4c0 = 0;
      DAT_003af27c = iVar7;
      DAT_003af288 = iVar2;
      mui_DisplayGameSum();
    }
  }
  else {
    if (0 < DAT_003af394) {
      iVar6 = 1;
      do {
        if (iVar7 != iVar6 + -1) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar6);
        }
        bVar1 = iVar6 < DAT_003af394;
        iVar6 = iVar6 + 1;
      } while (bVar1);
    }
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar7 + 1);
    DAT_003af278 = iVar11;
    DAT_003af27c = iVar7;
    if ((0 < DAT_003af394) && (iVar11 != iVar2)) {
      iVar6 = 0;
      do {
        iVar5 = iVar6 + 1;
        mui_DisplayLine_t(iVar6,iVar7,0);
        if (DAT_003af394 <= iVar5) break;
        iVar6 = iVar5;
      } while (iVar2 != iVar11 + iVar5);
    }
    uVar12 = 0;
    local_4bc = 0;
    local_4c0 = 0;
    DAT_003af280 = 0;
    uVar10 = DAT_003af284 >> 0x1f;
    DisplayThumbnailflag = 3;
    DAT_003af288 = iVar2;
    mui_DisplayGameSum();
  }
LAB_00023630:
  DAT_003af274 = DAT_003af274 | 1;
  do {
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    DAT_003af274 = 0;
    do {
      mui_WaitNMI();
      bVar1 = false;
      if ((joy_key._0_4_ & 0x8000) == 0) goto LAB_0002348c;
LAB_00023688:
      uVar3 = mui_ReadJoystick();
      if ((uVar3 & 0xffff7fff) == 0x20) goto LAB_00023978;
      if ((uVar3 & 0xffff7fff) == 0x80) goto LAB_00023700;
      uVar12 = uVar12 + 1;
      if ((uVar12 & 0xf) == 0) {
        if ((uVar12 & 0x10) == 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c)
          ;
        }
        else {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                          DAT_003af394 + 1 + DAT_003af26c);
        }
        goto LAB_00023630;
      }
LAB_000237b4:
      if (bVar1) goto LAB_00023630;
    } while (DAT_003af274 == 0);
  } while( true );
LAB_00023a80:
  if ((AutoRestoreKey & 1) != 0) {
    m_menulog._284_4_ = iVar7;
    m_menulog._288_4_ = iVar11;
    SaveMenuLog();
  }
  mui_run_game(&file_info_list + DAT_003af27c * 0x404);
  RARCH_LOG("mui_menu exit back to here...\r\n");
  DAT_003af278 = iVar11;
  DAT_003af27c = iVar7;
  goto joined_r0x0002331c;
}
