/* ============================================================
 * ShareMemCreat   @ 0x0000a774   size=132B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 * ShareMemCreat(void)

{
  gh_u4 *puVar1;
  
  shmid = shmget(0x4d2,8,0x3b6);
  if (shmid == -1) {
    puts("shmget failed");
  }
  else {
    puVar1 = (gh_u4 *)shmat(shmid,(void *)0x0,0);
    shm = puVar1;
    if (puVar1 != (gh_u4 *)0xffffffff) {
      *puVar1 = 1;
      puVar1[1] = 0;
      return puVar1;
    }
    puts("shmat failed");
  }
  return (gh_u4 *)0xffffffff;
}
