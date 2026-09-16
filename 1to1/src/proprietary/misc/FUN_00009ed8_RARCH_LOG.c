/* ============================================================
 * RARCH_LOG   @ 0x00009ed8   size=44B   callers=46
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* ★★ Ghidra 把变参函数渲染成「单参数」：本例把 `RARCH_LOG(const char *fmt, ...)` 渲染成
 *    `void RARCH_LOG(undefined4 param_1) { RARCH_LOG_V(param_1); }` —— `...` 被整个丢掉。
 *
 *    为什么必须还原（P5 第五个真实分歧，全部有运行时证据）：
 *      `RARCH_LOG_V(char *fmt, __gnuc_va_list ap)` 需要**两个**参数。丢掉 `...` 后
 *      `RARCH_LOG_V(param_1)` 只传 r0 ⇒ **r1（va_list）成了调用者的残留值**。
 *      实测：`main_Menu()` 里 `RARCH_LOG("root_path:%s\n", root_path)` 被调用时 r1 = root_path(0x3e1398)
 *      ⇒ `vfprintf(stdout, fmt, ap=0x3e1398)` 把**字符串自己的内存**当成参数列表
 *      ⇒ `%s` 取到的"指针" = `0x6364732f`（恰是 "/sdc" 的**内容**）
 *      ⇒ 崩在 libc `strlen`（shim 现场：`r1 = r0 & ~7`、`r4 = 7` 对齐掩码、
 *        `[sp+4] = _IO_2_1_stdout_`；`lr` 也在 libc 内 ⇒ 是 printf 族的内部调用）
 *      ⇒ 观测窗口停在 18/32，进不了 `main_Menu` 正文。
 *
 *    原厂指令证据（0x9ed8，size=44B）：
 *        9ed8: push {r0, r1, r2, r3}   ← AAPCS32 变参「寄存器保存区」
 *        9ee4: add  r1, sp, #20        ← r1 = va_list 指针
 *        9ee8: ldr  r0, [sp, #16]      ← r0 = 第 1 个参数（格式串）
 *        9ef0: bl   RARCH_LOG_V        ← 传 (fmt, va_list) **两个**参数
 *      （对照我们修复前的产物：`push {fp,lr}` / `pop {fp,lr}` / `b RARCH_LOG_V` = 纯尾调用，r1 未设）
 *
 *    ★ 同类函数在全 .text 里只有 4 个（`push {r0,r1,r2,r3}` 特征）：RARCH_LOG / spi_printf /
 *      mxml_error / _mxml_strdupf。`spi_printf` 此前已按原形还原，**本函数被漏掉**；
 *      现已新增门禁 `tools/scan_varargs_fns.py` 逐个人工核对，防止再漏。 */
void RARCH_LOG(char *param_1, ...)

{
  __gnuc_va_list ap;

  __builtin_va_start(ap, param_1);
  RARCH_LOG_V(param_1, ap);
  __builtin_va_end(ap);
  return;
}
