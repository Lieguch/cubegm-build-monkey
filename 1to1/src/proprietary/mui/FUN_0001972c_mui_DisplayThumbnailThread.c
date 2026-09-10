/* ============================================================
 * mui_DisplayThumbnailThread   @ 0x0001972c   size=292B   callers=0
 * module: 02_mui_menu_ui
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void mui_DisplayThumbnailThread(void)

{
  uint uVar1;
  int iVar2;
  int iVar3;
  pthread_t __th;
  uint uVar4;
  uint unaff_r4;
  int iVar5;
  
  iVar2 = GetTicks();
  if ((DisplayThumbnailflag & 1) != 0) {
    iVar5 = 0;
    do {
      if ((DisplayThumbnailflag & 2) == 0) {
        unaff_r4 = unaff_r4 + 1;
      }
      else {
        uVar4 = DisplayThumbnailflag | 8;
        if ((DisplayThumbnailflag & 4) == 0) {
          unaff_r4 = 1;
          DAT_003af280 = 0;
          DisplayThumbnailflag = DisplayThumbnailflag | 0xc;
        }
        else {
          uVar1 = unaff_r4 & 0x3f;
          unaff_r4 = unaff_r4 + 1;
          DisplayThumbnailflag = uVar4;
          if (uVar1 != 0) goto LAB_0001977c;
        }
        mui_DisplayThumbnail();
        DAT_003af274 = DAT_003af274 | 1;
      }
LAB_0001977c:
      DisplayThumbnailflag = DisplayThumbnailflag & 0xf7;
      iVar3 = GetTicks();
      iVar3 = (iVar5 / 0x3c + iVar2) - iVar3;
      if (0 < iVar3) {
        usleep(iVar3 * 1000);
      }
      iVar5 = iVar5 + 1000;
    } while ((DisplayThumbnailflag & 1) != 0);
  }
  __th = pthread_self();
  pthread_detach(__th);
  DisplayThumbnailflag = 0;
  return;
}
