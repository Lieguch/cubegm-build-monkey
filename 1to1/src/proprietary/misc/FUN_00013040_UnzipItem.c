/* ============================================================
 * UnzipItem   @ 0x00013040   size=124B   callers=13
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 UnzipItem(int *param_1,int param_2,void *param_3,gh_uint param_4,gh_uint param_5)

{
  if (param_1 != (int *)0x0) {
    if (*param_1 == 1) {
      lasterrorU = TUnzip::Unzip((TUnzip *)param_1[1],param_2,param_3,param_4,param_5);
    }
    else {
      lasterrorU = 0x80000;
    }
    return lasterrorU;
  }
  lasterrorU = 0x10000;
  return 0x10000;
}
