/* ============================================================
 * get_executable_path   @ 0x0000a438   size=96B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int get_executable_path(char *param_1,char *param_2,size_t param_3)

{
  ssize_t sVar1;
  char *pcVar2;
  
  sVar1 = readlink("/proc/self/exe",param_1,param_3);
  if ((0 < sVar1) && (pcVar2 = strrchr(param_1,0x2f), pcVar2 != (char *)0x0)) {
    strcpy(param_2,pcVar2 + 1);
    pcVar2[1] = '\0';
    return (int)(pcVar2 + 1) - (int)param_1;
  }
  return -1;
}
