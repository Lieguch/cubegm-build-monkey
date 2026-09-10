/* ============================================================
 * myStrrstr   @ 0x0002197c   size=176B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

char * myStrrstr(char *param_1,char *param_2)

{
  size_t sVar1;
  size_t sVar2;
  char *pcVar3;
  char *pcVar4;
  char *pcVar5;
  char *pcVar6;
  
  sVar1 = strlen(param_1);
  sVar2 = strlen(param_2);
  if (sVar2 == 0) {
    return param_1;
  }
  if (((int)sVar2 <= (int)sVar1) && (!CARRY4((uint)param_1,sVar1 - sVar2))) {
    pcVar5 = param_1 + (sVar1 - sVar2);
    do {
      if ((int)sVar2 < 1) {
LAB_00021a00:
        *pcVar5 = '\0';
        return pcVar5;
      }
      pcVar6 = pcVar5 + -1;
      if (*param_2 == *pcVar5) {
        pcVar3 = param_2;
        pcVar4 = pcVar5;
        do {
          pcVar4 = pcVar4 + 1;
          if (pcVar4 == pcVar6 + sVar2 + 1) goto LAB_00021a00;
          pcVar3 = pcVar3 + 1;
        } while (*pcVar3 == *pcVar4);
      }
      pcVar5 = pcVar6;
    } while (param_1 <= pcVar6);
  }
  return (char *)0x0;
}
