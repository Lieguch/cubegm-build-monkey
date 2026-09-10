/* ============================================================
 * ShareMemClose   @ 0x0000a80c   size=68B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

undefined4 ShareMemClose(void)

{
  int iVar1;
  undefined4 uVar2;
  
  iVar1 = shmdt(shm);
  if (iVar1 == -1) {
    puts("shmdt failed");
    uVar2 = 0xffffffff;
  }
  else {
    uVar2 = 0;
  }
  return uVar2;
}
