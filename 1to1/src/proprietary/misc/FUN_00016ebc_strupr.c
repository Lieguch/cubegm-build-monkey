/* ============================================================
 * strupr   @ 0x00016ebc   size=76B   callers=7
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

byte * strupr(byte *param_1)

{
  byte bVar1;
  uint uVar2;
  int iVar3;
  __int32_t **pp_Var4;
  byte *pbVar5;
  
  bVar1 = *param_1;
  pbVar5 = param_1;
  while (uVar2 = (uint)bVar1, uVar2 != 0) {
    iVar3 = islower(uVar2);
    if (iVar3 != 0) {
      pp_Var4 = __ctype_toupper_loc();
      *pbVar5 = (byte)(*pp_Var4)[uVar2];
    }
    pbVar5 = pbVar5 + 1;
    bVar1 = *pbVar5;
  }
  return param_1;
}
