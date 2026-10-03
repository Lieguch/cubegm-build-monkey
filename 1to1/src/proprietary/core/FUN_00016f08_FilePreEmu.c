/* ============================================================
 * FilePreEmu   @ 0x00016f08   size=676B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 FilePreEmu(char *param_1)

{
  char *pcVar1;
  gh_u4 uVar2;
  FILE *__stream;
  gh_u4 *iVar3;
  int iVar4;
  gh_uint uVar5;
  /* 根修（UB）：同 run_game.c —— 这是 0x130 字节栈缓冲，非 4 字节 int。 */
  gh_u1 local_158[0x130];
  gh_u1 auStack_154 [292];
  int local_30;
  
  pcVar1 = (char *)GetFilenameExt(param_1);
  strcpy((char *)(ze + 184),pcVar1);
  strupr(ze + 184);
  Filetype = 0;
  GetCoreIndex((char *)(ze + 184));
  RARCH_LOG("Filetype %d\n",Filetype);
  uVar5 = Filetype;
  if (Filetype < 0x10000) {
    __stream = fopen(param_1,"rb");
    if (__stream != (FILE *)0x0) {
    RARCH_LOG("FilePreEmu: open file SUCCESS\n");
      fseek(__stream,0,2);
      ZIP_BUF_SIZE = ftell(__stream);
      fseek(__stream,0,0);
      uVar5 = ZIP_BUF_SIZE + 3 & 0xfffffffc;
      ZIP_BUF_SIZE = uVar5;
      ZIP_BUF = malloc(uVar5 + 4);
      if (ZIP_BUF == (void *)0x0) {
        ZIP_BUF_SIZE = 0;
      }
      else {
        fread(ZIP_BUF,1,uVar5,__stream);
      }
      fclose(__stream);
      RARCH_LOG("FilePreEmu: return 1\n");
      return 1;
    }
    RARCH_LOG("FilePreEmu: file open FAIL\n");
    uVar2 = 0;
  }
  else {
    pcVar1 = strstr(param_1,"000/");
    if (pcVar1 == (char *)0x0) {
      memset(&local_158,0,0x130);
      iVar3 = OpenZipU(param_1,0,2);
    if (iVar3 == 0) {
    RARCH_LOG("FilePreEmu: OpenZipU FAIL\n");
      RARCH_LOG("open %s fail!\n",param_1);
      uVar2 = 0;
    }
    else {
    RARCH_LOG("FilePreEmu: OpenZipU OK\n");
        GetZipItemA(iVar3,0xffffffff,&local_158);
        RARCH_LOG("zipcount %d\n",*(int *)(void *)local_158);
        if (local_158 < 2) {
          iVar4 = GetZipItemA(iVar3,0,&local_158);
          RARCH_LOG("FilePreEmu: GetZipItemA0 result=%d\n",iVar4);
          if (iVar4 == 0) {
            strupr(auStack_154);
            pcVar1 = (char *)GetFilenameExt(auStack_154);
            strcpy((char *)(ze + 184),pcVar1);
            strupr(ze + 184);
            RARCH_LOG("FilenameExt %s\n",(char *)(ze + 184));
            GetCoreIndex((char *)(ze + 184));
            RARCH_LOG("Filetype %d\n",Filetype);
            ZIP_BUF_SIZE = local_30;
            ZIP_BUF = malloc(local_30 + 0x10);
            if (ZIP_BUF == (void *)0x0) {
              ZIP_BUF_SIZE = 0;
            }
            else {
              iVar4 = UnzipItem(iVar3,0,ZIP_BUF,0,3);
              if (iVar4 != 0) {
                free(ZIP_BUF);
                ZIP_BUF = (void *)0x0;
                ZIP_BUF_SIZE = 0;
              }
            }
          }
        }
        else {
          Filetype = Filetype | 1;
        }
        CloseZipU(iVar3);
        RARCH_LOG("FilePreEmu: return 1\n");
        uVar2 = 1;
      }
    }
    else {
      uVar2 = 1;
      Filetype = uVar5 | 1;
    }
  }
  return uVar2;
}
