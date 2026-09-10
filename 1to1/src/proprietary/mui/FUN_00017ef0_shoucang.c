/* ============================================================
 * shoucang   @ 0x00017ef0   size=1344B   callers=5
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void shoucang(char *param_1)

{
  char cVar1;
  gh_u4 uVar2;
  FILE *pFVar3;
  size_t sVar4;
  gh_byte *__ptr;
  gh_byte bVar5;
  gh_byte *pbVar6;
  int iVar7;
  gh_byte *pbVar8;
  gh_byte abStack_5ac [128];
  char acStack_52c [256];
  char local_42c [260];
  char local_328 [128];
  char local_2a8 [128];
  char local_228 [128];
  char local_1a8 [388];
  gh_byte *pbVar9;
  
  uVar2 = GetWorkPath();
  sprintf(acStack_52c,"%s/favorites.lst",uVar2);
  pFVar3 = fopen(acStack_52c,"rb");
  if (pFVar3 == (FILE *)0x0) {
    pFVar3 = fopen(acStack_52c,"wt");
    if (pFVar3 != (FILE *)0x0) {
      __ptr = (gh_byte *)0x0;
      goto LAB_00017fa4;
    }
  }
  else {
    fseek(pFVar3,0,2);
    sVar4 = ftell(pFVar3);
    __ptr = malloc(sVar4 + 1);
    fseek(pFVar3,0,0);
    fread(__ptr,1,sVar4,pFVar3);
    __ptr[sVar4] = 0;
    fclose(pFVar3);
    pFVar3 = fopen(acStack_52c,"wt");
    if (pFVar3 != (FILE *)0x0) {
LAB_00017fa4:
      code_convert_constprop_22(param_1,0x100,local_42c);
      code_convert_constprop_22(param_1 + 0x104,0x80,local_328);
      code_convert_constprop_22(param_1 + 0x184,0x80,local_2a8);
      if ((*(gh_uint *)(param_1 + 0x100) & 0x80) == 0) {
        fprintf(pFVar3,"%s;%s;%s;%s;%s\n",local_42c,local_328,param_1 + 0x204,local_2a8,
                param_1 + 0x284);
      }
    }
    if (__ptr != (gh_byte *)0x0) {
      iVar7 = 0;
      pbVar6 = __ptr;
      pbVar8 = abStack_5ac;
LAB_0001802c:
      do {
        bVar5 = *pbVar6;
        if (bVar5 == 0xd) goto LAB_00018050;
        if (0xd < bVar5) goto LAB_00018064;
        while ((bVar5 != 0 && (pbVar9 = pbVar8, bVar5 != 10))) {
          while( true ) {
            pbVar8 = pbVar9 + 1;
            *pbVar9 = bVar5;
LAB_00018050:
            do {
              pbVar6 = pbVar6 + 1;
              bVar5 = *pbVar6;
            } while (bVar5 == 0xd);
            if (bVar5 < 0xe) break;
LAB_00018064:
            if ((bVar5 == 0x2c) || (pbVar9 = pbVar8, bVar5 == 0x3b)) goto LAB_00018074;
          }
        }
LAB_00018074:
        if (iVar7 == 0) {
          cVar1 = '\0';
          if (abStack_5ac < pbVar8) {
            *pbVar8 = 0;
            strcpy(local_42c,(char *)abStack_5ac);
            cVar1 = local_42c[0];
          }
LAB_00018088:
          local_42c[0] = cVar1;
          if (bVar5 == 10) {
            if (local_328[0] == '\0') {
LAB_000182c4:
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
            bVar5 = *pbVar6;
            if (bVar5 == 10) {
              pbVar6 = pbVar6 + 1;
              if ((local_42c[0] == '\0') || (iVar7 = strcmp(param_1,local_42c), iVar7 == 0)) {
                iVar7 = 0;
                local_42c[0] = '\0';
                pbVar8 = abStack_5ac;
              }
              else {
                iVar7 = 0;
                fprintf(pFVar3,"%s;%s;%s;%s;%s\n",local_42c,local_328,local_228,local_2a8,local_1a8)
                ;
                local_42c[0] = '\0';
                pbVar8 = abStack_5ac;
              }
              goto LAB_0001802c;
            }
          }
        }
        else {
          if (iVar7 != 1) {
            cVar1 = local_42c[0];
            if (iVar7 == 2) {
              if (abStack_5ac < pbVar8) {
                *pbVar8 = 0;
                strcpy(local_228,(char *)abStack_5ac);
                cVar1 = local_42c[0];
              }
              else {
                local_228[0] = '\0';
              }
            }
            else if (iVar7 == 3) {
              if (abStack_5ac < pbVar8) {
                *pbVar8 = 0;
                strcpy(local_2a8,(char *)abStack_5ac);
                cVar1 = local_42c[0];
              }
              else {
                local_2a8[0] = '\0';
              }
            }
            else if (iVar7 == 4) {
              if (abStack_5ac < pbVar8) {
                *pbVar8 = 0;
                strcpy(local_1a8,(char *)abStack_5ac);
                cVar1 = local_42c[0];
              }
              else {
                local_1a8[0] = '\0';
              }
            }
            goto LAB_00018088;
          }
          if (abStack_5ac < pbVar8) {
            *pbVar8 = 0;
            strcpy(local_328,(char *)abStack_5ac);
            cVar1 = local_42c[0];
            goto LAB_00018088;
          }
          local_328[0] = '\0';
          if (bVar5 == 10) goto LAB_000182c4;
        }
        if (bVar5 == 0x2c || bVar5 == 0x3b) {
          pbVar6 = pbVar6 + 1;
          iVar7 = iVar7 + 1;
          pbVar8 = abStack_5ac;
          goto LAB_0001802c;
        }
      } while (bVar5 != 0);
      fputc(0,pFVar3);
      free(__ptr);
      goto LAB_0001811c;
    }
  }
  fputc(0,pFVar3);
LAB_0001811c:
  fflush(pFVar3);
  iVar7 = fileno(pFVar3);
  fsync(iVar7);
  fclose(pFVar3);
  uVar2 = GetWorkPath();
  sprintf(acStack_52c,"%s/favorites.lst",uVar2);
  pFVar3 = fopen(acStack_52c,"rb");
  if (pFVar3 != (FILE *)0x0) {
    fseek(pFVar3,0,2);
    sVar4 = ftell(pFVar3);
    if (DAT_003af2b4 != (void *)0x0) {
      free(DAT_003af2b4);
    }
    DAT_003af2b4 = malloc(sVar4 + 1);
    fseek(pFVar3,0,0);
    fread(DAT_003af2b4,1,sVar4,pFVar3);
    *(gh_u1 *)((int)DAT_003af2b4 + sVar4) = 0;
    fclose(pFVar3);
    return;
  }
  DAT_003af2b4 = (void *)0x0;
  return;
}
