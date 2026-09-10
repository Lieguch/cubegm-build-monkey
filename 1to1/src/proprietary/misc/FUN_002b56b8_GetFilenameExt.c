/* ============================================================
 * GetFilenameExt   @ 0x002b56b8   size=92B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

char * GetFilenameExt(char *param_1)

{
  size_t sVar1;
  char *pcVar2;
  uint uVar3;
  
  sVar1 = strlen(param_1);
  uVar3 = sVar1 - 1;
  pcVar2 = param_1 + uVar3;
  if (!CARRY4((uint)param_1,uVar3)) {
    if (param_1[uVar3] != '.') {
      do {
        pcVar2 = pcVar2 + -1;
        if (pcVar2 == param_1 + -1) goto LAB_002b5704;
      } while (*pcVar2 != '.');
    }
    return pcVar2 + 1;
  }
LAB_002b5704:
  return param_1 + sVar1;
}
