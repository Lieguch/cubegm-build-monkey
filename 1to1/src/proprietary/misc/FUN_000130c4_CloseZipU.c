/* ============================================================
 * CloseZipU   @ 0x000130c4   size=132B   callers=11
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 CloseZipU(gh_u4 *param_1)

{
  TUnzip *this;
  
  if (param_1 == (gh_u4 *)0x0) {
    lasterrorU = 0x10000;
    return 0x10000;
  }
  if (*param_1 != 1) {
    lasterrorU = 0x80000;
    return 0x80000;
  }
  this = (TUnzip *)param_1[1];
  lasterrorU = _ZN6TUnzip5CloseEv(this);
  _ZdlPv(this);
  _ZdlPv(param_1);
  return lasterrorU;
}
