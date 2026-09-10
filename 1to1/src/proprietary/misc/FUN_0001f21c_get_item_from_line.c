/* ============================================================
 * get_item_from_line   @ 0x0001f21c   size=212B   callers=2
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

char * get_item_from_line(gh_u4 param_1,char *param_2)

{
  char *pcVar1;
  size_t sVar2;
  char *pcVar3;
  char *__dest;
  
  pcVar1 = (char *)strtrim();
  sVar2 = strlen(pcVar1);
  if ((0 < (int)sVar2) && (*pcVar1 != '#')) {
    if (*pcVar1 != '[') {
      pcVar3 = strchr(pcVar1,0x3d);
      if (pcVar3 != (char *)0x0) {
        *pcVar3 = '\0';
        __dest = stpcpy(param_2,mainkey);
        strcpy(__dest,pcVar1);
        strcpy(param_2 + 0x32,pcVar3 + 1);
        return param_2;
      }
      return (char *)0x0;
    }
    pcVar3 = strchr(pcVar1,0x5d);
    if (pcVar3 != (char *)0x0) {
      *pcVar3 = '\0';
      pcVar1 = stpcpy(mainkey,pcVar1 + 1);
      pcVar1[0] = '_';
      pcVar1[1] = '\0';
      return param_2;
    }
  }
  return (char *)0x0;
}
