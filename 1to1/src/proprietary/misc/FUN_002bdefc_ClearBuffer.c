/* ============================================================
 * ClearBuffer   @ 0x002bdefc   size=32B   callers=1
 * module: 01_main_emurun_joystick
 * ============================================================ */

/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */
#include "ghidra_compat.h"
#include "globals.h"
#include "proto.h"

/* ★★★ 2026-10-05（第 144 轮）编译器保真属性 —— 根因级修复，勿删
 *
 * 【现象】工厂 ClearBuffer = 0x2bdefc / 32B / 8 条指令的**逐字节 strb 循环**：
 *     2bdefc: cmp r1,#0 / bxle lr / add r1,r0,r1 / mov r3,#0
 *     2bdf0c: strb r3,[r0],#1 / cmp r0,r1 / bne ⇒ 逐字节
 *   我方同函数只有 20B，且是 **memset 尾调用**（`b <memset>`，零 strb）。
 *
 * 【根因】本文件 C 源码是**正确的 do-while 逐字节循环**（见下），
 *   但 clang/clang-loop-idiom 把"存 0 的字节循环"整体识别成 memset 并替换掉函数体。
 *   ⇒ 差异是**编译器优化决策**，不是源码缺失（Ghidra 反编译已 1:1 还原）。
 *
 * 【为什么不能用 -fno-builtin-memset】第 144 轮全量 A/B 实测（云开发）：
 *   腿 A 现状 `-Os`               → PASS 770 / DIVERGE 17
 *   腿 B `-Os -fno-builtin-memset` → PASS 768 / DIVERGE **19**（净恶化 +2）
 *   新增发散 = stbtt__h_prefilter / stbtt__v_prefilter，收敛 = **0**
 *   原因：`-fno-builtin-memset` 只阻止编译器**自己合成** memset 调用；
 *   而这里是 clang 在**被调用函数体内部**做 idiom 识别（memcpy/memset 展开），
 *   flag 管不到 ⇒ 对本函数零效应，只误伤 stb 的两个 prefilter。
 *   ⇒ 全局/细粒度 flag 方案已否决（PROGRESS 第 144 轮 P0 判据）。
 *
 * 【正解】clang 官方函数级属性 `no_builtin("memset")`（LLVM ≥ 11），
 *   作用域**仅限本函数体**、零全局影响，正是"定点修法"。
 *   云端单变量实测：加属性后 ClearBuffer 恢复 7 条 strb 循环（memset=0 / strb=1）。
 *
 * 【可移植性】属性由 clang 前端校验。zig cc 走的就是 clang 前端
 *   （第 144 轮云端实测：`zig cc -Os` + 本属性 ⇒ 成功恢复 strb 循环），
 *   故此处**不排除 zig**。非 clang 编译器按 C11 规则忽略 unknown attribute
 *   （可能告警），语义不变 ⇒ 对 gcc 腿（工厂同族对照腿）安全。
 */
#if defined(__clang__)
#define CGM_NO_MEMSET_IDIOM __attribute__((no_builtin("memset")))
#else
#define CGM_NO_MEMSET_IDIOM
#endif

void ClearBuffer(gh_u1 *param_1,int param_2) CGM_NO_MEMSET_IDIOM

{
  gh_u1 *puVar1;
  gh_u1 *puVar2;
  
  if (param_2 < 1) {
    return;
  }
  puVar2 = param_1;
  do {
    puVar1 = puVar2 + 1;
    *puVar2 = 0;
    puVar2 = puVar1;
  } while (puVar1 != param_1 + param_2);
  return;
}
