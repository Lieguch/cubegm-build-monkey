/* ============================================================
 * mui_run_game   @ 0x000229f8   size=1928B   callers=5
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 mui_run_game(char *param_1)

{
  char cVar1;
  FILE *pFVar2;
  gh_u4 uVar3;
  size_t __n;
  char *__dest;
  gh_byte bVar4;
  pthread_t *ppVar5;
  gh_byte *pbVar7;
  int iVar8;
  gh_byte *local_6c8;
  pthread_t apStack_6ac [32];
  char acStack_62c [256];
  char acStack_52c [256];
  char local_42c [260];
  char local_328 [128];
  char local_2a8 [128];
  char local_228 [128];
  char local_1a8 [388];
  pthread_t *ppVar6;
  
  RARCH_LOG("mui_run_game:%s\n",param_1);
  mui_extract_basename(RomName,param_1,0x100);
  RARCH_LOG("RomName:%s\n",RomName);
  sprintf(acStack_52c,"%s/%s",root_path,param_1);
  pFVar2 = fopen(acStack_52c,"rb");
  if (pFVar2 == (FILE *)0x0) {
    RARCH_LOG("find %s miss\n",param_1);
    return 0;
  }
  fclose(pFVar2);
  Soundplayflag = Soundplayflag & 0xfe;
  while (Soundplayflag != 0) {
    usleep(1000);
  }
  SoundClose(0);
  DisplayThumbnailflag = DisplayThumbnailflag & 0xfe;
  SoundPlayer._0_4_ = 0;
  SoundPlayer._36_4_ = 0;
  while (DisplayThumbnailflag != 0) {
    usleep(1000);
  }
  memset(DAT_003af29c,0,DAT_003af2a4 * DAT_003af2a0 * 2);
  ForceFlashCount = 0;
  dispFlip(DAT_003af29c,DAT_003af2a0,DAT_003af2a4,DAT_003af2a0 << 1);
  uVar3 = GetWorkPath();
  sprintf(acStack_62c,"%s/recent.lst",uVar3);
  pFVar2 = fopen(acStack_62c,"rb");
  if (pFVar2 == (FILE *)0x0) {
    pFVar2 = fopen(acStack_62c,"wt");
    if (pFVar2 != (FILE *)0x0) {
      local_6c8 = (gh_byte *)0x0;
      goto LAB_00022bec;
    }
  }
  else {
    fseek(pFVar2,0,2);
    __n = ftell(pFVar2);
    local_6c8 = malloc(__n + 1);
    fseek(pFVar2,0,0);
    fread(local_6c8,1,__n,pFVar2);
    local_6c8[__n] = 0;
    fclose(pFVar2);
    pFVar2 = fopen(acStack_62c,"wt");
    if (pFVar2 != (FILE *)0x0) {
LAB_00022bec:
      code_convert_constprop_22(param_1,0x100,local_42c);
      code_convert_constprop_22(param_1 + 0x104,0x80,local_328);
      code_convert_constprop_22(param_1 + 0x184,0x80,local_2a8);
      fprintf(pFVar2,"%s;%s;%s;%s;%s\n",local_42c,local_328,param_1 + 0x204,local_2a8,
              param_1 + 0x284);
    }
    if (local_6c8 != (gh_byte *)0x0) {
      iVar8 = 0;
      ppVar5 = apStack_6ac;
      pbVar7 = local_6c8;
LAB_00022c94:
      do {
        bVar4 = *pbVar7;
        if (bVar4 == 0xd) goto LAB_00022cb8;
        if (0xd < bVar4) goto LAB_00022ccc;
        while ((bVar4 != 0 && (ppVar6 = ppVar5, bVar4 != 10))) {
          while( true ) {
            ppVar5 = (pthread_t *)((int)ppVar6 + 1);
            *(gh_byte *)ppVar6 = bVar4;
LAB_00022cb8:
            do {
              pbVar7 = pbVar7 + 1;
              bVar4 = *pbVar7;
            } while (bVar4 == 0xd);
            if (bVar4 < 0xe) break;
LAB_00022ccc:
            if ((bVar4 == 0x2c) || (ppVar6 = ppVar5, bVar4 == 0x3b)) goto LAB_00022cdc;
          }
        }
LAB_00022cdc:
        if (iVar8 == 0) {
          cVar1 = '\0';
          if (apStack_6ac < ppVar5) {
            *(gh_byte *)ppVar5 = 0;
            strcpy(local_42c,(char *)apStack_6ac);
            cVar1 = local_42c[0];
          }
LAB_00022cf0:
          local_42c[0] = cVar1;
          if (bVar4 == 10) {
            if (local_328[0] == '\0') {
LAB_00022fd0:
              mui_extract_basename(local_328,local_42c,0x80);
              if (local_228[0] == '\0') goto LAB_00022ff4;
LAB_00022f30:
              if (local_2a8[0] != '\0') goto LAB_00022f3c;
LAB_0002301c:
              strcpy(local_2a8,local_328);
              if (local_1a8[0] == '\0') goto LAB_0002303c;
LAB_00022f48:
              bVar4 = *pbVar7;
            }
            else {
              if (local_228[0] != '\0') goto LAB_00022f30;
LAB_00022ff4:
              strcpy(local_228,local_328);
              strupr();
              if (local_2a8[0] == '\0') goto LAB_0002301c;
LAB_00022f3c:
              if (local_1a8[0] != '\0') goto LAB_00022f48;
LAB_0002303c:
              strcpy(local_1a8,local_228);
              bVar4 = *pbVar7;
            }
            if (bVar4 == 10) {
              pbVar7 = pbVar7 + 1;
              if ((local_42c[0] == '\0') || (iVar8 = strcmp(param_1,local_42c), iVar8 == 0)) {
                iVar8 = 0;
                local_42c[0] = '\0';
                ppVar5 = apStack_6ac;
              }
              else {
                iVar8 = 0;
                fprintf(pFVar2,"%s;%s;%s;%s;%s\n",local_42c,local_328,local_228,local_2a8,local_1a8)
                ;
                local_42c[0] = '\0';
                ppVar5 = apStack_6ac;
              }
              goto LAB_00022c94;
            }
          }
        }
        else {
          if (iVar8 != 1) {
            cVar1 = local_42c[0];
            if (iVar8 == 2) {
              if (apStack_6ac < ppVar5) {
                __dest = local_228;
                goto LAB_00023074;
              }
              local_228[0] = '\0';
            }
            else if (iVar8 == 3) {
              if (apStack_6ac < ppVar5) {
                __dest = local_2a8;
                goto LAB_00023074;
              }
              local_2a8[0] = '\0';
            }
            else if (iVar8 == 4) {
              if (apStack_6ac < ppVar5) {
                __dest = local_1a8;
                goto LAB_00023074;
              }
              local_1a8[0] = '\0';
            }
            goto LAB_00022cf0;
          }
          if (apStack_6ac < ppVar5) {
            __dest = local_328;
LAB_00023074:
            *(gh_byte *)ppVar5 = 0;
            strcpy(__dest,(char *)apStack_6ac);
            cVar1 = local_42c[0];
            goto LAB_00022cf0;
          }
          local_328[0] = '\0';
          if (bVar4 == 10) goto LAB_00022fd0;
        }
        if (bVar4 == 0x2c || bVar4 == 0x3b) {
          pbVar7 = pbVar7 + 1;
          iVar8 = iVar8 + 1;
          ppVar5 = apStack_6ac;
          goto LAB_00022c94;
        }
      } while (bVar4 != 0);
      fputc(0,pFVar2);
      free(local_6c8);
      goto LAB_00022d70;
    }
  }
  fputc(0,pFVar2);
LAB_00022d70:
  fflush(pFVar2);
  iVar8 = fileno(pFVar2);
  fsync(iVar8);
  fclose(pFVar2);
  if (DAT_003af28c != (void *)0x0) {
    free(DAT_003af28c);
    DAT_003af28c = (void *)0x0;
  }
  if (DAT_003af290 != (void *)0x0) {
    free(DAT_003af290);
    DAT_003af290 = (void *)0x0;
  }
  if (DAT_003af294 != (void *)0x0) {
    free(DAT_003af294);
    DAT_003af294 = (void *)0x0;
  }
  if (DAT_003af298 != (void *)0x0) {
    free(DAT_003af298);
    DAT_003af298 = (void *)0x0;
  }
  if (DAT_003af2a8 != (void *)0x0) {
    free(DAT_003af2a8);
    DAT_003af2a8 = (void *)0x0;
  }
  if (DAT_003af2ac != (void *)0x0) {
    free(DAT_003af2ac);
    DAT_003af2ac = (void *)0x0;
  }
  if (DAT_003af2b0 != (void *)0x0) {
    free(DAT_003af2b0);
    DAT_003af2b0 = (void *)0x0;
  }
  iVar8 = GetFileCore(acStack_52c);
  if (iVar8 == 0) {
    file_info_list_ext[0x80] = 0;
    uVar3 = run_game(acStack_52c,0);
  }
  else {
    FilePreEmu(acStack_52c);
    uVar3 = Core_Load(acStack_52c,iVar8);
  }
  Soundplayflag = 3;
  iVar8 = pthread_create(apStack_6ac,(pthread_attr_t *)0x0,mui_SoundplayThread,(void *)0x0);
  if (iVar8 != 0) {
    RARCH_LOG("can\'t create mui_SoundplayThread process thread \r\n");
  }
  DisplayThumbnailflag = 1;
  iVar8 = pthread_create(apStack_6ac,(pthread_attr_t *)0x0,mui_DisplayThumbnailThread,(void *)0x0);
  if (iVar8 != 0) {
    RARCH_LOG("can\'t create mui_DisplayThread process thread \r\n");
  }
  usleep(1000);
  SoundPlay(0,mui_MenuMusic);
  dispmeninfo();
  return uVar3;
}
