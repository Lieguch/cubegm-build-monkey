/* ============================================================
 * sfc_uninit   @ 0x002c43cc   size=40B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

gh_u4 sfc_uninit(void)

{
  /* ★ munmap 只释放映射，**不做设备访问** ⇒ 此处显式去掉 volatile 限定，
   *   否则（`g_sfc_reg` 为设备寄存器基址、声明为 volatile）严格口径会报"丢弃限定符"。 */
  munmap((void *)g_sfc_reg,0x400);
  g_sfc_reg = (void *)0x0;
  return 0;
}
