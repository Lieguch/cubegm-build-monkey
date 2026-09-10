/* ============================================================
 * get_value_from_items   @ 0x0001f514   size=108B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

char * get_value_from_items(char *param_1,char *param_2,char *param_3,int param_4)

{
  int iVar1;
  int iVar2;
  
  if (param_4 < 1) {
    if (param_4 != 0) {
      return param_2;
    }
  }
  else {
    iVar2 = 0;
    do {
      iVar1 = strcmp(param_3,param_1);
      iVar2 = iVar2 + 1;
      if (iVar1 == 0) {
        strcpy(param_2,param_3 + 0x32);
        return param_2;
      }
      param_3 = param_3 + 0xfa;
    } while (param_4 != iVar2);
  }
  *param_2 = '\0';
  return param_2;
}
