/* ============================================================
 * OpenZipU   @ 0x00012cd0   size=128B   callers=13
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 * OpenZipU(void *param_1,uint param_2,uint param_3)

{
  TUnzip *this;
  undefined4 *puVar1;
  
  this = operator_new(0x240);
  *(undefined4 *)(this + 0x138) = 0xffffffff;
  *(undefined4 *)this = 0;
  *(undefined4 *)(this + 4) = 0xffffffff;
  lasterrorU = TUnzip::Open(this,param_1,param_2,param_3);
  if (lasterrorU == 0) {
    puVar1 = operator_new(8);
    puVar1[1] = this;
    *puVar1 = 1;
    return puVar1;
  }
  operator_delete(this);
  return (undefined4 *)0x0;
}
