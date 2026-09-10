/* ============================================================
 * strtrimr   @ 0x0001f150   size=84B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

char * strtrimr(char *param_1)

{
  size_t sVar1;
  ushort **ppuVar2;
  char *pcVar3;
  
  sVar1 = strlen(param_1);
  ppuVar2 = __ctype_b_loc();
  pcVar3 = param_1 + sVar1;
  while (sVar1 = sVar1 - 1, (~sVar1 >> 0x1f & (uint)((*ppuVar2)[(byte)pcVar3[-1]] >> 0xd)) != 0) {
    pcVar3 = pcVar3 + -1;
    *pcVar3 = '\0';
  }
  return param_1;
}
