/* ============================================================
 * mui_shoucang   @ 0x00028a74   size=3600B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_shoucang(void)

{
  gh_bool bVar1;
  gh_uint uVar2;
  gh_uint uVar3;
  char *pcVar4;
  gh_u4 uVar5;
  FILE *pFVar6;
  size_t __n;
  int iVar7;
  gh_uint uVar8;
  int iVar9;
  gh_uint uVar10;
  gh_uint uVar11;
  gh_uint uVar12;
  gh_uint local_4cc;
  int local_4c0;
  pthread_t pStack_4ac;
  int local_4a8;
  gh_uint local_4a4;
  gh_uint local_4a0;
  gh_uint local_49c;
  gh_uint local_498;
  int local_494;
  char acStack_490 [100];
  char acStack_42c [256];
  gh_u4 local_32c;
  char acStack_128 [260];
  
  local_4c0 = 0;
  local_4cc = 0;
  bVar1 = false;
  uVar10 = m_menulog._320_4_;
  uVar11 = 0;
  uVar12 = m_menulog._316_4_;
  DAT_003af278 = m_menulog._316_4_;
  DAT_003af27c = m_menulog._320_4_;
  m_menulog._0_4_ = DAT_003af26c;
joined_r0x00028b18:
  if (DAT_003af2b4 == (gh_u1 *)0x0) {
    uVar5 = GetWorkPath();
    sprintf(acStack_490,"%s/favorites.lst",uVar5);
    pFVar6 = fopen(acStack_490,"rb");
    if (pFVar6 == (FILE *)0x0) {
      pFVar6 = fopen(acStack_490,"w+b");
      fputc(0,pFVar6);
      fflush(pFVar6);
      iVar7 = fileno(pFVar6);
      fsync(iVar7);
      fclose(pFVar6);
      DAT_003af2b4 = malloc(1);
      *DAT_003af2b4 = 0;
    }
    else {
      fseek(pFVar6,0,2);
      __n = ftell(pFVar6);
      DAT_003af2b4 = malloc(__n + 1);
      fseek(pFVar6,0,0);
      fread(DAT_003af2b4,1,__n,pFVar6);
      DAT_003af2b4[__n] = 0;
      fclose(pFVar6);
    }
  }
  if (DAT_003af28c == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af28c,"menu.raw");
  }
  memcpy(DAT_003af29c,(void *)((int)DAT_003af28c + *DAT_003af28c),
         (gh_uint)*(gh_ushort *)((int)DAT_003af28c + 6) * (gh_uint)*(gh_ushort *)(DAT_003af28c + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 8);
  mui_fast_lsit = 0;
  uVar2 = mui_do_file_list(uVar12,DAT_003af2b4);
  mui_fast_lsit = 1;
  DAT_003af288 = uVar2;
  mui_DisplayGameSum();
  if (DAT_003af288 != 0) {
    DisplayThumbnailflag = 3;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
    uVar8 = DAT_003af27c;
    uVar11 = DAT_003af278;
    if ((0 < DAT_003af394) && (uVar2 != DAT_003af278)) {
      iVar7 = 0;
      do {
        iVar9 = iVar7 + 1;
        mui_DisplayLine_t(iVar7,uVar8,0);
        if (DAT_003af394 <= iVar9) break;
        iVar7 = iVar9;
      } while (uVar2 != uVar11 + iVar9);
    }
    uVar11 = DAT_003af284 >> 0x1f;
  }
  uVar8 = 0;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  if ((joy_key._0_4_ & 0x8000) != 0) goto LAB_00028db0;
LAB_00028c20:
  if (uVar8 == 0) {
    uVar8 = mui_ReadJoystick();
  }
  else {
    bVar1 = true;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
    uVar8 = mui_ReadJoystick();
  }
  if (uVar8 != 0x108) goto LAB_00028c34;
  goto LAB_00028eac;
LAB_00028c34:
  if (uVar8 < 0x108) {
    if (uVar8 == 0x10) {
      if ((int)uVar10 < 1) {
        if (uVar12 != 0) {
          uVar12 = uVar12 - 1;
          uVar10 = 0;
          mui_do_file_list(uVar12,DAT_003af2b4);
        }
      }
      else {
        uVar10 = uVar10 - 1;
      }
    }
    else {
      if (uVar8 < 0x11) {
        if (uVar8 == 1) {
          uVar10 = 0;
          shoucang(&file_info_list + DAT_003af27c * 0x404);
          DAT_003af278 = 0;
          DAT_003af27c = 0;
          uVar11 = uVar10;
          uVar12 = uVar10;
          goto joined_r0x00028b18;
        }
        if (uVar8 != 8) goto LAB_00028c5c;
        goto LAB_000293d4;
      }
      if (uVar8 != 0x40) {
        if (uVar8 == 0x80) {
          if ((int)uVar12 < DAT_003af394) {
            uVar10 = 0;
            mui_do_file_list(0,DAT_003af2b4);
            uVar12 = 0;
          }
          else {
            uVar12 = uVar12 - DAT_003af394;
            mui_do_file_list(uVar12,DAT_003af2b4);
          }
        }
        else {
          if (uVar8 != 0x20) goto LAB_00028c5c;
          if ((int)(uVar12 + uVar10 + DAT_003af394) < (int)uVar2) {
            uVar12 = uVar12 + DAT_003af394;
            mui_do_file_list(uVar12,DAT_003af2b4);
          }
          else {
            uVar8 = uVar12 + DAT_003af394;
            if ((int)uVar8 < (int)uVar2) {
              uVar10 = (uVar2 - 1) - uVar8;
              mui_do_file_list(uVar8,DAT_003af2b4);
              uVar12 = uVar8;
            }
          }
        }
        SoundPlay(1,mui_Effect1);
        goto LAB_00028c5c;
      }
      if ((int)uVar10 < DAT_003af394 + -1) {
        if (((int)uVar2 < 0) || ((int)(uVar12 + uVar10) < (int)(uVar2 - 1))) {
          uVar10 = uVar10 + 1;
        }
      }
      else if ((int)(uVar12 + uVar10) < (int)(uVar2 - 1)) {
        uVar12 = uVar12 + 1;
        mui_do_file_list(uVar12,DAT_003af2b4);
      }
    }
    SoundPlay(1,mui_Effect0);
    goto LAB_00028c5c;
  }
  if (uVar8 == 0x1000) {
    while ((DisplayThumbnailflag & 8) != 0) {
      usleep(1000);
    }
    DisplayThumbnailflag = DisplayThumbnailflag & 0xfffffffd;
    iVar7 = DAT_003af394 + 0xb;
    local_4a8 = (int)DAT_003af28c + DAT_003af28c[iVar7 * 4];
    local_4a4 = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 2);
    local_494 = DAT_003af2a0 << 1;
    local_4a0 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 10);
    local_49c = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 3);
    local_498 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 0xe);
    popwindows(&local_4a8);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    while( true ) {
      iVar7 = mui_ReadJoystick();
      if (iVar7 == 0x2000) {
        uVar5 = GetWorkPath();
        sprintf(acStack_490,"%s/favorites.lst",uVar5);
        pFVar6 = fopen(acStack_490,"wb");
        if (pFVar6 != (FILE *)0x0) {
          fputc(0,pFVar6);
          fflush(pFVar6);
          iVar7 = fileno(pFVar6);
          fsync(iVar7);
          fclose(pFVar6);
        }
        if (DAT_003af2b4 != (gh_u1 *)0x0) {
          free(DAT_003af2b4);
          DAT_003af2b4 = (gh_u1 *)0x0;
        }
        uVar11 = 0;
        popoffwindows(&local_4a8);
        uVar10 = 0;
        uVar12 = 0;
        DAT_003af278 = 0;
        DisplayThumbnailflag = DisplayThumbnailflag | 2;
        DAT_003af27c = 0;
        goto joined_r0x00028b18;
      }
      if (iVar7 == 0x4000) break;
      mui_WaitNMI();
    }
    popoffwindows(&local_4a8);
    DisplayThumbnailflag = DisplayThumbnailflag | 2;
    goto LAB_00028c5c;
  }
  if (uVar8 < 0x1001) {
    if (uVar8 == 0x400) {
LAB_00029470:
      DAT_003af26c = 2;
      SoundPlay(1,mui_Effect1);
      if ((AutoRestoreKey & 8) != 0) {
        m_menulog._316_4_ = uVar12;
        m_menulog._320_4_ = uVar10;
        return;
      }
    }
    else {
      if (uVar8 != 0x800) goto LAB_00028c5c;
LAB_00028e28:
      DAT_003af26c = 4;
      SoundPlay(1,mui_Effect1);
      if ((AutoRestoreKey & 8) != 0) {
        m_menulog._316_4_ = uVar12;
        m_menulog._320_4_ = uVar10;
      }
    }
    return;
  }
  if (uVar8 == 0x2100) {
LAB_00028eac:
    DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
    while (DisplayThumbnailflag != 0) {
      usleep(1000);
    }
    pcVar4 = stpcpy(acStack_42c,root_path);
    uVar2 = DAT_003af27c;
    iVar7 = DAT_003af27c * 0x404;
    pcVar4[0] = '/';
    pcVar4[1] = '\0';
    strcpy(pcVar4 + 1,&file_info_list + iVar7);
    local_32c = (&DAT_003b2320)[uVar2 * 0x101];
    pcVar4 = (char *)SeletEmuCore(acStack_42c);
    if (pcVar4 == (char *)0x0) {
      DisplayThumbnailflag = 1;
      pthread_create(&pStack_4ac,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
    }
    else {
      if ((AutoRestoreKey & 8) != 0) {
        m_menulog._316_4_ = uVar12;
        m_menulog._320_4_ = uVar10;
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
    if ((AutoRestoreKey & 8) != 0) {
      uVar10 = m_menulog._320_4_;
      uVar12 = m_menulog._316_4_;
    }
    DAT_003af278 = 0;
    DAT_003af27c = 0;
  }
  else {
    if (uVar8 == 0x4000) {
      while ((DisplayThumbnailflag & 8) != 0) {
        usleep(1000);
      }
      DisplayThumbnailflag = DisplayThumbnailflag & 0xfffffffd;
      iVar7 = DAT_003af394 + 10;
      local_4a8 = (int)DAT_003af28c + DAT_003af28c[iVar7 * 4];
      local_4a4 = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 2);
      local_494 = DAT_003af2a0 << 1;
      local_4a0 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 10);
      local_49c = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar7 * 4 + 3);
      local_498 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar7 * 0x10 + 0xe);
      popwindows(&local_4a8);
      mui_ReadJoystick();
      diff_prev = 0;
      m_time0 = GetTicks();
      while( true ) {
        iVar7 = mui_ReadJoystick();
        if (iVar7 == 0x2000) {
          uVar11 = 0;
          uVar10 = 0;
          uVar12 = 0;
          shoucang(&file_info_list + DAT_003af27c * 0x404);
          popoffwindows(&local_4a8);
          DAT_003af278 = 0;
          DAT_003af27c = 0;
          DisplayThumbnailflag = DisplayThumbnailflag | 2;
          goto joined_r0x00028b18;
        }
        if (iVar7 == 0x4000) break;
        mui_WaitNMI();
      }
      popoffwindows(&local_4a8);
      DisplayThumbnailflag = DisplayThumbnailflag | 2;
LAB_00028c5c:
      if (uVar12 == DAT_003af278) {
        if (uVar10 == DAT_003af27c) {
          local_4cc = local_4cc + 1;
          uVar3 = uVar11;
          if (((uVar11 == 0) || ((int)local_4cc < 0x65)) || (uVar3 = local_4cc & 1, uVar3 != 0)) {
            uVar8 = 0;
            uVar11 = uVar3;
            goto LAB_000290e4;
          }
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar10 + 1);
          mui_DisplayLine_t(uVar10,uVar10,local_4c0);
          if ((int)DAT_003af284 < 0x82) {
            local_4c0 = local_4c0 + -1;
          }
          else {
            local_4c0 = 0;
          }
          uVar8 = 0;
        }
        else {
          uVar8 = 0;
          local_4c0 = 0;
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
          mui_DisplayLine_t(DAT_003af27c,uVar10,0);
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar10 + 1);
          mui_DisplayLine_t(uVar10,uVar10,0);
          uVar11 = DAT_003af284 >> 0x1f;
          DisplayThumbnailflag = 3;
          local_4cc = 0;
          DAT_003af27c = uVar10;
          DAT_003af288 = uVar2;
          mui_DisplayGameSum();
        }
      }
      else {
        if (0 < DAT_003af394) {
          iVar7 = 1;
          do {
            if (uVar10 != iVar7 - 1U) {
              mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar7);
            }
            bVar1 = iVar7 < DAT_003af394;
            iVar7 = iVar7 + 1;
          } while (bVar1);
        }
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar10 + 1);
        DAT_003af27c = uVar10;
        if ((0 < DAT_003af394) && (uVar12 != uVar2)) {
          iVar7 = 0;
          do {
            iVar9 = iVar7 + 1;
            mui_DisplayLine_t(iVar7,uVar10,0);
            if (DAT_003af394 <= iVar9) break;
            iVar7 = iVar9;
          } while (uVar2 != uVar12 + iVar9);
        }
        uVar8 = 0;
        local_4c0 = 0;
        local_4cc = 0;
        uVar11 = DAT_003af284 >> 0x1f;
        DisplayThumbnailflag = 3;
        DAT_003af278 = uVar12;
        DAT_003af288 = uVar2;
        mui_DisplayGameSum();
      }
LAB_00028d5c:
      DAT_003af274 = 1;
      do {
        ForceFlashCount = 0;
        dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
        DAT_003af274 = 0;
        do {
          mui_WaitNMI();
          bVar1 = false;
          if ((joy_key._0_4_ & 0x8000) == 0) goto LAB_00028c20;
LAB_00028db0:
          uVar3 = mui_ReadJoystick();
          if ((uVar3 & 0xffff7fff) == 0x20) goto LAB_00028e28;
          if ((uVar3 & 0xffff7fff) == 0x80) goto LAB_00029470;
          uVar8 = uVar8 + 1;
          if ((uVar8 & 0xf) == 0) {
            if ((uVar8 & 0x10) == 0) {
              mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                            DAT_003af394 + 1 + DAT_003af26c);
            }
            else {
              mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                              DAT_003af394 + 1 + DAT_003af26c);
            }
            goto LAB_00028d5c;
          }
LAB_000290e4:
          if (bVar1) goto LAB_00028d5c;
        } while (DAT_003af274 == 0);
      } while( true );
    }
    if (uVar8 != 0x2000) goto LAB_00028c5c;
LAB_000293d4:
    if ((AutoRestoreKey & 8) != 0) {
      m_menulog._316_4_ = uVar12;
      m_menulog._320_4_ = uVar10;
      SaveMenuLog();
    }
    mui_run_game(&file_info_list + DAT_003af27c * 0x404);
    if ((AutoRestoreKey & 8) != 0) {
      uVar10 = m_menulog._320_4_;
      uVar12 = m_menulog._316_4_;
    }
    DAT_003af278 = 0;
    DAT_003af27c = 0;
  }
  goto joined_r0x00028b18;
}
