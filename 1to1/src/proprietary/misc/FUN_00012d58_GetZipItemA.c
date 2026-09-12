/* ============================================================
 * GetZipItemA   @ 0x00012d58   size=104B   callers=6
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 GetZipItemA(int *param_1,int param_2,ZIPENTRY *param_3)

{
  if (param_1 == (int *)0x0) {
    lasterrorU = 0x10000;
    return 0x10000;
  }
  if (*param_1 != 1) {
    lasterrorU = 0x80000;
    return 0x80000;
  }
  lasterrorU = _ZN6TUnzip3GetEiP8ZIPENTRY((TUnzip *)param_1[1],param_2,param_3);
  return lasterrorU;
}
