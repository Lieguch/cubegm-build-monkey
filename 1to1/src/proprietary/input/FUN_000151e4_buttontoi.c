/* ============================================================
 * buttontoi   @ 0x000151e4   size=552B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

long buttontoi(char *param_1)

{
  int iVar1;
  long lVar2;
  char cVar3;
  
  cVar3 = *param_1;
  if (cVar3 == 'A') {
    if (param_1[1] == '\0') {
      return 0x2000;
    }
  }
  else if ((cVar3 == 'B') && (param_1[1] == '\0')) {
    return 0x4000;
  }
  iVar1 = strcmp(param_1,"SELECT");
  if (iVar1 == 0) {
    return 1;
  }
  iVar1 = strcmp(param_1,"START");
  if (iVar1 == 0) {
    return 8;
  }
  if (((cVar3 == 'U') && (param_1[1] == 'P')) && (param_1[2] == '\0')) {
    return 0x10;
  }
  iVar1 = strcmp(param_1,"DOWN");
  if (iVar1 == 0) {
    return 0x40;
  }
  iVar1 = strcmp(param_1,"LEFT");
  if (iVar1 == 0) {
    return 0x80;
  }
  iVar1 = strcmp(param_1,"RIGHT");
  if (iVar1 == 0) {
    return 0x20;
  }
  if (cVar3 == 'X') {
    if (param_1[1] == '\0') {
      return 0x1000;
    }
    goto LAB_00015338;
  }
  if (cVar3 == 'Y') {
    if (param_1[1] == '\0') {
      return 0x8000;
    }
    goto LAB_00015338;
  }
  if (cVar3 != 'T') goto LAB_00015338;
  cVar3 = param_1[1];
  if (cVar3 == 'R') {
    cVar3 = param_1[2];
    if (cVar3 != '1') {
      if (cVar3 == '2') {
        if (param_1[3] == '\0') {
          return 0x200;
        }
        goto LAB_00015338;
      }
      goto LAB_00015330;
    }
  }
  else {
    if (cVar3 == 'L') {
      cVar3 = param_1[2];
      if (cVar3 != '1') {
        if (cVar3 == '2') {
          if (param_1[3] == '\0') {
            return 0x100;
          }
          goto LAB_00015338;
        }
        if (cVar3 != '3') goto LAB_00015338;
      }
      if (param_1[3] == '\0') {
        return 0x400;
      }
      goto LAB_00015338;
    }
    if (cVar3 != 'R') goto LAB_00015338;
    cVar3 = param_1[2];
LAB_00015330:
    if (cVar3 != '3') goto LAB_00015338;
  }
  if (param_1[3] == '\0') {
    return 0x800;
  }
LAB_00015338:
  iVar1 = strcmp(param_1,"RESET");
  if (iVar1 == 0) {
    return -0x80000000;
  }
  lVar2 = strtol(param_1,(char **)0x0,10);
  return lVar2;
}
