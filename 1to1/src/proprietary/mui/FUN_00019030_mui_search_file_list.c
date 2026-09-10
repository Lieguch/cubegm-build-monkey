/* ============================================================
 * mui_search_file_list   @ 0x00019030   size=1616B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int mui_search_file_list(int param_1,int param_2)

{
  char *pcVar1;
  byte *pbVar2;
  undefined4 uVar3;
  long lVar4;
  char *pcVar5;
  char *pcVar6;
  byte bVar7;
  char cVar8;
  undefined1 *puVar9;
  byte *pbVar10;
  int iVar11;
  int iVar12;
  int iVar13;
  int iVar14;
  byte *pbVar15;
  int iVar16;
  byte *local_100;
  byte *local_fc;
  undefined1 *local_f8;
  undefined1 *local_f4;
  byte local_f0 [100];
  undefined4 local_8c [26];
  
  pbVar10 = DAT_003af2ac;
  iVar11 = *(int *)((&m_ui)[m_ui + 0x16] + 0x40);
  uVar3 = libiconv_open("utf-8","GB2312");
  if (0 < DAT_003af394) {
    puVar9 = &file_info_list;
    iVar12 = DAT_003af394 * 0x404;
    do {
      *puVar9 = 0;
      puVar9[0x104] = 0;
      puVar9[0x184] = 0;
      puVar9[0x204] = 0;
      puVar9[0x284] = 0;
      puVar9 = puVar9 + 0x404;
    } while (&file_info_list + iVar12 != puVar9);
  }
  bVar7 = *pbVar10;
  iVar12 = 0;
  iVar11 = (iVar11 + 4) * 0x80;
  iVar16 = 0;
  iVar13 = 0;
  pbVar2 = local_f0;
joined_r0x00019104:
  do {
    while( true ) {
      while (bVar7 == 0xd) {
        pbVar10 = pbVar10 + 1;
        bVar7 = *pbVar10;
      }
      if (bVar7 < 0xe) break;
      if ((bVar7 == 0x2c) || (bVar7 == 0x3b)) goto LAB_00019144;
LAB_0001911c:
      *pbVar2 = bVar7;
      pbVar10 = pbVar10 + 1;
      bVar7 = *pbVar10;
      pbVar2 = pbVar2 + 1;
    }
    if ((bVar7 != 0) && (bVar7 != 10)) goto LAB_0001911c;
LAB_00019144:
    if (iVar12 == 0) {
      if (local_f0 < pbVar2) {
        pbVar15 = &file_info_list + iVar13 * 0x404;
        *pbVar2 = 0;
        local_f4 = (undefined1 *)0x100;
        local_f8 = (undefined1 *)0x64;
        local_100 = local_f0;
        local_fc = pbVar15;
        libiconv(uVar3,&local_100,&local_f8,&local_fc,&local_f4);
        mui_extract_basepath(local_8c,pbVar15,100);
        lVar4 = strtol((char *)local_8c,(char **)0x0,10);
        (&DAT_003b2320)[iVar13 * 0x101] = lVar4;
        iVar14 = IsShoucang(pbVar15);
        if (iVar14 != 0) {
          (&DAT_003b2320)[iVar13 * 0x101] = (&DAT_003b2320)[iVar13 * 0x101] | 0x80;
        }
LAB_000191d0:
        bVar7 = *pbVar10;
      }
      else {
        (&file_info_list)[iVar13 * 0x404] = 0;
        bVar7 = *pbVar10;
      }
joined_r0x00019170:
      if (bVar7 == 10) {
        if ((&DAT_003b2324)[iVar13 * 0x404] == '\0') {
LAB_000194ac:
          mui_extract_basename(&DAT_003b2324 + iVar13 * 0x404,&file_info_list + iVar13 * 0x404,0x80)
          ;
        }
        iVar14 = iVar13 * 0x404;
        if ((&DAT_003b2424)[iVar14] == '\0') {
          strcpy(&DAT_003b2424 + iVar14,&DAT_003b2324 + iVar14);
          strupr();
        }
        if ((&DAT_003b23a4)[iVar13 * 0x404] == '\0') {
          strcpy(&DAT_003b23a4 + iVar14,&DAT_003b2324 + iVar14);
        }
        if ((&DAT_003b24a4)[iVar13 * 0x404] == '\0') {
          strcpy(&DAT_003b24a4 + iVar14,&DAT_003b2424 + iVar14);
        }
        iVar14 = iVar11 + 4 + iVar14;
        pcVar5 = &file_info_list + iVar14;
        cVar8 = (&file_info_list)[iVar14];
        pcVar6 = (char *)*m_search;
        do {
          if ((*pcVar6 == cVar8) && (pcVar1 = pcVar6 + 1, pcVar6 = pcVar6 + 1, *pcVar1 == '\0')) {
            if ((iVar16 < param_1) || (DAT_003af394 <= iVar13)) {
              iVar14 = iVar13 * 0x404;
              (&DAT_003b2324)[iVar14] = 0;
              (&DAT_003b23a4)[iVar14] = 0;
              (&DAT_003b2424)[iVar14] = 0;
              (&DAT_003b24a4)[iVar14] = 0;
            }
            else {
              iVar13 = iVar13 + 1;
              if (DAT_003af394 <= iVar13 && param_2 != 0) {
                return iVar16;
              }
            }
            bVar7 = *pbVar10;
            iVar16 = iVar16 + 1;
            goto LAB_000192e4;
          }
          pcVar5 = pcVar5 + 1;
          cVar8 = *pcVar5;
        } while (cVar8 != '\0');
        iVar14 = iVar13 * 0x404;
        (&DAT_003b2324)[iVar14] = 0;
        (&DAT_003b23a4)[iVar14] = 0;
        (&DAT_003b2424)[iVar14] = 0;
        (&DAT_003b24a4)[iVar14] = 0;
        bVar7 = *pbVar10;
LAB_000192e4:
        if (bVar7 == 10) {
          iVar12 = 0;
          pbVar10 = pbVar10 + 1;
          bVar7 = *pbVar10;
          pbVar2 = local_f0;
          goto joined_r0x00019104;
        }
      }
    }
    else {
      if (iVar12 != 1) {
        if (iVar12 == 2) {
          if (local_f0 < pbVar2) {
            *pbVar2 = 0;
            strcpy(&DAT_003b2424 + iVar13 * 0x404,(char *)local_f0);
            bVar7 = *pbVar10;
          }
          else {
            (&DAT_003b2424)[iVar13 * 0x404] = 0;
            bVar7 = *pbVar10;
          }
        }
        else if (iVar12 == 3) {
          if (local_f0 < pbVar2) {
            local_f8 = &DAT_003b23a4 + iVar13 * 0x404;
            goto LAB_000195cc;
          }
          (&DAT_003b23a4)[iVar13 * 0x404] = 0;
          bVar7 = *pbVar10;
        }
        else if (iVar12 == 4) {
          if (pbVar2 <= local_f0) {
            (&DAT_003b24a4)[iVar13 * 0x404] = 0;
            goto LAB_000191d0;
          }
          *pbVar2 = 0;
          strcpy(&DAT_003b24a4 + iVar13 * 0x404,(char *)local_f0);
          bVar7 = *pbVar10;
        }
        goto joined_r0x00019170;
      }
      if (local_f0 < pbVar2) {
        local_f8 = &DAT_003b2324 + iVar13 * 0x404;
LAB_000195cc:
        *pbVar2 = 0;
        local_f4 = (undefined1 *)0x64;
        local_8c[0] = 0x80;
        local_fc = local_f0;
        libiconv(uVar3,&local_fc,&local_f4,&local_f8,local_8c);
        bVar7 = *pbVar10;
        goto joined_r0x00019170;
      }
      (&DAT_003b2324)[iVar13 * 0x404] = 0;
      bVar7 = *pbVar10;
      if (bVar7 == 10) goto LAB_000194ac;
    }
    if (bVar7 == 0x2c || bVar7 == 0x3b) {
      iVar12 = iVar12 + 1;
      pbVar10 = pbVar10 + 1;
      bVar7 = *pbVar10;
      pbVar2 = local_f0;
      goto joined_r0x00019104;
    }
  } while (bVar7 != 0);
  if ((&file_info_list)[iVar13 * 0x404] != '\0') {
    iVar11 = iVar13 * 0x404 + iVar11 + 4;
    pcVar5 = &file_info_list + iVar11;
    cVar8 = (&file_info_list)[iVar11];
    pcVar6 = (char *)*m_search;
    do {
      if ((*pcVar6 == cVar8) && (pcVar1 = pcVar6 + 1, pcVar6 = pcVar6 + 1, *pcVar1 == '\0')) {
        if ((param_1 <= iVar16) &&
           ((iVar13 < DAT_003af394 && (param_2 != 0 && DAT_003af394 <= iVar13 + 1)))) {
          return iVar16;
        }
        iVar16 = iVar16 + 1;
        break;
      }
      pcVar5 = pcVar5 + 1;
      cVar8 = *pcVar5;
    } while (cVar8 != '\0');
  }
  libiconv_close(uVar3);
  return iVar16;
}
