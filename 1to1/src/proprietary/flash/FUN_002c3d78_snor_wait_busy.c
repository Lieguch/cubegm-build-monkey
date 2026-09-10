/* ============================================================
 * snor_wait_busy   @ 0x002c3d78   size=136B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* WARNING: Type propagation algorithm not settling */

int snor_wait_busy(int param_1)

{
  int iVar1;
  int iVar2;
  uint *unaff_r6;
  uint *unaff_r7;
  uint local_24 [4];
  
  iVar2 = 0;
  if (0 < param_1) {
    unaff_r7 = local_24;
    unaff_r6 = local_24 + 1;
  }
  local_24[2] = 0;
  local_24[1] = 5;
  if (0 < param_1) {
    do {
      iVar1 = sfc_request(unaff_r6,0,unaff_r7,1);
      iVar2 = iVar2 + 1;
      if ((iVar1 != 0) || ((local_24[0] & 1) == 0)) {
        return iVar1;
      }
      usleep(1);
    } while (param_1 != iVar2);
  }
  return -6;
}
