/* ============================================================
 * mui_type   @ 0x00023e10   size=4380B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_type(void)

{
  bool bVar1;
  uint uVar2;
  char *pcVar3;
  uint uVar4;
  int iVar5;
  int iVar6;
  uint uVar7;
  int iVar8;
  uint uVar9;
  int iVar10;
  int local_474;
  int local_468;
  uint local_464;
  int local_45c;
  uint local_450;
  undefined4 local_434;
  pthread_t pStack_430;
  char acStack_42c [256];
  undefined4 local_32c;
  char acStack_128 [260];
  
  DAT_003af278 = m_menulog._300_4_;
  DAT_003af27c = m_menulog._304_4_;
  iVar5 = 0;
  local_474 = m_menulog._292_4_;
  m_menulog._0_4_ = DAT_003af26c;
  local_450 = 0;
  local_468 = 0;
  local_464 = 0;
  local_45c = m_menulog._296_4_;
  bVar1 = false;
  uVar4 = m_menulog._304_4_;
  iVar10 = m_menulog._300_4_;
LAB_00023eb8:
  while ((DisplayThumbnailflag & 8) != 0) {
    usleep(1000);
  }
  DisplayThumbnailflag = 1;
  if ((DAT_003af28c == (int *)0x0) &&
     (mui_LoadUIResource(&DAT_003af28c,"menu.raw"), DAT_003af28c == (int *)0x0)) {
    mui_LoadUIResource(&DAT_003af28c,"menu.raw");
  }
  if (DAT_003af298 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af298,"type.raw");
  }
  if (DAT_003af2a8 == (void *)0x0) {
    uVar9 = (uint)(byte)m_Typetab[local_45c * 0x14];
    sprintf(acStack_42c,"%s/%03d/%03d.dat",root_path,uVar9,uVar9);
    DAT_003af270 = uVar9;
    hz = OpenZipU(acStack_42c,0,2);
    if (hz == 0) {
      RARCH_LOG("find %s fail!\n",acStack_42c);
    }
    else {
      RARCH_LOG("find %s ok!\n",acStack_42c);
      GetZipItemA(hz,0xffffffff,ze);
      zr = FindZipItemA(hz,"filelist.txt",1,&local_434,ze);
      if (zr == 0) {
        DAT_003af2a8 = malloc(ze._296_4_ + 1);
        zr = UnzipItem(hz,local_434,DAT_003af2a8,0,3);
        *(undefined1 *)((int)DAT_003af2a8 + ze._296_4_) = 0;
      }
      CloseZipU(hz);
    }
  }
  DAT_003af288 = 0;
  if (local_474 == 0) {
    memcpy(DAT_003af29c,(void *)((int)DAT_003af28c + *DAT_003af28c),
           (uint)*(ushort *)((int)DAT_003af28c + 6) * (uint)*(ushort *)(DAT_003af28c + 1) * 2);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
    mui_fast_lsit = local_474;
    iVar5 = mui_type_file_list(iVar10,DAT_003af2a8);
    mui_fast_lsit = 1;
    if (iVar5 != 0) {
      bVar1 = true;
      memcpy(DAT_003af29c,(void *)((int)DAT_003af28c + *DAT_003af28c),
             (uint)*(ushort *)((int)DAT_003af28c + 6) * (uint)*(ushort *)(DAT_003af28c + 1) * 2);
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 6);
    }
  }
  else {
    memcpy(DAT_003af29c,(void *)((int)DAT_003af298 + *DAT_003af298),
           (uint)*(ushort *)((int)DAT_003af298 + 6) * (uint)*(ushort *)(DAT_003af298 + 1) * 2);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af298,local_45c + 1);
  }
  mui_DisplayGameSum();
  uVar7 = 0;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  uVar9 = local_450;
  if ((joy_key._0_4_ & 0x8000) != 0) goto LAB_00024188;
LAB_00023ff8:
  iVar8 = local_474;
  local_450 = uVar9;
  if (uVar7 == 0) {
    uVar7 = mui_ReadJoystick();
    if (uVar7 == 0x108) goto LAB_000242d0;
LAB_0002400c:
    if (uVar7 < 0x108) {
      if (uVar7 == 0x10) {
        if (local_474 == 0) {
          if ((int)uVar4 < 1) {
            if (iVar10 != 0) {
              iVar10 = iVar10 + -1;
              mui_type_file_list(iVar10,DAT_003af2a8);
              uVar4 = local_474;
            }
          }
          else {
            uVar4 = uVar4 + -1;
          }
        }
        else {
          iVar8 = *(int *)(m_Typetab + local_45c * 0x14 + 4);
joined_r0x00024aec:
          if (local_45c != iVar8) {
            bVar1 = true;
            mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af298,local_45c + 1);
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af298,iVar8 + 1);
            local_45c = iVar8;
          }
        }
LAB_00024a5c:
        SoundPlay(1,mui_Effect0);
      }
      else if (uVar7 < 0x11) {
        if (uVar7 == 1) {
          if (local_474 == 0) {
            shoucang(&file_info_list + DAT_003af27c * 0x404);
            mui_type_file_list(iVar10,DAT_003af2a8);
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar4 + 1);
            mui_DisplayLine_t(uVar4,uVar4,0);
            bVar1 = true;
          }
        }
        else if (uVar7 == 8) goto LAB_0002475c;
      }
      else {
        if (uVar7 == 0x40) {
          if (local_474 != 0) {
            iVar8 = *(int *)(m_Typetab + local_45c * 0x14 + 8);
            goto joined_r0x00024aec;
          }
          if ((int)uVar4 < DAT_003af394 + -1) {
            if ((iVar5 < 0) || ((int)(iVar10 + uVar4) < iVar5 + -1)) {
              uVar4 = uVar4 + 1;
            }
          }
          else if ((int)(iVar10 + uVar4) < iVar5 + -1) {
            iVar10 = iVar10 + 1;
            mui_type_file_list(iVar10,DAT_003af2a8);
          }
          goto LAB_00024a5c;
        }
        if (uVar7 == 0x80) {
          if (local_474 == 0) {
            if (iVar10 < DAT_003af394) {
              if (iVar10 == 0 && uVar4 == 0) {
                uVar4 = 0;
                iVar10 = 0;
              }
              else {
                mui_type_file_list(0,DAT_003af2a8);
                uVar4 = local_474;
                iVar10 = local_474;
              }
            }
            else {
              iVar10 = iVar10 - DAT_003af394;
              mui_type_file_list(iVar10,DAT_003af2a8);
            }
LAB_00024a00:
            SoundPlay(1,mui_Effect1);
          }
        }
        else {
          if (uVar7 != 0x20) goto LAB_00024034;
          if (local_474 == 0) {
            if ((int)(iVar10 + uVar4 + DAT_003af394) < iVar5) {
              iVar10 = iVar10 + DAT_003af394;
              mui_type_file_list(iVar10,DAT_003af2a8);
            }
            else {
              iVar8 = iVar10 + DAT_003af394;
              if (iVar8 < iVar5) {
                mui_type_file_list(iVar8,DAT_003af2a8);
                uVar4 = (iVar5 + -1) - iVar8;
                iVar10 = iVar8;
              }
            }
            goto LAB_00024a00;
          }
        }
        SoundPlay(1,mui_Effect1);
      }
    }
    else if (uVar7 == 0x2000) {
LAB_0002475c:
      if (local_474 == 0) {
        if ((AutoRestoreKey & 2) != 0) {
          m_menulog._292_4_ = local_474;
          m_menulog._296_4_ = local_45c;
          m_menulog._300_4_ = iVar10;
          m_menulog._304_4_ = uVar4;
          SaveMenuLog();
        }
        mui_run_game(&file_info_list + DAT_003af27c * 0x404);
        DAT_003af278 = iVar10;
        DAT_003af27c = uVar4;
        goto LAB_00023eb8;
      }
      uVar7 = (uint)(byte)m_Typetab[local_45c * 0x14];
      sprintf(acStack_42c,"%s/%03d/%03d.dat",root_path,uVar7,uVar7);
      DAT_003af270 = uVar7;
      hz = OpenZipU(acStack_42c,0,2);
      if (hz == 0) {
        RARCH_LOG("find %s fail!\n",acStack_42c);
      }
      else {
        RARCH_LOG("find %s ok!\n",acStack_42c);
        GetZipItemA(hz,0xffffffff,ze);
        zr = FindZipItemA(hz,"filelist.txt",1,&local_434,ze);
        if (zr == 0) {
          if (DAT_003af2a8 != (void *)0x0) {
            free(DAT_003af2a8);
          }
          DAT_003af2a8 = malloc(ze._296_4_ + 1);
          zr = UnzipItem(hz,local_434,DAT_003af2a8,0,3);
          *(undefined1 *)((int)DAT_003af2a8 + ze._296_4_) = 0;
        }
        CloseZipU(hz);
      }
      local_450 = 0;
      mui_fast_lsit = 0;
      iVar5 = mui_type_file_list(iVar10,DAT_003af2a8);
      mui_fast_lsit = 1;
      if (iVar5 != 0) {
        local_474 = 0;
        bVar1 = true;
        memcpy(DAT_003af29c,(void *)((int)DAT_003af28c + *DAT_003af28c),
               (uint)*(ushort *)((int)DAT_003af28c + 6) * (uint)*(ushort *)(DAT_003af28c + 1) * 2);
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 6);
        DAT_003af27c = -1;
        uVar4 = local_450;
      }
    }
    else if (uVar7 < 0x2001) {
      if (uVar7 == 0x400) {
LAB_00024238:
        DAT_003af26c = 0;
        SoundPlay(1,mui_Effect1);
joined_r0x00024228:
        if ((AutoRestoreKey & 2) != 0) {
          m_menulog._292_4_ = local_474;
          m_menulog._296_4_ = local_45c;
          m_menulog._300_4_ = iVar10;
          m_menulog._304_4_ = uVar4;
        }
        return;
      }
      if (uVar7 == 0x800) {
LAB_00024200:
        DAT_003af26c = 2;
        SoundPlay(1,mui_Effect1);
        goto joined_r0x00024228;
      }
    }
    else {
      if (uVar7 == 0x3000) goto LAB_000242d0;
      if (uVar7 == 0x4000) {
        if (local_474 == 0) goto code_r0x0002455c;
      }
      else if (uVar7 == 0x2100) goto LAB_000242d0;
    }
  }
  else {
    bVar1 = true;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
    uVar7 = mui_ReadJoystick();
    if (uVar7 != 0x108) goto LAB_0002400c;
LAB_000242d0:
    if (local_474 == 0) {
      DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
      while (DisplayThumbnailflag != 0) {
        usleep(1000);
      }
      pcVar3 = stpcpy(acStack_42c,root_path);
      pcVar3[0] = '/';
      iVar8 = DAT_003af27c;
      pcVar3[1] = '\0';
      strcpy(pcVar3 + 1,&file_info_list + DAT_003af27c * 0x404);
      local_32c = (&DAT_003b2320)[iVar8 * 0x101];
      pcVar3 = (char *)SeletEmuCore(acStack_42c);
      if (pcVar3 == (char *)0x0) {
        DisplayThumbnailflag = 1;
        pthread_create(&pStack_430,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
      }
      else {
        if ((AutoRestoreKey & 2) != 0) {
          m_menulog._296_4_ = local_45c;
          m_menulog._292_4_ = 0;
          m_menulog._300_4_ = iVar10;
          m_menulog._304_4_ = uVar4;
          SaveMenuLog();
        }
        strcpy(acStack_128,pcVar3);
        filelist_run_game(acStack_42c);
      }
      if (ZIP_BUF != (void *)0x0) {
        free(ZIP_BUF);
      }
      ZIP_BUF = (void *)0x0;
      ZIP_BUF_SIZE = 0;
      DAT_003af278 = iVar10;
      DAT_003af27c = uVar4;
      goto LAB_00023eb8;
    }
  }
LAB_00024034:
  if (iVar5 == DAT_003af288) {
    if (iVar10 == DAT_003af278) {
      if (local_474 != 0) {
LAB_00024420:
        uVar7 = 0;
        goto LAB_00024424;
      }
      if (uVar4 == DAT_003af27c) {
        local_464 = local_464 + 1;
        if (uVar9 == 0) {
          uVar7 = 0;
          local_474 = 0;
          goto LAB_00024424;
        }
        if ((int)local_464 < 0x65) goto LAB_00024420;
        if ((local_464 & 1) != 0) {
          uVar7 = 0;
          uVar9 = local_464 & 1;
          goto LAB_00024424;
        }
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar4 + 1);
        mui_DisplayLine_t(uVar4,uVar4,local_468);
        uVar7 = 0;
        if ((int)DAT_003af284 < 0x82) {
          local_468 = local_468 + -1;
        }
        else {
          local_468 = local_474;
        }
      }
      else {
        if (DAT_003af27c != -1) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
          mui_DisplayLine_t(DAT_003af27c,uVar4,0);
        }
        uVar7 = 0;
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar4 + 1);
        mui_DisplayLine_t(uVar4,uVar4,0);
        local_468 = 0;
        uVar9 = DAT_003af284 >> 0x1f;
        DisplayThumbnailflag = 3;
        local_464 = 0;
        DAT_003af27c = uVar4;
        DAT_003af288 = iVar5;
        mui_DisplayGameSum();
      }
      goto LAB_00024134;
    }
    if (0 < DAT_003af394) {
      iVar8 = 1;
      do {
        if (uVar4 != iVar8 + -1) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar8);
        }
        bVar1 = iVar8 < DAT_003af394;
        iVar8 = iVar8 + 1;
      } while (bVar1);
    }
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar4 + 1);
    DAT_003af278 = iVar10;
    DAT_003af27c = uVar4;
    if ((0 < DAT_003af394) && (iVar10 != iVar5)) {
      iVar8 = 0;
      do {
        iVar6 = iVar8 + 1;
        mui_DisplayLine_t(iVar8,uVar4,0);
        if (DAT_003af394 <= iVar6) break;
        iVar8 = iVar6;
      } while (iVar5 != iVar10 + iVar6);
    }
    uVar9 = DAT_003af284 >> 0x1f;
    if (local_474 == 0) {
      DisplayThumbnailflag = 3;
    }
  }
  else {
    if (0 < DAT_003af394) {
      iVar8 = 0;
      do {
        iVar8 = iVar8 + 1;
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar8);
      } while (iVar8 < DAT_003af394);
    }
    if (local_474 == 0) {
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar4 + 1);
      if ((0 < DAT_003af394) && (iVar10 != iVar5)) goto LAB_000240ac;
      uVar9 = DAT_003af284 >> 0x1f;
      DAT_003af27c = uVar4;
LAB_00024108:
      DisplayThumbnailflag = 3;
      DAT_003af278 = iVar10;
    }
    else if ((DAT_003af394 < 1) || (iVar10 == iVar5)) {
      uVar9 = DAT_003af284 >> 0x1f;
      DAT_003af278 = iVar10;
      DAT_003af27c = uVar4;
    }
    else {
LAB_000240ac:
      iVar8 = 0;
      DAT_003af27c = uVar4;
      do {
        iVar6 = iVar8 + 1;
        mui_DisplayLine_t(iVar8,uVar4,0);
        if (DAT_003af394 <= iVar6) break;
        iVar8 = iVar6;
      } while (iVar5 != iVar6 + iVar10);
      uVar9 = DAT_003af284 >> 0x1f;
      DAT_003af278 = iVar10;
      if (local_474 == 0) goto LAB_00024108;
    }
  }
  uVar7 = 0;
  local_468 = 0;
  local_464 = 0;
  DAT_003af288 = iVar5;
  mui_DisplayGameSum();
LAB_00024134:
  DAT_003af274 = 1;
  do {
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    DAT_003af274 = 0;
    do {
      mui_WaitNMI();
      bVar1 = false;
      if ((joy_key._0_4_ & 0x8000) == 0) goto LAB_00023ff8;
LAB_00024188:
      uVar2 = mui_ReadJoystick();
      if ((uVar2 & 0xffff7fff) == 0x20) goto LAB_00024200;
      if ((uVar2 & 0xffff7fff) == 0x80) goto LAB_00024238;
      uVar7 = uVar7 + 1;
      if ((uVar7 & 0xf) == 0) {
        if ((uVar7 & 0x10) == 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c)
          ;
        }
        else {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                          DAT_003af394 + 1 + DAT_003af26c);
        }
        goto LAB_00024134;
      }
LAB_00024424:
      if (bVar1) goto LAB_00024134;
    } while (DAT_003af274 == 0);
  } while( true );
code_r0x0002455c:
  uVar4 = -1;
  DAT_003af278 = local_474;
  DAT_003af27c = -1;
  local_474 = 1;
  iVar5 = 0;
  iVar10 = iVar8;
  goto LAB_00023eb8;
}
