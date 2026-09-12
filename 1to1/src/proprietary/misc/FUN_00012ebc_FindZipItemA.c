/* ============================================================
 * FindZipItemA   @ 0x00012ebc   size=124B   callers=9
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 FindZipItemA(gh_u4 *param_1,char *param_2,gh_uchar param_3,int *param_4,void *param_5)

{
  if (param_1 != (gh_u4 *)0x0) {
    if (*param_1 == 1) {
      lasterrorU = _ZN6TUnzip4FindEPKchPiP8ZIPENTRY((TUnzip *)param_1[1],param_2,param_3,param_4,(ZIPENTRY *)param_5);
    }
    else {
      lasterrorU = 0x80000;
    }
    return lasterrorU;
  }
  lasterrorU = 0x10000;
  return 0x10000;
}
