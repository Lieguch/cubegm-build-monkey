/* ============================================================
 * mui_recent   @ 0x000277bc   size=4492B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_recent(void)

{
  gh_bool bVar1;
  char cVar2;
  gh_u4 uVar3;
  FILE *pFVar4;
  size_t sVar5;
  int iVar6;
  gh_uint uVar7;
  char *pcVar8;
  gh_byte *__ptr;
  gh_byte bVar9;
  gh_uint uVar10;
  int iVar11;
  gh_byte *pbVar12;
  int iVar13;
  gh_uint uVar14;
  gh_byte *pbVar15;
  int iVar17;
  int iVar18;
  int iVar19;
  int iVar20;
  gh_uint local_670;
  int local_664;
  FILE *local_644;
  int local_628;
  gh_uint local_624;
  gh_uint local_620;
  gh_uint local_61c;
  gh_uint local_618;
  int local_614;
  char acStack_610 [100];
  gh_byte abStack_5ac [128];
  pthread_t apStack_52c [64];
  char local_42c [256];
  gh_u4 local_32c;
  char local_328 [128];
  char local_2a8 [128];
  char local_228 [128];
  char local_1a8 [128];
  char acStack_128 [260];
  gh_byte *pbVar16;
  
  uVar14 = 0;
  m_menulog._0_4_ = DAT_003af26c;
  local_664 = 0;
  local_670 = 0;
  bVar1 = false;
  DAT_003af278 = m_menulog._308_4_;
  DAT_003af27c = m_menulog._312_4_;
  iVar19 = m_menulog._312_4_;
  iVar20 = m_menulog._308_4_;
LAB_00027864:
  do {
    uVar3 = GetWorkPath();
    sprintf(acStack_610,"%s/recent.lst",uVar3);
    pFVar4 = fopen(acStack_610,"rb");
    if (pFVar4 == (FILE *)0x0) {
      pFVar4 = fopen(acStack_610,"w+b");
      fputc(0,pFVar4);
      fflush(pFVar4);
      iVar6 = fileno(pFVar4);
      fsync(iVar6);
      fclose(pFVar4);
      DAT_003af2b0 = malloc(1);
      *DAT_003af2b0 = 0;
    }
    else {
      fseek(pFVar4,0,2);
      sVar5 = ftell(pFVar4);
      if (DAT_003af2b0 != (gh_u1 *)0x0) {
        free(DAT_003af2b0);
      }
      DAT_003af2b0 = malloc(sVar5 + 1);
      fseek(pFVar4,0,0);
      fread(DAT_003af2b0,1,sVar5,pFVar4);
      DAT_003af2b0[sVar5] = 0;
      fclose(pFVar4);
    }
    if (DAT_003af28c == (int *)0x0) {
      mui_LoadUIResource(&DAT_003af28c,"menu.raw");
    }
    memcpy(DAT_003af29c,(void *)((int)DAT_003af28c + *DAT_003af28c),
           (gh_uint)*(gh_ushort *)((int)DAT_003af28c + 6) * (gh_uint)*(gh_ushort *)(DAT_003af28c + 1) * 2);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 7);
    mui_fast_lsit = 0;
    iVar6 = mui_do_file_list(iVar20,DAT_003af2b0);
    mui_fast_lsit = 1;
    DAT_003af288 = iVar6;
    mui_DisplayGameSum();
    if (DAT_003af288 != 0) {
      DisplayThumbnailflag = 3;
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
      iVar11 = DAT_003af27c;
      iVar13 = DAT_003af278;
      if ((0 < DAT_003af394) && (iVar6 != DAT_003af278)) {
        iVar17 = 0;
        do {
          iVar18 = iVar17 + 1;
          mui_DisplayLine_t(iVar17,iVar11,0);
          if (DAT_003af394 <= iVar18) break;
          iVar17 = iVar18;
        } while (iVar6 != iVar18 + iVar13);
      }
      uVar14 = DAT_003af284 >> 0x1f;
    }
    uVar10 = 0;
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    mui_ReadJoystick();
    diff_prev = 0;
    m_time0 = GetTicks();
    if ((joy_key._0_4_ & 0x8000) != 0) goto LAB_00027ba4;
LAB_00027a14:
    if (uVar10 != 0) {
      bVar1 = true;
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
      uVar10 = mui_ReadJoystick();
      if (uVar10 != 0x108) goto LAB_00027a28;
      goto LAB_00027ca0;
    }
    uVar10 = mui_ReadJoystick();
    if (uVar10 == 0x108) goto LAB_00027ca0;
LAB_00027a28:
    if (uVar10 < 0x108) {
      if (uVar10 == 0x10) {
        if (iVar19 < 1) {
          if (iVar20 != 0) {
            iVar20 = iVar20 + -1;
            iVar19 = 0;
            mui_do_file_list(iVar20,DAT_003af2b0);
          }
        }
        else {
          iVar19 = iVar19 + -1;
        }
LAB_000284a8:
        SoundPlay(1,mui_Effect0);
        goto LAB_00027a50;
      }
      if (0x10 < uVar10) {
        if (uVar10 != 0x40) {
          if (uVar10 == 0x80) {
            if (iVar20 < DAT_003af394) {
              iVar19 = 0;
              mui_do_file_list(0,DAT_003af2b0);
              iVar20 = 0;
            }
            else {
              iVar20 = iVar20 - DAT_003af394;
              mui_do_file_list(iVar20,DAT_003af2b0);
            }
          }
          else {
            if (uVar10 != 0x20) goto LAB_00027a50;
            if (iVar20 + iVar19 + DAT_003af394 < iVar6) {
              iVar20 = iVar20 + DAT_003af394;
              mui_do_file_list(iVar20,DAT_003af2b0);
            }
            else {
              iVar13 = iVar20 + DAT_003af394;
              if (iVar13 < iVar6) {
                iVar19 = (iVar6 + -1) - iVar13;
                mui_do_file_list(iVar13,DAT_003af2b0);
                iVar20 = iVar13;
              }
            }
          }
          SoundPlay(1,mui_Effect1);
          goto LAB_00027a50;
        }
        if (iVar19 < DAT_003af394 + -1) {
          if ((iVar6 < 0) || (iVar20 + iVar19 < iVar6 + -1)) {
            iVar19 = iVar19 + 1;
          }
        }
        else if (iVar20 + iVar19 < iVar6 + -1) {
          iVar20 = iVar20 + 1;
          mui_do_file_list(iVar20,DAT_003af2b0);
        }
        goto LAB_000284a8;
      }
      if (uVar10 != 1) {
        if (uVar10 != 8) goto LAB_00027a50;
        goto LAB_0002827c;
      }
      shoucang(&file_info_list + DAT_003af27c * 0x404);
      mui_do_file_list(iVar20,DAT_003af2b0);
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar19 + 1);
      mui_DisplayLine_t(iVar19,iVar19,0);
      bVar1 = true;
      goto LAB_00027a50;
    }
    if (uVar10 == 0x1000) {
      while ((DisplayThumbnailflag & 8) != 0) {
        usleep(1000);
      }
      DisplayThumbnailflag = DisplayThumbnailflag & 0xfffffffd;
      iVar13 = DAT_003af394 + 0xb;
      local_628 = (int)DAT_003af28c + DAT_003af28c[iVar13 * 4];
      local_624 = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar13 * 4 + 2);
      local_614 = DAT_003af2a0 << 1;
      local_620 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar13 * 0x10 + 10);
      local_61c = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar13 * 4 + 3);
      local_618 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar13 * 0x10 + 0xe);
      popwindows(&local_628);
      mui_ReadJoystick();
      diff_prev = 0;
      m_time0 = GetTicks();
      while( true ) {
        iVar13 = mui_ReadJoystick();
        if (iVar13 == 0x2000) {
          uVar3 = GetWorkPath();
          sprintf(acStack_610,"%s/recent.lst",uVar3);
          pFVar4 = fopen(acStack_610,"wb");
          if (pFVar4 != (FILE *)0x0) {
            fputc(0,pFVar4);
            fflush(pFVar4);
            iVar6 = fileno(pFVar4);
            fsync(iVar6);
            fclose(pFVar4);
          }
          popoffwindows(&local_628);
          DisplayThumbnailflag = DisplayThumbnailflag | 2;
          goto LAB_00027864;
        }
        if (iVar13 == 0x4000) break;
        mui_WaitNMI();
      }
      popoffwindows(&local_628);
      DisplayThumbnailflag = DisplayThumbnailflag | 2;
      goto LAB_00027a50;
    }
    if (uVar10 < 0x1001) {
      if (uVar10 == 0x400) {
LAB_00028198:
        DAT_003af26c = 1;
        SoundPlay(1,mui_Effect1);
        if ((AutoRestoreKey & 4) != 0) {
          m_menulog._308_4_ = iVar20;
          m_menulog._312_4_ = iVar19;
          return;
        }
      }
      else {
        if (uVar10 != 0x800) goto LAB_00027a50;
LAB_00027c1c:
        DAT_003af26c = 3;
        SoundPlay(1,mui_Effect1);
        if ((AutoRestoreKey & 4) != 0) {
          m_menulog._308_4_ = iVar20;
          m_menulog._312_4_ = iVar19;
        }
      }
      return;
    }
    if (uVar10 == 0x2100) {
LAB_00027ca0:
      DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
      while (DisplayThumbnailflag != 0) {
        usleep(1000);
      }
      pcVar8 = stpcpy(local_42c,root_path);
      iVar20 = DAT_003af27c;
      iVar19 = DAT_003af27c * 0x404;
      pcVar8[0] = '/';
      pcVar8[1] = '\0';
      strcpy(pcVar8 + 1,&file_info_list + iVar19);
      local_32c = (&DAT_003b2320)[iVar20 * 0x101];
      pcVar8 = (char *)SeletEmuCore(local_42c);
      if (pcVar8 == (char *)0x0) {
        DisplayThumbnailflag = 1;
        pthread_create(apStack_52c,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
      }
      else {
        if ((AutoRestoreKey & 4) != 0) {
          m_menulog._308_4_ = 0;
          m_menulog._312_4_ = 0;
          SaveMenuLog();
        }
        strcpy(acStack_128,pcVar8);
        filelist_run_game(local_42c);
      }
      if (ZIP_BUF != (void *)0x0) {
        free(ZIP_BUF);
      }
      iVar19 = 0;
      iVar20 = 0;
      ZIP_BUF = (void *)0x0;
      DAT_003af27c = 0;
      ZIP_BUF_SIZE = 0;
      DAT_003af278 = 0;
    }
    else {
      if (uVar10 == 0x4000) {
        while ((DisplayThumbnailflag & 8) != 0) {
          usleep(1000);
        }
        DisplayThumbnailflag = DisplayThumbnailflag & 0xfffffffd;
        iVar13 = DAT_003af394 + 10;
        local_628 = (int)DAT_003af28c + DAT_003af28c[iVar13 * 4];
        local_624 = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar13 * 4 + 2);
        local_614 = DAT_003af2a0 << 1;
        local_620 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar13 * 0x10 + 10);
        local_61c = (gh_uint)*(gh_ushort *)(DAT_003af28c + iVar13 * 4 + 3);
        local_618 = (gh_uint)*(gh_ushort *)((int)DAT_003af28c + iVar13 * 0x10 + 0xe);
        popwindows(&local_628);
        mui_ReadJoystick();
        diff_prev = 0;
        m_time0 = GetTicks();
        while( true ) {
          iVar11 = mui_ReadJoystick();
          iVar13 = DAT_003af27c;
          if (iVar11 == 0x2000) {
            uVar3 = GetWorkPath();
            sprintf((char *)apStack_52c,"%s/recent.lst",uVar3);
            pFVar4 = fopen((char *)apStack_52c,"rb");
            if (pFVar4 == (FILE *)0x0) {
              local_644 = fopen((char *)apStack_52c,"wt");
            }
            else {
              fseek(pFVar4,0,2);
              sVar5 = ftell(pFVar4);
              __ptr = malloc(sVar5 + 1);
              fseek(pFVar4,0,0);
              fread(__ptr,1,sVar5,pFVar4);
              __ptr[sVar5] = 0;
              fclose(pFVar4);
              local_644 = fopen((char *)apStack_52c,"wt");
              if (__ptr != (gh_byte *)0x0) {
                iVar6 = 0;
                pbVar12 = __ptr;
                pbVar15 = abStack_5ac;
                goto LAB_00027fe8;
              }
            }
            fputc(0,local_644);
            goto LAB_000285dc;
          }
          if (iVar11 == 0x4000) break;
          mui_WaitNMI();
        }
        popoffwindows(&local_628);
        DisplayThumbnailflag = DisplayThumbnailflag | 2;
LAB_00027a50:
        if (iVar20 == DAT_003af278) {
          if (iVar19 == DAT_003af27c) {
            local_670 = local_670 + 1;
            uVar7 = uVar14;
            if (((uVar14 == 0) || ((int)local_670 < 0x65)) || (uVar7 = local_670 & 1, uVar7 != 0)) {
              uVar10 = 0;
              uVar14 = uVar7;
              goto LAB_00027de8;
            }
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar19 + 1);
            mui_DisplayLine_t(iVar19,iVar19,local_664);
            if ((int)DAT_003af284 < 0x82) {
              local_664 = local_664 + -1;
            }
            else {
              local_664 = 0;
            }
            uVar10 = 0;
          }
          else {
            uVar10 = 0;
            local_664 = 0;
            mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
            mui_DisplayLine_t(DAT_003af27c,iVar19,0);
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar19 + 1);
            mui_DisplayLine_t(iVar19,iVar19,0);
            uVar14 = DAT_003af284 >> 0x1f;
            DisplayThumbnailflag = 3;
            local_670 = 0;
            DAT_003af27c = iVar19;
            DAT_003af288 = iVar6;
            mui_DisplayGameSum();
          }
        }
        else {
          if (0 < DAT_003af394) {
            iVar13 = 1;
            do {
              if (iVar19 != iVar13 + -1) {
                mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar13);
              }
              bVar1 = iVar13 < DAT_003af394;
              iVar13 = iVar13 + 1;
            } while (bVar1);
          }
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar19 + 1);
          DAT_003af278 = iVar20;
          DAT_003af27c = iVar19;
          if ((0 < DAT_003af394) && (iVar20 != iVar6)) {
            iVar13 = 0;
            do {
              iVar11 = iVar13 + 1;
              mui_DisplayLine_t(iVar13,iVar19,0);
              if (DAT_003af394 <= iVar11) break;
              iVar13 = iVar11;
            } while (iVar6 != iVar11 + iVar20);
          }
          uVar10 = 0;
          local_664 = 0;
          local_670 = 0;
          DisplayThumbnailflag = 3;
          uVar14 = DAT_003af284 >> 0x1f;
          DAT_003af288 = iVar6;
          mui_DisplayGameSum();
        }
LAB_00027b50:
        DAT_003af274 = 1;
        do {
          ForceFlashCount = 0;
          dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
          DAT_003af274 = 0;
          do {
            mui_WaitNMI();
            bVar1 = false;
            if ((joy_key._0_4_ & 0x8000) == 0) goto LAB_00027a14;
LAB_00027ba4:
            uVar7 = mui_ReadJoystick();
            if ((uVar7 & 0xffff7fff) == 0x20) goto LAB_00027c1c;
            if ((uVar7 & 0xffff7fff) == 0x80) goto LAB_00028198;
            uVar10 = uVar10 + 1;
            if ((uVar10 & 0xf) == 0) {
              if ((uVar10 & 0x10) == 0) {
                mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                              DAT_003af394 + 1 + DAT_003af26c);
              }
              else {
                mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                                DAT_003af394 + 1 + DAT_003af26c);
              }
              goto LAB_00027b50;
            }
LAB_00027de8:
            if (bVar1) goto LAB_00027b50;
          } while (DAT_003af274 == 0);
        } while( true );
      }
      if (uVar10 != 0x2000) goto LAB_00027a50;
LAB_0002827c:
      if ((AutoRestoreKey & 4) != 0) {
        m_menulog._308_4_ = 0;
        m_menulog._312_4_ = 0;
        SaveMenuLog();
      }
      iVar19 = 0;
      mui_run_game(&file_info_list + DAT_003af27c * 0x404);
      DAT_003af278 = 0;
      DAT_003af27c = 0;
      iVar20 = iVar19;
    }
  } while( true );
  while (bVar9 != 0) {
LAB_00027fe8:
    bVar9 = *pbVar12;
    if (bVar9 == 0xd) goto LAB_0002800c;
    if (0xd < bVar9) goto LAB_00028020;
    while ((bVar9 != 0 && (pbVar16 = pbVar15, bVar9 != 10))) {
      while( true ) {
        pbVar15 = pbVar16 + 1;
        *pbVar16 = bVar9;
LAB_0002800c:
        do {
          pbVar12 = pbVar12 + 1;
          bVar9 = *pbVar12;
        } while (bVar9 == 0xd);
        if (bVar9 < 0xe) break;
LAB_00028020:
        if ((bVar9 == 0x2c) || (pbVar16 = pbVar15, bVar9 == 0x3b)) goto LAB_00028030;
      }
    }
LAB_00028030:
    if (iVar6 == 0) {
      cVar2 = '\0';
      if (abStack_5ac < pbVar15) {
        *pbVar15 = 0;
        strcpy(local_42c,(char *)abStack_5ac);
        cVar2 = local_42c[0];
      }
LAB_00028048:
      local_42c[0] = cVar2;
      if (bVar9 == 10) {
        if (local_328[0] == '\0') {
LAB_000288f8:
          mui_extract_basename(local_328,local_42c,0x80);
        }
        if (local_228[0] == '\0') {
          strcpy(local_228,local_328);
          strupr();
        }
        if (local_2a8[0] == '\0') {
          strcpy(local_2a8,local_328);
        }
        if (local_1a8[0] == '\0') {
          strcpy(local_1a8,local_228);
        }
        bVar9 = *pbVar12;
        if (bVar9 == 10) {
          pbVar12 = pbVar12 + 1;
          if ((local_42c[0] != '\0') &&
             (iVar6 = strcmp(&file_info_list + iVar13 * 0x404,local_42c), iVar6 != 0)) {
            fprintf(local_644,"%s;%s;%s;%s;%s\n",local_42c,local_328,local_228,local_2a8,local_1a8);
          }
          local_42c[0] = '\0';
          iVar6 = 0;
          pbVar15 = abStack_5ac;
          goto LAB_00027fe8;
        }
      }
    }
    else {
      if (iVar6 != 1) {
        cVar2 = local_42c[0];
        if (iVar6 == 2) {
          if (abStack_5ac < pbVar15) {
            *pbVar15 = 0;
            strcpy(local_228,(char *)abStack_5ac);
            cVar2 = local_42c[0];
          }
          else {
            local_228[0] = '\0';
          }
        }
        else if (iVar6 == 3) {
          if (abStack_5ac < pbVar15) {
            *pbVar15 = 0;
            strcpy(local_2a8,(char *)abStack_5ac);
            cVar2 = local_42c[0];
          }
          else {
            local_2a8[0] = '\0';
          }
        }
        else if (iVar6 == 4) {
          if (abStack_5ac < pbVar15) {
            *pbVar15 = 0;
            strcpy(local_1a8,(char *)abStack_5ac);
            cVar2 = local_42c[0];
          }
          else {
            local_1a8[0] = '\0';
          }
        }
        goto LAB_00028048;
      }
      if (abStack_5ac < pbVar15) {
        *pbVar15 = 0;
        strcpy(local_328,(char *)abStack_5ac);
        cVar2 = local_42c[0];
        goto LAB_00028048;
      }
      local_328[0] = '\0';
      if (bVar9 == 10) goto LAB_000288f8;
    }
    if (bVar9 == 0x2c || bVar9 == 0x3b) {
      pbVar12 = pbVar12 + 1;
      iVar6 = iVar6 + 1;
      pbVar15 = abStack_5ac;
      goto LAB_00027fe8;
    }
  }
  fputc(0,local_644);
  free(__ptr);
LAB_000285dc:
  fflush(local_644);
  iVar6 = fileno(local_644);
  fsync(iVar6);
  fclose(local_644);
  popoffwindows(&local_628);
  DisplayThumbnailflag = DisplayThumbnailflag | 2;
  goto LAB_00027864;
}
