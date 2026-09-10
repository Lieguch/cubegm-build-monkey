/* ============================================================
 * GetInputInfo   @ 0x0000c0a0   size=168B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 GetInputInfo(char *param_1,undefined4 param_2)

{
  FILE *__stream;
  char *pcVar1;
  char acStack_418 [1028];
  
  __stream = fopen("/proc/bus/input/devices","r");
  if (__stream != (FILE *)0x0) {
    while (pcVar1 = fgets(acStack_418,0x3ff,__stream), pcVar1 != (char *)0x0) {
      pcVar1 = (char *)get_from_line(acStack_418,param_2);
      if ((pcVar1 != (char *)0x0) && (pcVar1 = strstr(pcVar1,param_1), pcVar1 != (char *)0x0)) {
        fclose(__stream);
        return 1;
      }
    }
    close((int)__stream);
  }
  return 0xffffffff;
}
