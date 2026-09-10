/* ============================================================
 * run_process.constprop.0   @ 0x0000d628   size=72B   callers=3
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 run_process_constprop_0(undefined4 param_1)

{
  code *pcVar1;
  
  pcVar1 = (code *)dlsym(handle,param_1);
  if (pcVar1 != (code *)0x0) {
    (*pcVar1)();
    return 1;
  }
  printf("find %s process fail \n",param_1);
  return 0;
}
