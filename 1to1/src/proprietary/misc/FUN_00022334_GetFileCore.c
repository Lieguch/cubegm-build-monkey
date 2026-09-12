/* ============================================================
 * GetFileCore   @ 0x00022334   size=168B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 GetFileCore(char *param_1)

{
  int iVar1;
  char *pcVar2;
  gh_u4 uVar3;
  
  iVar1 = filelist_tree;
  if (filelist_tree != 0) {
    while (iVar1 = mxmlFindElement(iVar1,filelist_tree,(char *)DAT_002dbd74,0,0,1), iVar1 != 0) {
      pcVar2 = (char *)mxmlElementGetAttr(iVar1,DAT_002dcd70);
      pcVar2 = strstr(param_1,pcVar2);
      if (pcVar2 != (char *)0x0) {
        uVar3 = mxmlElementGetAttr(iVar1,DAT_002dd508);
        return uVar3;
      }
    }
  }
  return 0;
}
