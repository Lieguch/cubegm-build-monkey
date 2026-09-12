/* ============================================================
 * mui_DisplayThumbnail   @ 0x00014f84   size=568B   callers=1
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_DisplayThumbnail(void)

{
  gh_u4 *iVar1;
  int iVar2;
  void *__ptr;
  int iVar3;
  gh_u1 *puVar4;
  gh_u4 local_38c;
  void *local_388;
  int local_384;
  int local_380;
  int local_37c;
  int local_378;
  int local_374;
  int local_370;
  int local_36c;
  int local_368;
  int local_364;
  int local_360;
  int local_35c;
  gh_u1 auStack_358 [128];
  gh_u1 auStack_2d8 [128];
  char acStack_258 [128];
  char acStack_1d8 [128];
  gh_u1 auStack_158 [296];
  size_t local_30;
  
  puVar4 = auStack_358;
  mui_extract_basepath(puVar4,&file_info_list + DAT_003af27c * 0x404,0x80);
  mui_extract_basename(auStack_2d8,&file_info_list + DAT_003af27c * 0x404,0x80);
  sprintf(acStack_258,"%s/%s/%s.dat",root_path,puVar4,puVar4);
  iVar1 = OpenZipU(acStack_258,0,2);
  if (iVar1 == 0) {
    RARCH_LOG("open %s fail\n",acStack_258);
  }
  else {
    while( true ) {
      sprintf(acStack_1d8,"%s_%03d.raw",auStack_2d8,DAT_003af280,puVar4);
      puVar4 = auStack_158;
      /* 证据：15028 add r9,sp,#0x240 + 15060 str r9,[sp]（AAPCS 第 5 参经栈传递）
         → 原厂此处传了 ZIPENTRY 输出缓冲；Ghidra C 漏参并留下死赋值 puVar4 = auStack_158 */
      iVar2 = FindZipItemA(iVar1,acStack_1d8,1,&local_38c,(ZIPENTRY *)auStack_158);
      if (iVar2 == 0) break;
      if (DAT_003af280 == 0) {
        iVar2 = 0;
        if (0 < DAT_003af6c4) {
          do {
            iVar3 = iVar2 + DAT_003af6bc;
            iVar2 = iVar2 + 1;
            iVar3 = DAT_003af2a0 * 2 * iVar3;
            memcpy((void *)(DAT_003af29c + iVar3 + DAT_003af6b8 * 2),
                   (void *)((int)DAT_003af28c + DAT_003af6b8 * 2 + *DAT_003af28c + iVar3),
                   DAT_003af6c0 << 1);
          } while (iVar2 < DAT_003af6c4);
        }
        goto LAB_00015128;
      }
      DAT_003af280 = 0;
    }
    __ptr = malloc(local_30);
    UnzipItem(iVar1,local_38c,__ptr,0,3);
    local_37c = DAT_003af6c0;
    local_36c = DAT_003af6b8;
    local_378 = DAT_003af6c4;
    local_368 = DAT_003af6bc;
    local_364 = DAT_003af6b8 + DAT_003af6c0;
    local_374 = DAT_003af6c0 << 1;
    local_370 = (int)DAT_003af29c;
    local_35c = DAT_003af2a0 << 1;
    local_360 = DAT_003af6bc + DAT_003af6c4;
    local_388 = __ptr;
    local_384 = iVar2;
    local_380 = iVar2;
    mui_blockcopy((int *)&local_370,(int *)&local_388);
    free(__ptr);
    DAT_003af280 = DAT_003af280 + 1;
LAB_00015128:
    CloseZipU(iVar1);
  }
  return;
}
