/* ============================================================
 * get_items_from_zipfile   @ 0x0001f39c   size=360B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int get_items_from_zipfile(undefined4 param_1,int param_2)

{
  char cVar1;
  int iVar2;
  char *__ptr;
  char *pcVar3;
  int iVar4;
  char *pcVar5;
  undefined4 local_424;
  char acStack_420 [1024];
  
  res_hz = OpenZipU(param_1,0,2);
  if (res_hz == 0) {
    RARCH_LOG("open %s fail\n",param_1);
    return 0;
  }
  zr = FindZipItemA(res_hz,"ui.cfg",1,&local_424,ze);
  if (zr != 0) {
    RARCH_LOG("find ui.cfg in %s fail\n",param_1);
    CloseZipU(res_hz);
    return 0;
  }
  __ptr = malloc(ze._296_4_);
  UnzipItem(res_hz,local_424,__ptr,0,3);
  CloseZipU(res_hz);
  if (__ptr == (char *)0x0) {
    iVar4 = 0;
LAB_0001f4a8:
    free(__ptr);
    return iVar4;
  }
  iVar4 = 0;
  pcVar3 = acStack_420;
  pcVar5 = __ptr;
LAB_0001f448:
  do {
    cVar1 = *pcVar5;
    while (pcVar5 = pcVar5 + 1, cVar1 != '\n') {
      if (cVar1 == '\r') goto LAB_0001f448;
      if (cVar1 == '\0') {
        *pcVar3 = '\0';
        get_item_from_line(acStack_420,iVar4 * 0xfa + param_2);
        iVar4 = iVar4 + 1;
        goto LAB_0001f4a8;
      }
      *pcVar3 = cVar1;
      pcVar3 = pcVar3 + 1;
      cVar1 = *pcVar5;
    }
    iVar2 = iVar4 * 0xfa;
    *pcVar3 = '\0';
    iVar4 = iVar4 + 1;
    get_item_from_line(acStack_420,iVar2 + param_2);
    pcVar3 = acStack_420;
  } while( true );
}
