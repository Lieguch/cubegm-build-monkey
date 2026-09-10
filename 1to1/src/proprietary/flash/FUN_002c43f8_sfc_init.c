/* ============================================================
 * sfc_init   @ 0x002c43f8   size=152B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 sfc_init(void)

{
  gh_u4 *puVar1;
  int __fd;
  gh_u4 uVar2;
  
  __fd = open("/dev/mem",2);
  if (__fd < 0) {
    uVar2 = 0xffffffff;
  }
  else {
    g_sfc_reg = mmap((void *)0x0,0x400,3,1,__fd,0x10208000);
    if (g_sfc_reg == (gh_u4 *)0xffffffff) {
      uVar2 = 0xfffffffe;
    }
    else {
      close(__fd);
      puVar1 = g_sfc_reg;
      uVar2 = 0;
      *g_sfc_reg = 0;
      if (3 < (puVar1[0xb] & 0xffff)) {
        puVar1[0x22] = 1;
      }
    }
  }
  return uVar2;
}
