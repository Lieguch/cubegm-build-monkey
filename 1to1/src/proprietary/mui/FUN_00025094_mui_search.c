/* ============================================================
 * mui_search   @ 0x00025094   size=5356B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

void mui_search(void)

{
  byte bVar1;
  ushort uVar2;
  ushort uVar3;
  int iVar4;
  int *piVar5;
  uint uVar6;
  int iVar7;
  char *pcVar8;
  int *piVar9;
  void *pvVar10;
  int iVar11;
  undefined1 *puVar12;
  undefined4 *puVar13;
  undefined4 uVar14;
  int iVar15;
  undefined4 uVar16;
  int iVar17;
  uint uVar18;
  uint uVar19;
  int iVar20;
  int unaff_r11;
  int iVar21;
  bool bVar22;
  uint local_474;
  uint local_470;
  uint local_46c;
  uint local_460;
  int local_45c;
  uint local_458;
  int local_454;
  pthread_t local_430;
  char acStack_42c [256];
  undefined4 local_32c;
  char acStack_128 [260];
  
  m_menulog._0_4_ = DAT_003af26c;
  local_46c = m_menulog._324_4_;
  uVar19 = 0;
  local_460 = 0;
  local_45c = 0;
  local_474 = 0;
  local_458 = 0;
  DAT_003af278 = m_menulog._328_4_;
  DAT_003af27c = m_menulog._332_4_;
  uVar18 = m_menulog._332_4_;
  iVar20 = m_menulog._328_4_;
LAB_00025144:
  while ((DisplayThumbnailflag & 8) != 0) {
    usleep(1000);
  }
  DisplayThumbnailflag = 1;
  if (m_search == (int *)0x0) {
    piVar9 = calloc(0x18,1);
    m_search = piVar9;
    pvVar10 = malloc(100);
    *piVar9 = (int)pvVar10;
    memcpy(pvVar10,m_menulog + 0x150,100);
    piVar9[2] = m_menulog._436_4_;
  }
  if (DAT_003af28c == 0) {
    mui_LoadUIResource(&DAT_003af28c,"menu.raw");
  }
  if (DAT_003af290 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af290,"search.raw");
  }
  if (DAT_003af2ac == (void *)0x0) {
    sprintf(acStack_42c,"%s/root.dat",root_path);
    hz = OpenZipU(acStack_42c,0,2);
    if (hz == 0) {
      RARCH_LOG("find %s fail!\n",acStack_42c);
    }
    else {
      RARCH_LOG("find %s ok!\n",acStack_42c);
      GetZipItemA(hz,0xffffffff,ze);
      zr = FindZipItemA(hz,"fileinfo.txt",1,&local_430,ze);
      if (zr == 0) {
        DAT_003af2ac = malloc(ze._296_4_ + 1);
        zr = UnzipItem(hz,local_430,DAT_003af2ac,0,3);
        *(undefined1 *)((int)DAT_003af2ac + ze._296_4_) = 0;
      }
      CloseZipU(hz);
    }
  }
  piVar5 = m_search;
  piVar9 = DAT_003af290;
  uVar2 = *(ushort *)(DAT_003af290 + 1);
  uVar3 = *(ushort *)((int)DAT_003af290 + 6);
  m_search[3] = DAT_003af6c8 + 2;
  memcpy(DAT_003af29c,(void *)((int)piVar9 + *piVar9),(uint)uVar3 * (uint)uVar2 * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
  uVar14 = m_menulog._440_4_;
  local_454 = m_menulog._440_4_;
  if (piVar5[2] != 0) {
    unaff_r11 = mui_search_file_list(iVar20,0);
  }
  if (local_46c == 0) {
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,0x28);
    DAT_003af27c = 0xffffffff;
  }
  else {
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,uVar14 + 1);
  }
  local_470 = 0;
  DAT_003af288 = 0;
  mui_DisplayGameSum();
  mui_DisplayInputBuffer();
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
  if ((joy_key._0_4_ & 0x8000) != 0) goto LAB_00025514;
LAB_000252cc:
  if (local_470 == 0) {
    uVar6 = mui_ReadJoystick();
    bVar22 = false;
    if (uVar6 == 0x108) goto LAB_00025688;
LAB_000252e8:
    piVar9 = m_search;
    if (uVar6 < 0x108 || bVar22) {
      if (uVar6 == 0x10) {
        if (local_46c == 0) {
          if ((int)uVar18 < 1) {
            if (iVar20 != 0) {
              iVar20 = iVar20 + -1;
              mui_search_file_list(iVar20,1);
              uVar18 = local_46c;
            }
          }
          else {
            uVar18 = uVar18 - 1;
          }
        }
        else if (local_454 != *(int *)(m_movetab + local_454 * 0x14 + 4)) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
          local_454 = *(int *)(m_movetab + local_454 * 0x14 + 4);
LAB_00025b78:
          uVar19 = 1;
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
        }
      }
      else {
        if (uVar6 < 0x11) {
          if (uVar6 == 1) {
            if (local_46c == 0) {
              local_470 = local_46c;
              shoucang(&file_info_list + DAT_003af27c * 0x404);
              mui_search_file_list(iVar20,1);
              mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar18 + 1);
              mui_DisplayLine_t(uVar18,uVar18,0);
              uVar19 = 1;
              goto LAB_00025318;
            }
            goto LAB_00025310;
          }
          if (uVar6 == 8) {
LAB_00025e4c:
            if (local_46c != 0) {
              bVar1 = m_movetab[local_454 * 0x14];
              if (bVar1 == 1) {
                local_470 = m_search[2];
                if (local_470 == 0) goto LAB_00025318;
                iVar20 = *m_search;
                m_search[2] = local_470 - 1;
                *(undefined1 *)(iVar20 + (local_470 - 1)) = 0;
              }
              else {
                if (bVar1 == 2) {
                  unaff_r11 = mui_search_file_list(iVar20,0);
                  local_470 = 0;
                  goto LAB_00025318;
                }
                if (bVar1 == 3) {
                  unaff_r11 = 0;
                  uVar19 = 1;
                  local_470 = 0;
                  puVar12 = (undefined1 *)*m_search;
                  m_search[2] = 0;
                  *puVar12 = 0;
                  mui_DisplayInputBuffer();
                  goto LAB_00025318;
                }
                if (bVar1 < 6 || DAT_003af6d0 <= m_search[3]) {
                  local_470 = 0;
                  goto LAB_00025318;
                }
                iVar17 = m_search[2];
                iVar20 = *m_search;
                m_search[2] = iVar17 + 1;
                *(byte *)(iVar20 + iVar17) = bVar1;
                *(undefined1 *)(*piVar9 + piVar9[2]) = 0;
              }
              uVar19 = 1;
              local_470 = 0;
              iVar20 = 0;
              mui_DisplayInputBuffer();
              unaff_r11 = mui_search_file_list(0,0);
              goto LAB_00025318;
            }
            if ((AutoRestoreKey & 0x10) != 0) {
              m_menulog._324_4_ = local_46c;
              m_menulog._328_4_ = iVar20;
              m_menulog._332_4_ = uVar18;
              memcpy(m_menulog + 0x150,(void *)*m_search,100);
              m_menulog._436_4_ = piVar9[2];
              m_menulog._440_4_ = local_454;
              SaveMenuLog();
            }
            mui_run_game(&file_info_list + DAT_003af27c * 0x404);
            DAT_003af278 = iVar20;
            DAT_003af27c = uVar18;
            goto LAB_00025144;
          }
          goto LAB_00025310;
        }
        if (uVar6 == 0x40) {
          if (local_46c == 0) {
            if ((int)uVar18 < DAT_003af394 + -1) {
              if ((unaff_r11 < 0) || ((int)(iVar20 + uVar18) < unaff_r11 + -1)) {
                uVar18 = uVar18 + 1;
              }
            }
            else if ((int)(iVar20 + uVar18) < unaff_r11 + -1) {
              iVar20 = iVar20 + 1;
              mui_search_file_list(iVar20,1);
            }
          }
          else if (local_454 != *(int *)(m_movetab + local_454 * 0x14 + 8)) {
            mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
            local_454 = *(int *)(m_movetab + local_454 * 0x14 + 8);
            goto LAB_00025b78;
          }
        }
        else if (uVar6 == 0x80) {
          if (local_46c == 0) {
            if (iVar20 < DAT_003af394) {
              if (iVar20 == 0 && uVar18 == 0) {
                uVar19 = 1;
                uVar18 = 0xffffffff;
                mui_Undisplay(DAT_003af37c,DAT_003af380,DAT_003af384,DAT_003af388);
                mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,1);
                mui_DisplayLine_t(0,0xffffffff,0);
                mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
                local_46c = 1;
                mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,0x28);
                iVar20 = 0;
              }
              else {
                mui_search_file_list(0,1);
                iVar20 = 0;
                uVar18 = local_46c;
              }
            }
            else {
              iVar20 = iVar20 - DAT_003af394;
              mui_search_file_list(iVar20,1);
            }
            SoundPlay(1,mui_Effect1);
            local_470 = 0;
            goto LAB_00025318;
          }
          if (local_454 != *(int *)(m_movetab + local_454 * 0x14 + 0xc)) {
            if (*(int *)(m_movetab + local_454 * 0x14 + 0xc) < 0) {
joined_r0x00026390:
              if (unaff_r11 != 0) {
                local_46c = 0;
                mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
                mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,0x28);
                DAT_003af27c = 0xffffffff;
                uVar18 = 0;
              }
            }
            else {
              uVar19 = 1;
              mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
              local_454 = *(int *)(m_movetab + local_454 * 0x14 + 0xc);
              mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
            }
          }
        }
        else {
          if (uVar6 != 0x20) goto LAB_00025310;
          if (local_46c == 0) {
            if ((int)(iVar20 + uVar18 + DAT_003af394) < unaff_r11) {
              iVar17 = iVar20 + DAT_003af394;
              mui_search_file_list(iVar17,1);
            }
            else {
              iVar17 = iVar20 + DAT_003af394;
              if (iVar17 < unaff_r11) {
                uVar18 = (unaff_r11 + -1) - iVar17;
                local_46c = 0;
                mui_search_file_list(iVar17,1);
              }
              else {
                local_46c = 1;
                uVar19 = 1;
                mui_Undisplay(DAT_003af37c,DAT_003af380,DAT_003af384,DAT_003af388);
                mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar18 + 1);
                mui_DisplayLine_t(uVar18,0xffffffff,0);
                uVar18 = 0xffffffff;
                mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
                mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,0x28);
                iVar17 = iVar20;
              }
            }
            SoundPlay(1,mui_Effect1);
            local_470 = 0;
            iVar20 = iVar17;
            goto LAB_00025318;
          }
          if (local_454 != *(int *)(m_movetab + local_454 * 0x14 + 0x10)) {
            if (*(int *)(m_movetab + local_454 * 0x14 + 0x10) < 0) goto joined_r0x00026390;
            uVar19 = 1;
            mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
            local_454 = *(int *)(m_movetab + local_454 * 0x14 + 0x10);
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
          }
        }
      }
      local_470 = 0;
      SoundPlay(1,mui_Effect0);
      goto LAB_00025318;
    }
    if (uVar6 == 0x1000) {
      uVar19 = 1;
      local_46c = 1;
      local_470 = 0;
      unaff_r11 = 0;
      uVar18 = 0xffffffff;
      puVar12 = (undefined1 *)*m_search;
      m_search[2] = 0;
      *puVar12 = 0;
      mui_DisplayInputBuffer();
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
      mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,0x28);
      goto LAB_00025318;
    }
    if (uVar6 < 0x1001) {
      if (uVar6 == 0x400) {
LAB_00025a84:
        DAT_003af26c = 3;
        SoundPlay(1,mui_Effect1);
        piVar9 = m_search;
        if ((AutoRestoreKey & 0x10) != 0) {
          m_menulog._324_4_ = local_46c;
          m_menulog._328_4_ = iVar20;
          m_menulog._332_4_ = uVar18;
          memcpy(m_menulog + 0x150,(void *)*m_search,100);
          m_menulog._436_4_ = piVar9[2];
          m_menulog._440_4_ = local_454;
        }
        if ((void *)*piVar9 != (void *)0x0) {
          free((void *)*piVar9);
        }
        free(piVar9);
        m_search = (int *)0x0;
        return;
      }
      if (uVar6 == 0x800) {
        local_470 = 0;
        goto LAB_000255bc;
      }
    }
    else {
      if (uVar6 == 0x2100) goto LAB_00025688;
      if (uVar6 == 0x4000) {
        local_470 = m_search[2];
        if (local_470 != 0) {
          iVar20 = *m_search;
          m_search[2] = local_470 - 1;
          *(undefined1 *)(iVar20 + (local_470 - 1)) = 0;
          mui_DisplayInputBuffer();
          unaff_r11 = mui_search_file_list(0,0);
          if (local_46c == 0 && unaff_r11 == 0) {
            uVar19 = 1;
            local_46c = 1;
            uVar18 = 0xffffffff;
            mui_Undisplay(DAT_003af37c,DAT_003af380,DAT_003af384,DAT_003af388);
            mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,1);
            mui_DisplayLine_t(0,0xffffffff,0);
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
            mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,0x28);
            iVar20 = 0;
            unaff_r11 = 0;
            local_470 = 0;
          }
          else {
            iVar20 = 0;
            uVar19 = 1;
            local_470 = 0;
          }
        }
        goto LAB_00025318;
      }
      if (uVar6 == 0x2000) goto LAB_00025e4c;
    }
  }
  else {
    uVar19 = 1;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c);
    uVar6 = mui_ReadJoystick();
    bVar22 = uVar6 == 0x108;
    if (!bVar22) goto LAB_000252e8;
LAB_00025688:
    if (local_46c == 0) goto code_r0x00025694;
  }
LAB_00025310:
  local_470 = 0;
LAB_00025318:
  if (unaff_r11 == DAT_003af288) {
    if (iVar20 == DAT_003af278) {
      uVar6 = local_460;
      if (local_46c == 0) {
        if (uVar18 == DAT_003af27c) {
          local_458 = local_458 + 1;
          if (((local_460 != 0) && (100 < (int)local_458)) &&
             (uVar6 = local_458 & 1, (local_458 & 1) == 0)) {
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar18 + 1);
            mui_DisplayLine_t(uVar18,uVar18,local_45c);
            uVar19 = local_460;
            if ((int)DAT_003af284 < 0x82) {
              local_45c = local_45c + -1;
              uVar6 = local_460;
            }
            else {
              local_45c = 0;
              uVar6 = local_460;
            }
          }
        }
        else {
          if (DAT_003af27c != 0xffffffff) {
            mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af27c + 1);
            mui_DisplayLine_t(DAT_003af27c,uVar18,0);
          }
          local_45c = 0;
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar18 + 1);
          mui_DisplayLine_t(uVar18,uVar18,0);
          local_458 = 0;
          uVar6 = DAT_003af284 >> 0x1f;
          DAT_003af27c = uVar18;
          DAT_003af288 = unaff_r11;
          mui_DisplayGameSum();
          uVar19 = 1;
        }
      }
      goto LAB_000253f4;
    }
    if (0 < DAT_003af394) {
      iVar17 = 1;
      do {
        if (uVar18 != iVar17 - 1U) {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar17);
        }
        bVar22 = iVar17 < DAT_003af394;
        iVar17 = iVar17 + 1;
      } while (bVar22);
    }
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar18 + 1);
    DAT_003af278 = iVar20;
    DAT_003af27c = uVar18;
    if ((0 < DAT_003af394) && (iVar20 != unaff_r11)) {
      iVar17 = 0;
      do {
        iVar15 = iVar17 + 1;
        mui_DisplayLine_t(iVar17,uVar18,0);
        if (DAT_003af394 <= iVar15) break;
        iVar17 = iVar15;
      } while (unaff_r11 != iVar15 + iVar20);
    }
  }
  else {
    if (0 < DAT_003af394) {
      iVar17 = 0;
      do {
        iVar17 = iVar17 + 1;
        mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,iVar17);
      } while (iVar17 < DAT_003af394);
    }
    if (local_46c == 0) {
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar18 + 1);
    }
    DAT_003af278 = iVar20;
    DAT_003af27c = uVar18;
    if ((0 < DAT_003af394) && (iVar20 != unaff_r11)) {
      iVar17 = 0;
      do {
        iVar15 = iVar17 + 1;
        mui_DisplayLine_t(iVar17,uVar18,0);
        if (DAT_003af394 <= iVar15) break;
        iVar17 = iVar15;
      } while (unaff_r11 != iVar15 + iVar20);
    }
  }
  local_45c = 0;
  local_458 = 0;
  uVar6 = DAT_003af284 >> 0x1f;
  DAT_003af288 = unaff_r11;
  mui_DisplayGameSum();
  uVar19 = 1;
LAB_000253f4:
  local_460 = uVar6;
  iVar17 = DAT_003af6cc;
  local_474 = local_474 + 1;
  if ((local_474 & 7) != 0) goto LAB_00025578;
  iVar15 = m_search[3];
  OutRect._12_4_ = DAT_003af6cc;
  OutRect._20_4_ = DAT_003af6d4;
  OutRect._16_4_ = iVar15 + 6;
  OutRect._8_4_ = iVar15;
  if (0 < DAT_003af6d4 - DAT_003af6cc) {
    iVar11 = (DAT_003af6d4 - DAT_003af6cc) + DAT_003af6cc;
    iVar21 = DAT_003af6cc;
    do {
      pvVar10 = DAT_003af29c;
      iVar7 = iVar21 * DAT_003af2a0 * 2 + iVar15 * 2;
      iVar4 = iVar21 * (uint)*(ushort *)(DAT_003af290 + 1) * 2;
      iVar21 = iVar21 + 1;
      puVar13 = (undefined4 *)((int)DAT_003af290 + iVar4 + iVar15 * 2 + *DAT_003af290);
      uVar16 = puVar13[1];
      uVar14 = puVar13[2];
      *(undefined4 *)((int)DAT_003af29c + iVar7) = *puVar13;
      *(undefined4 *)((int)pvVar10 + iVar7 + 4) = uVar16;
      *(undefined4 *)((int)pvVar10 + iVar7 + 8) = uVar14;
    } while (iVar11 != iVar21);
  }
  if ((local_474 & 0x10) != 0) {
    mui_outputxy_t(DAT_003af29c,iVar15 + 2,iVar17,(undefined1)DAT_003af6e0,DAT_003af6e4,
                   &DAT_003af6e8);
  }
LAB_000254c0:
  DAT_003af274 = DAT_003af274 | 1;
  do {
    ForceFlashCount = 0;
    dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
    DAT_003af274 = 0;
    do {
      mui_WaitNMI();
      uVar19 = 0;
      if ((joy_key._0_4_ & 0x8000) == 0) goto LAB_000252cc;
LAB_00025514:
      uVar6 = mui_ReadJoystick();
      if ((uVar6 & 0xffff7fff) == 0x20) goto LAB_000255bc;
      if ((uVar6 & 0xffff7fff) == 0x80) goto LAB_00025a84;
      local_470 = local_470 + 1;
      if ((local_470 & 0xf) == 0) {
        if ((local_470 & 0x10) == 0) {
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,DAT_003af394 + 1 + DAT_003af26c)
          ;
        }
        else {
          mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,
                          DAT_003af394 + 1 + DAT_003af26c);
        }
        goto LAB_000254c0;
      }
LAB_00025578:
      if (uVar19 != 0) goto LAB_000254c0;
    } while (DAT_003af274 == 0);
  } while( true );
code_r0x00025694:
  DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
  while (DisplayThumbnailflag != 0) {
    usleep(1000);
  }
  pcVar8 = stpcpy(acStack_42c,root_path);
  pcVar8[0] = '/';
  uVar6 = DAT_003af27c;
  pcVar8[1] = '\0';
  strcpy(pcVar8 + 1,&file_info_list + DAT_003af27c * 0x404);
  local_32c = (&DAT_003b2320)[uVar6 * 0x101];
  pcVar8 = (char *)SeletEmuCore(acStack_42c);
  piVar9 = m_search;
  if (pcVar8 == (char *)0x0) {
    DisplayThumbnailflag = 1;
    pthread_create(&local_430,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
  }
  else {
    if ((AutoRestoreKey & 0x10) != 0) {
      m_menulog._324_4_ = 0;
      m_menulog._328_4_ = iVar20;
      m_menulog._332_4_ = uVar18;
      memcpy(m_menulog + 0x150,(void *)*m_search,100);
      m_menulog._436_4_ = piVar9[2];
      m_menulog._440_4_ = local_454;
      SaveMenuLog();
    }
    strcpy(acStack_128,pcVar8);
    filelist_run_game(acStack_42c);
  }
  if (ZIP_BUF != (void *)0x0) {
    free(ZIP_BUF);
  }
  ZIP_BUF = (void *)0x0;
  ZIP_BUF_SIZE = 0;
  DAT_003af278 = iVar20;
  DAT_003af27c = uVar18;
  goto LAB_00025144;
LAB_000255bc:
  if (local_46c == 0) {
    mui_Undisplay(DAT_003af37c,DAT_003af380,DAT_003af384,DAT_003af388);
    mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af28c,uVar18 + 1);
    mui_DisplayLine_t(uVar18,0xffffffff,0);
    uVar18 = 0xffffffff;
    local_46c = 1;
    mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,local_454 + 1);
    mui_UnDispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af290,0x28);
  }
  goto LAB_00025318;
}
