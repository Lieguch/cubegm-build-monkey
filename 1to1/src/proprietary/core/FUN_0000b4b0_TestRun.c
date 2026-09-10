/* ============================================================
 * TestRun   @ 0x0000b4b0   size=476B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void TestRun(void)

{
  FILE *pFVar1;
  void *__ptr;
  size_t __size;
  void *pvVar2;
  void *pvVar3;
  int iVar4;
  gh_u8 uVar5;
  gh_u8 uVar6;
  void *local_98;
  char acStack_8c [104];
  
  sprintf(acStack_8c,"%s/images/02.pcm",work_path);
  pFVar1 = fopen(acStack_8c,"rb");
  if (pFVar1 == (FILE *)0x0) {
    __size = 0;
  }
  else {
    fseek(pFVar1,0,2);
    __size = ftell(pFVar1);
    fseek(pFVar1,0,0);
    local_98 = malloc(__size);
    if (local_98 != (void *)0x0) {
      fread(local_98,1,__size,pFVar1);
    }
    fclose(pFVar1);
  }
  __ptr = malloc(0x1c2000);
  frame_time_last = GetTick();
  iVar4 = 0;
  diff_prev = 0;
  pvVar2 = local_98;
  do {
    while( true ) {
      iVar4 = iVar4 + 1;
      sprintf(acStack_8c,"%s/images/%02d.raw",work_path,iVar4);
      pFVar1 = fopen(acStack_8c,"rb");
      if (pFVar1 != (FILE *)0x0) break;
      iVar4 = 0;
    }
    fread(__ptr,1,0x3fc00,pFVar1);
    fclose(pFVar1);
    dispFlip(__ptr,0x1e0,0x110,0x3c0);
    pvVar3 = (void *)((int)pvVar2 + 0xb7c);
    if ((void *)((int)local_98 + __size) < (void *)((int)pvVar2 + 0xb7c)) {
      pvVar3 = (void *)((int)local_98 + 0xb7c);
      pvVar2 = local_98;
    }
    uVar5 = GetTick();
    PlaySound(pvVar2,0x2df);
    uVar6 = GetTick();
    if ((int)((gh_ulonglong)uVar6 >> 0x20) !=
        (int)((gh_ulonglong)uVar5 >> 0x20) + (gh_uint)((gh_uint)uVar6 < (gh_uint)uVar5) ||
        5000 < (gh_uint)uVar6 - (gh_uint)uVar5) {
      printf("++++ AudioProcess timer over %dus ++++\n");
    }
    WaitNMI();
    pvVar2 = pvVar3;
  } while( true );
}
