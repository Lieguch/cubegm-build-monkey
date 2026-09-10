/* ============================================================
 * mui_SoundplayThread   @ 0x00026b64   size=232B   callers=0
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_SoundplayThread(void)

{
  int iVar1;
  int iVar2;
  pthread_t __th;
  undefined *puVar3;
  
  iVar1 = GetTicks();
  puVar3 = (undefined *)0x0;
  while ((Soundplayflag & 1) != 0) {
    while( true ) {
      puVar3 = puVar3 + 1;
      iVar2 = GetTicks();
      iVar2 = (iVar1 + ((int)puVar3 * 1000 - 1000U) / 0x3c) - iVar2;
      if (0 < iVar2) {
        usleep(iVar2 * 1000);
      }
      if ((Soundplayflag & 2) == 0) break;
      AudioProcess();
      if (&UNK_000d2f00 < puVar3) {
        puVar3 = (undefined *)0x0;
        SoundClose();
        SoundPlayer._0_4_ = 0;
        SoundPlayer._36_4_ = 0;
        usleep(1000);
        SoundPlay(0,mui_MenuMusic);
        iVar1 = GetTicks();
      }
      if ((Soundplayflag & 1) == 0) goto LAB_00026bf8;
    }
  }
LAB_00026bf8:
  __th = pthread_self();
  pthread_detach(__th);
  Soundplayflag = 0;
  return;
}
