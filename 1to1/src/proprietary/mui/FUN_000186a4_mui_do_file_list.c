/* ============================================================
 * mui_do_file_list   @ 0x000186a4   size=1296B   callers=3
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int mui_do_file_list(int param_1,byte *param_2)

{
  undefined4 uVar1;
  long lVar2;
  int iVar3;
  byte *pbVar4;
  byte bVar5;
  undefined1 *puVar6;
  byte *pbVar7;
  int iVar8;
  int iVar9;
  int iVar10;
  byte *local_100;
  byte *local_fc;
  undefined1 *local_f8;
  undefined1 *local_f4;
  byte abStack_f0 [100];
  char local_8c [104];
  
  uVar1 = libiconv_open("utf-8","GB2312");
  if (0 < DAT_003af394) {
    puVar6 = &file_info_list;
    iVar8 = DAT_003af394 * 0x404;
    do {
      *puVar6 = 0;
      *(undefined4 *)(puVar6 + 0x100) = 0;
      puVar6[0x104] = 0;
      puVar6[0x184] = 0;
      puVar6[0x204] = 0;
      puVar6[0x284] = 0;
      puVar6 = puVar6 + 0x404;
    } while (puVar6 != &file_info_list + iVar8);
  }
  iVar8 = 0;
  bVar5 = *param_2;
  iVar9 = 0;
  iVar10 = 0;
  pbVar7 = abStack_f0;
LAB_00018754:
  if (bVar5 == 0xd) goto LAB_00018774;
  if (0xd < bVar5) goto LAB_00018788;
  while ((bVar5 != 0 && (pbVar4 = pbVar7, bVar5 != 10))) {
    while( true ) {
      pbVar7 = pbVar4 + 1;
      *pbVar4 = bVar5;
LAB_00018774:
      do {
        bVar5 = param_2[1];
        param_2 = param_2 + 1;
      } while (bVar5 == 0xd);
      if (bVar5 < 0xe) break;
LAB_00018788:
      if ((bVar5 == 0x2c) || (pbVar4 = pbVar7, bVar5 == 0x3b)) goto LAB_00018798;
    }
  }
LAB_00018798:
  if ((iVar9 < param_1) || (DAT_003af394 <= iVar10)) {
    if (bVar5 == 10) {
      if (abStack_f0 < pbVar7) {
        iVar9 = iVar9 + 1;
      }
      goto LAB_0001880c;
    }
  }
  else {
    if (iVar8 == 0) {
      if (pbVar7 <= abStack_f0) {
        (&file_info_list)[iVar10 * 0x404] = 0;
        bVar5 = *param_2;
        if (bVar5 == 10) goto LAB_0001880c;
        goto LAB_000187dc;
      }
      *pbVar7 = 0;
      pbVar4 = &file_info_list + iVar10 * 0x404;
      local_f8 = (undefined1 *)0x64;
      local_f4 = (undefined1 *)0x100;
      local_100 = abStack_f0;
      local_fc = pbVar4;
      libiconv(uVar1,&local_100,&local_f8,&local_fc,&local_f4);
      mui_extract_basepath(local_8c,pbVar4,100);
      lVar2 = strtol(local_8c,(char **)0x0,10);
      (&DAT_003b2320)[iVar10 * 0x101] = lVar2;
      iVar3 = IsShoucang(pbVar4);
      if (iVar3 != 0) {
        (&DAT_003b2320)[iVar10 * 0x101] = (&DAT_003b2320)[iVar10 * 0x101] | 0x80;
      }
LAB_000189c4:
      bVar5 = *param_2;
    }
    else if (iVar8 == 1) {
      if (abStack_f0 < pbVar7) {
        local_f8 = &DAT_003b2324 + iVar10 * 0x404;
LAB_00018a98:
        *pbVar7 = 0;
        local_f4 = (undefined1 *)0x64;
        local_8c[0] = -0x80;
        local_8c[1] = '\0';
        local_8c[2] = '\0';
        local_8c[3] = '\0';
        local_fc = abStack_f0;
        libiconv(uVar1,&local_fc,&local_f4,&local_f8,local_8c);
        bVar5 = *param_2;
      }
      else {
        (&DAT_003b2324)[iVar10 * 0x404] = 0;
        bVar5 = *param_2;
      }
    }
    else if (iVar8 == 2) {
      if (abStack_f0 < pbVar7) {
        *pbVar7 = 0;
        strcpy(&DAT_003b2424 + iVar10 * 0x404,(char *)abStack_f0);
        bVar5 = *param_2;
      }
      else {
        (&DAT_003b2424)[iVar10 * 0x404] = 0;
        bVar5 = *param_2;
      }
    }
    else if (iVar8 == 3) {
      if (abStack_f0 < pbVar7) {
        local_f8 = &DAT_003b23a4 + iVar10 * 0x404;
        goto LAB_00018a98;
      }
      (&DAT_003b23a4)[iVar10 * 0x404] = 0;
      bVar5 = *param_2;
    }
    else if (iVar8 == 4) {
      if (pbVar7 <= abStack_f0) {
        (&DAT_003b24a4)[iVar10 * 0x404] = 0;
        goto LAB_000189c4;
      }
      *pbVar7 = 0;
      strcpy(&DAT_003b24a4 + iVar10 * 0x404,(char *)abStack_f0);
      bVar5 = *param_2;
    }
    if (bVar5 == 10) {
      iVar8 = iVar10 * 0x404;
      if ((&file_info_list)[iVar8] != '\0') {
        if ((&DAT_003b2324)[iVar8] == '\0') {
          mui_extract_basename(&DAT_003b2324 + iVar8,&file_info_list + iVar8,0x80);
        }
        iVar8 = iVar10 * 0x404;
        if ((&DAT_003b2424)[iVar8] == '\0') {
          strcpy(&DAT_003b2424 + iVar8,&DAT_003b2324 + iVar8);
          strupr();
        }
        iVar8 = iVar10 * 0x404;
        if ((&DAT_003b23a4)[iVar8] == '\0') {
          strcpy(&DAT_003b23a4 + iVar8,&DAT_003b2324 + iVar8);
        }
        iVar8 = iVar10 * 0x404;
        if ((&DAT_003b24a4)[iVar8] == '\0') {
          strcpy(&DAT_003b24a4 + iVar8,&DAT_003b2424 + iVar8);
        }
        iVar10 = iVar10 + 1;
        iVar9 = iVar9 + 1;
      }
      if ((mui_fast_lsit != 0) && (DAT_003af394 <= iVar10)) goto LAB_00018830;
LAB_0001880c:
      bVar5 = param_2[1];
      iVar8 = 0;
      param_2 = param_2 + 1;
      pbVar7 = abStack_f0;
      goto LAB_00018754;
    }
  }
LAB_000187dc:
  if (bVar5 == 0x2c || bVar5 == 0x3b) {
    bVar5 = param_2[1];
    iVar8 = iVar8 + 1;
    param_2 = param_2 + 1;
    pbVar7 = abStack_f0;
  }
  else if (bVar5 == 0) {
    if (abStack_f0 < pbVar7) {
      iVar9 = iVar9 + 1;
    }
LAB_00018830:
    libiconv_close(uVar1);
    return iVar9;
  }
  goto LAB_00018754;
}
