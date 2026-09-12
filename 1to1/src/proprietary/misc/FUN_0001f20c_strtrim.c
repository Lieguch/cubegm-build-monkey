/* ============================================================
 * strtrim   @ 0x0001f20c   size=16B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

char * strtrim(void) /* 原厂：bl strtriml → 尾调用 strtrimr，r0 = strtrimr 结果 */

{
  strtriml();
  return (char *)strtrimr();
}
