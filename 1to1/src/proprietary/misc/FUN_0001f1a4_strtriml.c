/* ============================================================
 * strtriml   @ 0x0001f1a4   size=104B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

byte * strtriml(byte *param_1)

{
  size_t sVar1;
  ushort **ppuVar2;
  byte *__src;
  int iVar3;
  
  sVar1 = strlen((char *)param_1);
  ppuVar2 = __ctype_b_loc();
  __src = param_1;
  for (iVar3 = 0; (ushort)((ushort)(iVar3 <= (int)(sVar1 - 1)) & (*ppuVar2)[*__src] >> 0xd) != 0;
      iVar3 = iVar3 + 1) {
    __src = __src + 1;
  }
  if (iVar3 != 0) {
    strcpy((char *)param_1,(char *)__src);
  }
  return param_1;
}
