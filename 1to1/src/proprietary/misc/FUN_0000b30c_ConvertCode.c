/* ============================================================
 * ConvertCode   @ 0x0000b30c   size=232B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

int ConvertCode(gh_u4 param_1,gh_u4 param_2,gh_u4 param_3,gh_u4 param_4,
               void *param_5,size_t param_6)

{
  int iVar1;
  int iVar2;
  int *piVar3;
  gh_u4 local_18;
  gh_u4 local_14 [2];
  
  local_18 = param_4;
  local_14[0] = param_3;
  iVar1 = libiconv_open((gh_byte *)param_2,(gh_byte *)param_1);
  if (iVar1 == -1) {
    iVar2 = -1;
  }
  else {
    memset(param_5,0,param_6);
    iVar2 = libiconv(iVar1,local_14,&local_18,&param_5,&param_6);
    if (iVar2 == -1) {
      piVar3 = __errno_location();
      iVar1 = *piVar3;
      if (iVar1 == 0x16) {
        puts("EINVAL");
        return -1;
      }
      if (iVar1 == 0x54) {
        puts("EILSEQ");
        return -1;
      }
      if (iVar1 == 7) {
        puts("E2BiG");
        return -1;
      }
    }
    else {
      libiconv_close((void *)iVar1);
    }
  }
  return iVar2;
}
