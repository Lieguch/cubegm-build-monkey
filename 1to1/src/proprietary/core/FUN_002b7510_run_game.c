/* ============================================================
 * run_game   @ 0x002b7510   size=1260B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 run_game(char *param_1)

{
  char *pcVar1;
  int iVar2;
  FILE *__stream;
  gh_u4 *iVar3;
  int iVar4;
  size_t sVar5;
  gh_uint uVar6;
  char acStack_160 [8];
  int local_158;
  char acStack_154 [4];
  char acStack_150 [288];
  size_t local_30;
  
  ZIP_BUF = (void *)0x0;
  ZIP_BUF_SIZE = 0;
  pcVar1 = (char *)GetFilenameExt();
  strcpy(acStack_160,pcVar1);
  strupr(acStack_160);
  RARCH_LOG("run_game %s,%s\n",param_1,acStack_160);
  Filetype = 0;
  iVar2 = GetCoreIndex(acStack_160);
  uVar6 = Filetype;
  if (0xffff < Filetype) {
    pcVar1 = strstr(param_1,"/000/");
    if (pcVar1 != (char *)0x0) {
      Filetype = uVar6 | 1;
      FBA_Load(param_1);
      return 1;
    }
    memset(&local_158,0,0x130);
    iVar3 = OpenZipU(param_1,0,2);
    if (iVar3 != 0) {
      GetZipItemA(iVar3,0xffffffff,&local_158);
      iVar4 = GetZipItemA(iVar3,0,&local_158);
      if (iVar4 == 0) {
        strupr(acStack_154);
        pcVar1 = (char *)GetFilenameExt(acStack_154);
        strcpy(acStack_160,pcVar1);
        if (1 < local_158) {
          Filetype = Filetype | 1;
          CloseZipU(iVar3);
          FBA_Load(param_1,Filetype);
          return 1;
        }
        iVar2 = GetCoreIndex(acStack_160);
        if ((short)Filetype == 0x10) {
          CloseZipU(iVar3);
          Gpsp_Load(param_1,Filetype);
          return 1;
        }
        ZIP_BUF_SIZE = local_30;
        ZIP_BUF = malloc(local_30 + 0x10);
        if (ZIP_BUF == (void *)0x0) {
          CloseZipU(iVar3);
          return 0;
        }
        iVar4 = UnzipItem(iVar3,0,ZIP_BUF,0,3);
        if (iVar4 == 0) {
          CloseZipU(iVar3);
        }
      }
    }
LAB_002b7664:
    uVar6 = Filetype & 0xffff;
    if (uVar6 == 4) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 8) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 2) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 0x400) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if ((uVar6 - 0x20 & 0xffffffdf) == 0) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 0x100) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
      uVar6 = Filetype & 0xffff;
    }
    if (uVar6 == 0x200) {
      Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
    }
    if (ZIP_BUF != (void *)0x0) {
      free(ZIP_BUF);
    }
    ZIP_BUF_SIZE = 0;
    ZIP_BUF = (void *)0x0;
    return 1;
  }
  if (Filetype == 0x10) {
    Gpsp_Load(param_1,0x10);
    return 1;
  }
  if (Filetype != 0x80) {
    if (Filetype != 0x800) {
      __stream = fopen(param_1,"rb");
      if (__stream == (FILE *)0x0) {
        RARCH_LOG("%s open fail\r\n",param_1);
        return 0xffffffff;
      }
      fseek(__stream,0,2);
      ZIP_BUF_SIZE = ftell(__stream);
      fseek(__stream,0,0);
      ZIP_BUF_SIZE = ZIP_BUF_SIZE + 3 & 0xfffffffc;
      ZIP_BUF = malloc(ZIP_BUF_SIZE + 4);
      if (ZIP_BUF == (void *)0x0) {
        fclose(__stream);
      }
      fread(ZIP_BUF,1,ZIP_BUF_SIZE,__stream);
      fclose(__stream);
      goto LAB_002b7664;
    }
    extract_basepath((char *)&local_158,param_1,100);
    sVar5 = strlen((char *)&local_158);
    builtin_strncpy((char *)((int)&local_158 + sVar5),"/gam",4);
    builtin_strncpy(acStack_154 + sVar5,"e.cf",4);
    (acStack_150 + sVar5)[0] = 'g';
    (acStack_150 + sVar5)[1] = '\0';
    get_items_from_file((char *)&local_158,items);
  }
  Core_Load(param_1,DAT_003b0278 + iVar2 * 0x44);
  return 1;
}
