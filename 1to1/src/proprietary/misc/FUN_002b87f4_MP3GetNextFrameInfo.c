/* ============================================================
 * MP3GetNextFrameInfo   @ 0x002b87f4   size=80B   callers=0
 * module: 06_helix_mp3
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 MP3GetNextFrameInfo(int param_1,gh_u4 *param_2,gh_u4 param_3)

{
  int iVar1;
  
  if (param_1 == 0) {
    return 0xfffffffb;
  }
  iVar1 = xmp3_UnpackFrameHeader((int *)param_1,(char *)param_3);
  if ((iVar1 != -1) && (*(int *)(param_1 + 2000) == 3)) {
    MP3GetLastFrameInfo(param_1,param_2);
    return 0;
  }
  return 0xfffffffa;
}
