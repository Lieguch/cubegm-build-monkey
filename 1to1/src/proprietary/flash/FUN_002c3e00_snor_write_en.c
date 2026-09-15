/* ============================================================
 * snor_write_en   @ 0x002c3e00   size=56B   callers=4
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

void snor_write_en(void)

{
  gh_u4 cmd[2];  /* ★★ 原厂：命令行是**连续的 2 个字**（cmd[0]=命令，cmd[1]=参数，sfc_request 会对 cmd[1] 置 bit1）。
   *    必须写成数组：拆成两个相邻标量时，编译器可以按任意顺序摆放，`cmd[0]+4` 就可能越出这对
   *    标量、砸到帧里别的东西 —— 实测把调用者保存的 fp 打成了 fp|2，导致上层 `sub sp,fp,#28`
   *    算出错帧、`pop {…,pc}` 跳到坏地址。工厂原版是 `str lr,[sp]` + `str lr,[sp,#4]`，即帧内 8B 数组。 */
  
  cmd[1] = 0;
  cmd[0] = 6;
  sfc_request(cmd,0,0,0);
  return;
}
