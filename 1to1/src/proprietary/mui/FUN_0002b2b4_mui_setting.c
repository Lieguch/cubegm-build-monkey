/* ============================================================
 * mui_setting   @ 0x0002b2b4   size=6500B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_setting(void)

{
  gh_uint uVar1;
  gh_u4 uVar2;
  FILE *pFVar3;
  size_t sVar4;
  char *pcVar5;
  int iVar6;
  int iVar7;
  gh_u4 uVar8;
  int iVar9;
  int iVar10;
  int iVar11;
  int *piVar12;
  int *piVar13;
  int iVar14;
  gh_u4 **puVar15;
  int local_728;
  int local_724;
  char acStack_6d0 [100];
  char acStack_66c [256];
  int local_56c [80];
  char acStack_42c [256];
  gh_u4 local_32c;
  char local_128 [260];
  
  local_724 = (m_menulog_blob)._272_4_;
  (m_menulog_blob)._0_4_ = DAT_003af26c;
  local_728 = m_ui;
  DAT_003af27c = (m_menulog_blob)._276_4_;
  if (0 < DAT_003af30c) {
    iVar11 = DAT_003af6f4;
    piVar13 = local_56c;
    do {
      piVar13[1] = iVar11;
      iVar9 = DAT_003af6fc + iVar11;
      *piVar13 = DAT_003af6f0;
      piVar12 = piVar13 + 4;
      piVar13[2] = DAT_003af6f0 + DAT_003af6f8;
      iVar11 = iVar11 + DAT_003af6fc + 10;
      piVar13[3] = iVar9;
      piVar13 = piVar12;
    } while (local_56c + DAT_003af30c * 4 != piVar12);
  }
  while ((DisplayThumbnailflag & 8) != 0) {
    usleep(1000);
  }
  DisplayThumbnailflag = 1;
LAB_0002b3b4:
  if (DAT_003af294 == (int *)0x0) {
    mui_LoadUIResource(&DAT_003af294,"setting.raw");
  }
  iVar11 = 0;
  memcpy(DAT_003af29c,(void *)((int)DAT_003af294 + *DAT_003af294),
         (gh_uint)*(gh_ushort *)((int)DAT_003af294 + 6) * (gh_uint)*(gh_ushort *)(DAT_003af294 + 1) * 2);
  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af294);
  OutRect._16_4_ = 0x500;
  OutRect._20_4_ = 0x2d0;
  OutRect._8_4_ = 0;
  OutRect._12_4_ = 0;
  if (0 < DAT_003af30c) {
    puVar15 = &DAT_003af2b8;
    piVar13 = local_56c;
    do {
      puVar15 = puVar15 + 1;
      mui_outputxy_t(DAT_003af29c,local_56c[iVar11 * 4] + 8,piVar13[1] + 6,(gh_u1)DAT_003af700,
                     DAT_003af704,(gh_byte *)*(gh_byte *)puVar15);
      if (m_ui == iVar11) {
        mui_outputxy_t(DAT_003af29c,local_56c[iVar11 * 4] + 0x120,piVar13[1] + -6,
                       (gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)(gh_byte *)&DAT_003af708);
      }
      else {
        mui_outputxy_t(DAT_003af29c,local_56c[iVar11 * 4] + 0x120,piVar13[1] + -10,
                       (gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)&DAT_003af70f);
      }
      iVar11 = iVar11 + 1;
      piVar13 = piVar13 + 4;
    } while (iVar11 < DAT_003af30c);
  }
  iVar11 = -1;
  DAT_003af27c = -1;
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  mui_ReadJoystick();
  diff_prev = 0;
  m_time0 = GetTicks();
LAB_0002b7a8:
  iVar9 = local_724;
  uVar1 = mui_ReadJoystick();
  if (uVar1 == 0x400) {
    DAT_003af26c = 0;
    return;
  }
  if (uVar1 < 0x401) {
    if (uVar1 == 0x20) {
      if (local_724 == 0) {
        if ((int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 6) < DAT_003af6f0) {
          local_724 = 1;
          DAT_003af27c = -1;
          iVar11 = iVar9;
        }
      }
      else if (DAT_003af6f0 < (int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 6)) {
        iVar11 = -1;
        local_724 = 0;
      }
      SoundPlay(1,(int *)mui_Effect1);
      goto LAB_0002b5d4;
    }
    if (uVar1 < 0x21) {
      if (uVar1 == 0x10) {
        SoundPlay(1,(int *)mui_Effect0);
        if ((local_724 != 0) && (iVar11 != 0)) {
          iVar11 = iVar11 + -1;
        }
        goto LAB_0002b5d4;
      }
LAB_0002b800:
      if (iVar11 == DAT_003af27c) goto LAB_0002b810;
LAB_0002b5dc:
      if (local_728 == m_ui) {
LAB_0002b5f4:
        if (-1 < DAT_003af27c) {
          UnDrawSelectBar(local_56c + DAT_003af27c * 4,(int)DAT_003af294,0);
          mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af294);
          mui_outputxy_t(DAT_003af29c,local_56c[DAT_003af27c * 4] + 8,
                         local_56c[DAT_003af27c * 4 + 1] + 6,(gh_u1)DAT_003af700,DAT_003af704,
                         (gh_byte *)(&m_ui)[DAT_003af27c + 0x16]);
          if (DAT_003af27c == m_ui) {
            puVar15 = (gh_u4 **)&DAT_003af708;
            iVar9 = local_56c[DAT_003af27c * 4];
            iVar10 = local_56c[DAT_003af27c * 4 + 1] + -6;
          }
          else {
            puVar15 = (gh_u4 **)&DAT_003af70f;
            iVar9 = local_56c[DAT_003af27c * 4];
            iVar10 = local_56c[DAT_003af27c * 4 + 1] + -10;
          }
          mui_outputxy_t(DAT_003af29c,iVar9 + 0x120,iVar10,(gh_u1)DAT_003af71c,DAT_003af718,
                         (gh_byte *)puVar15);
        }
        iVar9 = iVar11;
        if (-1 < iVar11) {
          DrawSelectBar(local_56c + iVar11 * 4);
          mui_outputxy_t(DAT_003af29c,local_56c[iVar11 * 4] + 8,local_56c[iVar11 * 4 + 1] + 6,
                         (gh_u1)DAT_003af700,DAT_003af704,(gh_byte *)(&m_ui)[iVar11 + 0x16]);
          if (iVar11 == m_ui) {
            mui_outputxy_t(DAT_003af29c,local_56c[iVar11 * 4] + 0x120,local_56c[iVar11 * 4 + 1] + -6
                           ,(gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)(gh_byte *)&DAT_003af708);
          }
          else {
            mui_outputxy_t(DAT_003af29c,local_56c[iVar11 * 4] + 0x120,
                           local_56c[iVar11 * 4 + 1] + -10,(gh_u1)DAT_003af71c,DAT_003af718,
                           (gh_byte *)&DAT_003af70f);
          }
        }
      }
      else {
LAB_0002b828:
        m_ui = local_728;
        mui_LoadConfig();
        mui_InitFont();
        if (DAT_003af28c != 0) {
          mui_LoadUIResource(&DAT_003af28c,"menu.raw");
        }
        if (DAT_003af294 != (int *)0x0) {
          mui_LoadUIResource(&DAT_003af294,"setting.raw");
        }
        if (DAT_003af290 != 0) {
          mui_LoadUIResource(&DAT_003af290,"search.raw");
        }
        if (DAT_003af298 != 0) {
          mui_LoadUIResource(&DAT_003af298,"type.raw");
        }
        if (0 < DAT_003af30c) {
          iVar9 = DAT_003af6f4;
          piVar13 = local_56c;
          do {
            piVar13[1] = iVar9;
            iVar10 = DAT_003af6fc + iVar9;
            *piVar13 = DAT_003af6f0;
            piVar12 = piVar13 + 4;
            piVar13[2] = DAT_003af6f0 + DAT_003af6f8;
            iVar9 = iVar9 + DAT_003af6fc + 10;
            piVar13[3] = iVar10;
            piVar13 = piVar12;
          } while (local_56c + DAT_003af30c * 4 != piVar12);
        }
        memcpy(DAT_003af29c,(void *)((int)DAT_003af294 + *DAT_003af294),
               (gh_uint)*(gh_ushort *)((int)DAT_003af294 + 6) * (gh_uint)*(gh_ushort *)(DAT_003af294 + 1) * 2);
        mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af294);
        if (0 < DAT_003af30c) {
          puVar15 = &DAT_003af2b8;
          iVar9 = 0;
          piVar13 = local_56c;
          do {
            puVar15 = puVar15 + 1;
            mui_outputxy_t(DAT_003af29c,local_56c[iVar9 * 4] + 8,piVar13[1] + 6,
                           (gh_u1)DAT_003af700,DAT_003af704,(gh_byte *)*(gh_byte *)puVar15);
            if (m_ui == iVar9) {
              mui_outputxy_t(DAT_003af29c,local_56c[iVar9 * 4] + 0x120,piVar13[1] + -6,
                             (gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)(gh_byte *)&DAT_003af708);
            }
            else {
              mui_outputxy_t(DAT_003af29c,local_56c[iVar9 * 4] + 0x120,piVar13[1] + -10,
                             (gh_u1)DAT_003af71c,DAT_003af718,(gh_byte *)&DAT_003af70f);
            }
            iVar9 = iVar9 + 1;
            piVar13 = piVar13 + 4;
          } while (iVar9 < DAT_003af30c);
        }
        DAT_003af27c = -1;
        uVar2 = (gh_u4)GetWorkPath();
        sprintf(acStack_6d0,"%s/setting.xml",uVar2);
        pFVar3 = fopen(acStack_6d0,"r");
        if (pFVar3 == (FILE *)0x0) {
          RARCH_LOG("open setting.xml fail!\n");
          tree = 0;
        }
        else {
          tree = mxmlLoadFile(0,pFVar3);
          fclose(pFVar3);
          if (tree != 0) {
            iVar9 = mxmlFindElement(tree,tree,"config",0,0,1);
            if (iVar9 != 0) {
              mxmlElementSetAttr(iVar9,"language",*(gh_u4 *)(number + m_ui * 4));
            }
            if (tree != 0) {
              pFVar3 = fopen(acStack_6d0,"wb");
              mxmlSaveFile(tree,pFVar3,0);
              fflush(pFVar3);
              iVar9 = fileno(pFVar3);
              fsync(iVar9);
              fclose(pFVar3);
              mxmlDelete(tree);
              tree = 0;
            }
          }
        }
        iVar9 = DAT_003af27c;
        if (iVar11 != DAT_003af27c) goto LAB_0002b5f4;
      }
      DAT_003af27c = iVar9;
      DAT_003af274 = 1;
LAB_0002b778:
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      DAT_003af274 = 0;
      goto LAB_0002b7a4;
    }
    if (uVar1 == 0x40) {
      SoundPlay(1,(int *)mui_Effect0);
      iVar9 = (m_menulog_blob)._8_4_;
      uVar2 = DAT_003af394;
      if (local_724 != 0) {
        if (iVar11 < DAT_003af30c + -1) {
          iVar11 = iVar11 + 1;
        }
        goto LAB_0002b5d4;
      }
      DAT_003af27c = (m_menulog_blob)._12_4_;
      DAT_003af394 = DAT_003af740;
      DAT_003af278 = (m_menulog_blob)._8_4_;
      strcpy(acStack_66c,root_path);
      sVar4 = strlen(root_path);
      pcVar5 = stpcpy(root_path + sVar4,(char *)&DAT_003af748);
      if (m_menulog[0x10] == '\0') {
        memcpy(path,root_path,(size_t)(pcVar5 + -0x3e1397));
      }
      else {
        strcpy(path,m_menulog + 0x10);
      }
      RARCH_LOG("mui_file_list path:%s\n",path);
      iVar10 = -1;
      iVar11 = (m_menulog_blob)._4_4_;
LAB_0002be88:
      if (DAT_003af294 == (int *)0x0) {
        mui_LoadUIResource(&DAT_003af294,"setting.raw");
      }
      memcpy(DAT_003af29c,(void *)((int)DAT_003af294 + *DAT_003af294),
             (gh_uint)*(gh_ushort *)((int)DAT_003af294 + 6) * (gh_uint)*(gh_ushort *)(DAT_003af294 + 1) * 2);
      mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af294,2);
      iVar6 = dir_serial_list(iVar9,&DAT_002dd860);
      DisplayPage_list(iVar9,iVar10,iVar6);
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      mui_ReadJoystick();
      diff_prev = 0;
      m_time0 = GetTicks();
LAB_0002c008:
      uVar1 = mui_ReadJoystick();
      iVar14 = iVar9;
      if (uVar1 == 0x80) {
        SoundPlay(1,(int *)mui_Effect1);
        iVar7 = DAT_003af27c;
        iVar14 = DAT_003af278;
        if (iVar11 == 0) {
          if ((int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 10) <= DAT_003af720) goto LAB_0002c094;
          iVar11 = 1;
          iVar6 = dir_serial_list(DAT_003af278,&DAT_002dd860);
        }
        else if (iVar9 < DAT_003af394) {
          if (iVar10 + iVar9 == 0) {
            iVar7 = iVar10;
            iVar14 = iVar9;
            if ((int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 10) < DAT_003af720) {
              iVar7 = -1;
              iVar11 = 0;
              DAT_003af278 = iVar9;
              DAT_003af27c = iVar10;
            }
          }
          else {
            iVar7 = 0;
            iVar14 = 0;
          }
          iVar6 = dir_serial_list(iVar14,&DAT_002dd860);
        }
        else {
          iVar14 = iVar9 - DAT_003af394;
          iVar6 = dir_serial_list(iVar14,&DAT_002dd860);
          iVar7 = iVar10;
        }
      }
      else {
        if (0x80 < uVar1) {
          if (uVar1 == 0x2000) {
LAB_0002c500:
            if (iVar11 == 0) goto LAB_0002c094;
            iVar14 = iVar10 * 0x404;
            if ((&DAT_003b2320)[iVar10 * 0x101] == 4) {
              if ((((&file_info_list)[iVar14] == '.') && (*(char *)(iVar14 + 0x3b2221) == '.')) &&
                 (*(char *)(iVar14 + 0x3b2222) == '\0')) {
                RARCH_LOG(&DAT_002dd878,path);
                iVar14 = strcmp(path,root_path);
                if (iVar14 == 0) goto LAB_0002c094;
                sVar4 = strlen(path);
                m_menulog[sVar4 + 0x1bb] = 0;
                myStrrstr(path,(char *)&DAT_002dd64c);
                RARCH_LOG(&DAT_002dd878,path);
                iVar6 = dir_serial_list(0,&DAT_002dd860);
                iVar7 = 0;
                iVar14 = 0;
              }
              else {
                sVar4 = strlen(path);
                path[sVar4] = 0x2f;
                strcpy(path + sVar4 + 1,&file_info_list + iVar14);
                iVar6 = dir_serial_list(0,&DAT_002dd860);
                iVar7 = 0;
                iVar14 = 0;
              }
              goto LAB_0002bfb4;
            }
            sprintf(acStack_42c,"%s/%s",path,&file_info_list + iVar14);
            local_32c = (&DAT_003b2320)[iVar10 * 0x101];
            local_128[0] = '\0';
            SaveMenuLog();
            filelist_run_game(acStack_42c);
            DAT_003af278 = iVar9;
            DAT_003af27c = iVar10;
            goto LAB_0002be88;
          }
          if (uVar1 < 0x2001) {
            if (uVar1 == 0x108) goto LAB_0002c1dc;
          }
          else if (uVar1 == 0x2100) {
LAB_0002c1dc:
            if ((iVar11 != 0) && ((&DAT_003b2320)[iVar10 * 0x101] != 4)) goto code_r0x0002c204;
          }
          else if ((uVar1 == 0x4000) && (iVar11 != 0)) {
            iVar7 = strcmp(path,root_path);
            if (iVar7 == 0) {
              iVar11 = 0;
              iVar7 = -1;
              DAT_003af278 = iVar9;
              DAT_003af27c = iVar10;
            }
            else {
              sVar4 = strlen(path);
              m_menulog[sVar4 + 0x1bb] = 0;
              myStrrstr(path,(char *)&DAT_002dd64c);
              iVar6 = dir_serial_list(0,&DAT_002dd860);
              iVar7 = 0;
              iVar14 = 0;
            }
            goto LAB_0002bfb4;
          }
LAB_0002c094:
          if (DAT_003af274 != 0) goto LAB_0002bfc4;
          goto LAB_0002c004;
        }
        if (uVar1 == 0x10) {
          SoundPlay(1,(int *)mui_Effect0);
          if (iVar11 != 0) {
            if (iVar10 < 1) {
              if (iVar9 == 0) goto LAB_0002c094;
              iVar14 = iVar9 + -1;
              iVar6 = dir_serial_list(iVar14,&DAT_002dd860);
              iVar7 = 0;
            }
            else {
              iVar7 = iVar10 + -1;
            }
            goto LAB_0002bfb4;
          }
          DAT_003af394 = uVar2;
          strcpy(root_path,acStack_66c);
          local_728 = m_ui;
          local_724 = 0;
          goto LAB_0002b3b4;
        }
        if (uVar1 < 0x11) {
          if (uVar1 == 8) goto LAB_0002c500;
          goto LAB_0002c094;
        }
        if (uVar1 == 0x20) {
          SoundPlay(1,(int *)mui_Effect1);
          iVar7 = DAT_003af27c;
          iVar14 = DAT_003af278;
          if (iVar11 == 0) {
            if (DAT_003af720 <= (int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 10)) goto LAB_0002c094;
            iVar11 = 1;
            iVar6 = dir_serial_list(DAT_003af278,&DAT_002dd860);
          }
          else {
            iVar7 = iVar6 + -1;
            if (iVar10 + iVar9 + DAT_003af394 < iVar7) {
              iVar14 = iVar9 + DAT_003af394;
              iVar6 = dir_serial_list(iVar14,&DAT_002dd860);
              iVar7 = iVar10;
            }
            else {
              iVar14 = iVar9 + DAT_003af394;
              if (iVar14 < iVar7) {
                iVar6 = dir_serial_list(iVar14,&DAT_002dd860);
                iVar7 = iVar7 - iVar14;
              }
              else if (DAT_003af720 < (int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 10)) {
                iVar11 = 0;
                iVar7 = -1;
                iVar14 = iVar9;
                DAT_003af278 = iVar9;
                DAT_003af27c = iVar10;
              }
              else {
                iVar6 = dir_serial_list(0,&DAT_002dd860);
                iVar7 = 0;
                iVar14 = 0;
              }
            }
          }
        }
        else {
          if (uVar1 != 0x40) goto LAB_0002c094;
          SoundPlay(1,(int *)mui_Effect0);
          if (iVar11 == 0) {
            if (DAT_003af294 == (int *)0x0) {
              mui_LoadUIResource(&DAT_003af294,"setting.raw");
            }
LAB_0002c7b8:
            memcpy(DAT_003af29c,(void *)((int)DAT_003af294 + *DAT_003af294),
                   (gh_uint)*(gh_ushort *)((int)DAT_003af294 + 6) * (gh_uint)*(gh_ushort *)(DAT_003af294 + 1) *
                   2);
            mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af294,3);
            OutRect._8_4_ = 0;
            OutRect._12_4_ = 0;
            OutRect._16_4_ = 0x500;
            OutRect._20_4_ = 0x2d0;
            mui_outputxy_t(DAT_003af29c,DAT_003af788,DAT_003af78c,(gh_u1)DAT_003af798,
                           DAT_003af79c,(gh_byte *)&DAT_003af7a0);
            mui_outputxy_t(DAT_003af29c,DAT_003af788,DAT_003af78c + DAT_003af794,
                           (gh_u1)DAT_003af798,DAT_003af79c,(gh_byte *)&DAT_003af7e0);
            ForceFlashCount = 0;
            dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
            mui_ReadJoystick();
            diff_prev = 0;
            m_time0 = GetTicks();
            iVar6 = mui_ReadJoystick();
            do {
              if (iVar6 == 0x40) {
                SoundPlay(1,(int *)mui_Effect0);
                do {
                  if (DAT_003af294 == (int *)0x0) {
                    mui_LoadUIResource(&DAT_003af294,"setting.raw");
                  }
                  memcpy(DAT_003af29c,(void *)((int)DAT_003af294 + *DAT_003af294),
                         (gh_uint)*(gh_ushort *)((int)DAT_003af294 + 6) *
                         (gh_uint)*(gh_ushort *)(DAT_003af294 + 1) * 2);
                  mui_DispBlock(DAT_003af29c,DAT_003af2a0 << 1,DAT_003af294,4);
                  OutRect._16_4_ = 0x500;
                  OutRect._20_4_ = 0x2d0;
                  OutRect._8_4_ = 0;
                  OutRect._12_4_ = 0;
                  ForceFlashCount = 0;
                  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
                  mui_ReadJoystick();
                  diff_prev = 0;
                  m_time0 = GetTicks();
                  iVar6 = mui_ReadJoystick();
                  while (iVar6 != 0x41) {
                    if (iVar6 == 0x2000) {
                      DAT_003af394 = uVar2;
                      strcpy(root_path,acStack_66c);
                      DAT_003af26c = 0;
                      return;
                    }
                    if (iVar6 == 0x10) {
                      SoundPlay(1,(int *)mui_Effect0);
                      goto LAB_0002c7b8;
                    }
                    if (DAT_003af274 != 0) {
                      ForceFlashCount = 0;
                      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
                      DAT_003af274 = 0;
                    }
                    mui_WaitNMI();
                    iVar6 = mui_ReadJoystick();
                  }
                  JoystickTest(0);
                } while( true );
              }
              if (iVar6 == 0x2000) {
                if (m_ui != DAT_003af310) {
                  m_ui = DAT_003af310;
                  mui_LoadConfig();
                  mui_InitFont();
                  if (DAT_003af28c != 0) {
                    mui_LoadUIResource(&DAT_003af28c,"menu.raw");
                  }
                  if (DAT_003af294 != (int *)0x0) {
                    mui_LoadUIResource(&DAT_003af294,"setting.raw");
                  }
                  if (DAT_003af290 != 0) {
                    mui_LoadUIResource(&DAT_003af290,"search.raw");
                  }
                  if (DAT_003af298 != 0) {
                    mui_LoadUIResource(&DAT_003af298,"type.raw");
                  }
                  memcpy(DAT_003af29c,(void *)((int)DAT_003af294 + *DAT_003af294),
                         (gh_uint)*(gh_ushort *)((int)DAT_003af294 + 6) *
                         (gh_uint)*(gh_ushort *)(DAT_003af294 + 1) * 2);
                  uVar8 = (gh_u4)GetWorkPath();
                  sprintf(acStack_42c,"%s/setting.xml",uVar8);
                  pFVar3 = fopen(acStack_42c,"r");
                  if (pFVar3 == (FILE *)0x0) {
                    RARCH_LOG("open setting.xml fail!\n");
                    tree = 0;
                  }
                  else {
                    tree = mxmlLoadFile(0,pFVar3);
                    fclose(pFVar3);
                    if (tree != 0) {
                      iVar6 = mxmlFindElement(tree,tree,"config",0,0,1);
                      if (iVar6 != 0) {
                        mxmlElementSetAttr(iVar6,"language",*(gh_u4 *)(number + m_ui * 4));
                      }
                      if (tree != 0) {
                        pFVar3 = fopen(acStack_42c,"wb");
                        mxmlSaveFile(tree,pFVar3,0);
                        fflush(pFVar3);
                        iVar6 = fileno(pFVar3);
                        fsync(iVar6);
                        fclose(pFVar3);
                        mxmlDelete(tree);
                        tree = 0;
                      }
                    }
                  }
                }
                if (DAT_003af2b0 != (void *)0x0) {
                  free(DAT_003af2b0);
                  DAT_003af2b0 = (void *)0x0;
                }
                uVar8 = (gh_u4)GetWorkPath();
                sprintf(acStack_42c,"%s/recent.lst",uVar8);
                pFVar3 = fopen(acStack_42c,"wb");
                if (pFVar3 != (FILE *)0x0) {
                  fputc(0,pFVar3);
                  fflush(pFVar3);
                  iVar6 = fileno(pFVar3);
                  fsync(iVar6);
                  fclose(pFVar3);
                }
                if (DAT_003af2b4 != (void *)0x0) {
                  free(DAT_003af2b4);
                  DAT_003af2b4 = (void *)0x0;
                }
                uVar8 = (gh_u4)GetWorkPath();
                sprintf(acStack_42c,"%s/favorites.lst",uVar8);
                pFVar3 = fopen(acStack_42c,"wb");
                if (pFVar3 != (FILE *)0x0) {
                  fputc(0,pFVar3);
                  fflush(pFVar3);
                  iVar6 = fileno(pFVar3);
                  fsync(iVar6);
                  fclose(pFVar3);
                }
              }
              else if (iVar6 == 0x10) {
                SoundPlay(1,(int *)mui_Effect0);
                goto LAB_0002be88;
              }
              if (DAT_003af274 != 0) {
                ForceFlashCount = 0;
                dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
                DAT_003af274 = 0;
              }
              mui_WaitNMI();
              iVar6 = mui_ReadJoystick();
            } while( true );
          }
          if (iVar10 < DAT_003af394 + -1) {
            if ((-1 < iVar6) && (iVar6 + -1 <= iVar10 + iVar9)) goto LAB_0002c094;
            iVar7 = iVar10 + 1;
          }
          else {
            if (iVar6 + -1 <= iVar10 + iVar9) goto LAB_0002c094;
            iVar6 = dir_serial_list(iVar9 + 1,&DAT_002dd860);
            iVar7 = iVar10;
            iVar14 = iVar9 + 1;
          }
        }
      }
LAB_0002bfb4:
      DAT_003af274 = 1;
      iVar10 = iVar7;
      iVar9 = iVar14;
LAB_0002bfc4:
      DisplayPage_list(iVar9,iVar10,iVar6);
      ForceFlashCount = 0;
      dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
      DAT_003af274 = 0;
LAB_0002c004:
      mui_WaitNMI();
      goto LAB_0002c008;
    }
    if (uVar1 != 0x80) goto LAB_0002b800;
    if (local_724 == 0) {
      if (DAT_003af6f0 < (int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 6)) {
        local_724 = 1;
        DAT_003af27c = -1;
        iVar11 = iVar9;
      }
    }
    else if ((int)(gh_uint)*(gh_ushort *)(DAT_003af294 + 6) < DAT_003af6f0) {
      iVar11 = -1;
      local_724 = 0;
    }
    SoundPlay(1,(int *)mui_Effect1);
  }
  else {
    if (uVar1 != 0x2000) {
      if (uVar1 < 0x2001) {
        if (uVar1 == 0x800) {
          DAT_003af26c = 0;
          return;
        }
      }
      else {
        if (uVar1 == 0x8020) {
          DAT_003af26c = 0;
          return;
        }
        if (uVar1 == 0x8080) {
          DAT_003af26c = 0;
          return;
        }
      }
      goto LAB_0002b800;
    }
    if (local_724 != 0) {
      local_728 = DAT_003af27c;
    }
  }
LAB_0002b5d4:
  if (iVar11 != DAT_003af27c) goto LAB_0002b5dc;
LAB_0002b810:
  if (local_728 != m_ui) goto LAB_0002b828;
  if (DAT_003af274 != 0) goto LAB_0002b778;
LAB_0002b7a4:
  mui_WaitNMI();
  goto LAB_0002b7a8;
code_r0x0002c204:
  sprintf(acStack_42c,"%s/%s",path);
  local_32c = (&DAT_003b2320)[iVar10 * 0x101];
  RARCH_LOG("SeletEmuCore %s\n",acStack_42c);
  pcVar5 = (char *)SeletEmuCore(acStack_42c);
  if (pcVar5 != (char *)0x0) {
    SaveMenuLog();
    strcpy(local_128,pcVar5);
    filelist_run_game(acStack_42c);
  }
  if (ZIP_BUF != (void *)0x0) {
    free(ZIP_BUF);
  }
  ZIP_BUF = (void *)0x0;
  ZIP_BUF_SIZE = 0;
  DAT_003af278 = iVar9;
  DAT_003af27c = iVar10;
  goto LAB_0002be88;
}
