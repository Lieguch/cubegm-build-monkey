/* ============================================================
 * ClearBuffer   @ 0x002bdefc   size=32B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void ClearBuffer(gh_u1 *param_1,int param_2)

{
  gh_u1 *puVar1;
  gh_u1 *puVar2;
  
  if (param_2 < 1) {
    return;
  }
  puVar2 = param_1;
  do {
    puVar1 = puVar2 + 1;
    *puVar2 = 0;
    puVar2 = puVar1;
  } while (puVar1 != param_1 + param_2);
  return;
}
