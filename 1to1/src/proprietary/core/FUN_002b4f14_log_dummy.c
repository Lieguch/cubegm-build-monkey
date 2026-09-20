/* ============================================================
 * log_dummy   @ 0x002b4f14   size=52B   callers=0
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* ★★ 2026-09-20：还原**变参**。Ghidra 把 `log_dummy(int lvl, const char *fmt, ...)` 渲染成
 *    `void log_dummy(gh_uint param_1, gh_u4 param_2) { if (param_1 < 2) return; RARCH_LOG_V(param_2); }`
 *    —— `...` 被整个丢掉（与 `RARCH_LOG` 完全同一类缺陷，见 FUN_00009ed8_RARCH_LOG.c）。
 *
 *    原厂指令证据（@0x002b4f14，size=52B，逐条来自 golden/factory.funcs.json 的 t1）：
 *        cmp  r0, #1               ← if (lvl < 2)
 *        bxls lr                   ←   return;
 *        push {r1, r2, r3}         ← ★ AAPCS32 变参「寄存器保存区」（**只存 r1..r3**，
 *                                     因为 r0=level 已被消费、不需要保存）
 *        push {lr}
 *        sub  sp, sp, #8
 *        add  r1, sp, #16          ← ★ r1 = va_list 指针（指向 &r2）
 *        ldr  r0, [sp, #12]        ← r0 = 第 2 个参数（fmt）
 *        str  r1, [sp, #4]
 *        bl   RARCH_LOG_V          ← ★ 传 (fmt, va_list) **两个**参数
 *      （对照修复前的产物：16B = `cmp r0,#1` / `bxls lr` / `mov r0,r1` / `b RARCH_LOG_V` ⇒
 *        纯尾调用、r1 未设 ⇒ 下游 vfprintf 会把**调用者的 r1 残留值**当 va_list）
 *
 *    ★ 门禁盲区（本轮发现）：`tools/scan_varargs_fns.py` 原判据是 `push {r0,r1,r2,r3}`
 *      （`0xE92D000F`）。本函数的序言是 `push {r1,r2,r3}`（`0xE92D000E`）—— 因为 `r0` 是
 *      level 不需要保存 ⇒ **判据太窄、整族漏掉**。已放宽为「保存 r1..r3 三者」。
 */
void log_dummy(gh_uint param_1, char *param_2, ...)

{
  __gnuc_va_list ap;

  if (param_1 < 2) {
    return;
  }
  __builtin_va_start(ap, param_2);
  RARCH_LOG_V(param_2, ap);
  __builtin_va_end(ap);
  return;
}
