/* ============================================================
 * strtrim   @ 0x0001f20c   size=16B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* ★ 2026-09-30 修（§0.45）：工厂机器码逐条为
 *      push {r4, lr} ; bl strtriml ; pop {r4, lr} ; b strtrimr
 *   两个被调函数的**参数就是 r0**（`strtriml: mov r5, r0 … pop {…,pc}` 返回原 r0；
 *   随后 `b strtrimr` 用的仍是该 r0）⇒ **参数必须透传**。
 *   旧重建写成 `char *strtrim(void)` 并把两个调用都写成 0 参 ⇒ **参数被丢弃**
 *   （proto.h 里"K&R：strtrim 内以 0 参尾调用"是**误读**）。这是语义缺失，不是判据问题。 */
char * strtrim(char *param_1)

{
  strtriml((gh_byte *)param_1);
  return (char *)strtrimr(param_1);
}
