/* ============================================================
 * OpenZipU   @ 0x00012cd0   size=128B   callers=13
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 * OpenZipU(void *param_1,gh_uint param_2,gh_uint param_3)

{
  TUnzip *this;
  gh_u4 *puVar1;
  
  this = operator_new(0x240);
  *(gh_u4 *)(this + 0x138) = 0xffffffff;
  *(gh_u4 *)this = 0;
  *(gh_u4 *)(this + 4) = 0xffffffff;
  lasterrorU = XUnzip_Open(this,param_1,param_2,param_3);
  if (lasterrorU == 0) {
    puVar1 = operator_new(8);
    puVar1[1] = (gh_u4)this;
    *puVar1 = 1;
    return puVar1;
  }
  operator_delete(this);
  return (gh_u4 *)0x0;
}
