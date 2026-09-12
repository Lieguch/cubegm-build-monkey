/* ============================================================
 * IsShoucang   @ 0x0001845c   size=572B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 IsShoucang(char *param_1)

{
  gh_u4 uVar1;
  FILE *__stream;
  size_t __n;
  gh_byte bVar2;
  gh_byte *pbVar3;
  int iVar4;
  gh_byte *pbVar5;
  gh_byte abStack_5ac [128];
  char acStack_52c [256];
  char local_42c [260];
  gh_u1 local_328;
  gh_u1 local_2a8;
  gh_u1 local_228;
  gh_u1 local_1a8;
  gh_byte *pbVar6;
  
  if (DAT_003af2b4 == (gh_byte *)0x0) {
    uVar1 = (gh_u4)GetWorkPath();
    sprintf(acStack_52c,"%s/favorites.lst",uVar1);
    __stream = fopen(acStack_52c,"rb");
    if (__stream == (FILE *)0x0) {
      DAT_003af2b4 = (gh_byte *)0x0;
      return 0;
    }
    fseek(__stream,0,2);
    __n = ftell(__stream);
    DAT_003af2b4 = malloc(__n + 1);
    fseek(__stream,0,0);
    fread(DAT_003af2b4,1,__n,__stream);
    DAT_003af2b4[__n] = 0;
    fclose(__stream);
    if (DAT_003af2b4 == (gh_byte *)0x0) {
      return 0;
    }
  }
  iVar4 = 0;
  pbVar3 = DAT_003af2b4;
  pbVar5 = abStack_5ac;
LAB_00018494:
  do {
    bVar2 = *pbVar3;
    if (bVar2 == 0xd) goto LAB_000184b8;
    if (0xd < bVar2) goto LAB_000184cc;
    while ((bVar2 != 0 && (pbVar6 = pbVar5, bVar2 != 10))) {
      while( true ) {
        pbVar5 = pbVar6 + 1;
        *pbVar6 = bVar2;
LAB_000184b8:
        do {
          pbVar3 = pbVar3 + 1;
          bVar2 = *pbVar3;
        } while (bVar2 == 0xd);
        if (bVar2 < 0xe) break;
LAB_000184cc:
        if ((bVar2 == 0x2c) || (pbVar6 = pbVar5, bVar2 == 0x3b)) goto LAB_000184dc;
      }
    }
LAB_000184dc:
    if (iVar4 == 0) {
      if (abStack_5ac < pbVar5) {
        *pbVar5 = 0;
        strcpy(local_42c,(char *)abStack_5ac);
        goto LAB_00018534;
      }
      local_42c[0] = '\0';
      if (bVar2 == 10) goto LAB_00018560;
    }
    else {
      if (iVar4 == 1) {
        if (abStack_5ac < pbVar5) {
          *pbVar5 = 0;
        }
        else {
          local_328 = 0;
        }
      }
      else if (iVar4 == 2) {
        if (abStack_5ac < pbVar5) {
          *pbVar5 = 0;
        }
        else {
          local_228 = 0;
        }
      }
      else if (iVar4 == 3) {
        if (abStack_5ac < pbVar5) {
          *pbVar5 = 0;
        }
        else {
          local_2a8 = 0;
        }
      }
      else if (iVar4 == 4) {
        if (abStack_5ac < pbVar5) {
          *pbVar5 = 0;
        }
        else {
          local_1a8 = 0;
        }
      }
LAB_00018534:
      if (bVar2 == 10) {
        if ((local_42c[0] != '\0') && (iVar4 = strcmp(param_1,local_42c), iVar4 == 0)) {
          return 1;
        }
LAB_00018560:
        pbVar3 = pbVar3 + 1;
        local_42c[0] = '\0';
        iVar4 = 0;
        pbVar5 = abStack_5ac;
        goto LAB_00018494;
      }
    }
    if (bVar2 == 0x2c || bVar2 == 0x3b) {
      pbVar3 = pbVar3 + 1;
      iVar4 = iVar4 + 1;
      pbVar5 = abStack_5ac;
    }
    else if (bVar2 == 0) {
      return 0;
    }
  } while( true );
}
