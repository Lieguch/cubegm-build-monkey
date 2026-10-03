# P2 `.dynsym` 符号对齐 · 判据（先写死，跑云上前落盘）

日期：2026-10-03 ｜ 手段：工厂汇编铁证 + 产物 .dynsym 对拍（自写 ELF 解析器）

## 一、根因（工厂汇编铁证，非推断）

工厂 `strupr`（golden/factory.funcs.json @0x16ebc，19 条指令）：
```
 6  mov r0, r4
 7  bl @islower@plt               ← 调用**真** islower 外部函数
 8  cmp r0, #0
 9  beq @strupr+0x38
10  bl @__ctype_toupper_loc@plt   ← 调用 __ctype_toupper_loc 外部函数
```
⇒ 工厂 `.dynsym` 含 `islower` 与 `__ctype_toupper_loc` 两个动态符号。

我方 `src/proprietary/misc/FUN_00016ebc_strupr.c:23` 写 `islower(uVar2)`，
但 `ghidra_compat.h:15` 直接 `#include <ctype.h>` ⇒ glibc 把 `islower` 定义成**宏**
`((*__ctype_b_loc())[c] & 0x200)` ⇒ zig cc 把它**内联成 __ctype_b_loc 表查**，
产物 `.dynsym` 只有 `__ctype_b_loc`，**缺 `islower`**。这与 AUDIT §G3 的
"islower 工厂有，我方缺（可能被内联/静态化）"完全吻合。

## 二、本轮改动（确定性）

`strupr.c:23`：`islower(uVar2)` → `(islower)(uVar2)`（圆括号抑制函数式宏，强制走真外部函数）。

## 三、预登记判据（跑云上前写死）

- **D1 编译门禁**：link_audit 重编 proprietary = **213/213**，0 fail。
- **D2 符号收敛**：我方产物 `.dynsym` 出现 `islower`（此前缺）；
  `__ctype_toupper_loc` 保持存在（工厂也有）；`__ctype_b_loc` 出现次数**不因本改动增加**。
- **D3 不引入新发散**：全量 `zig-Os` 腿汇总 `DIVERGE ≤（簇 A 收敛后的基线）`，
  且 `strupr` 自身不新增 DIVERGE。
- **反证条件**：若 D2 不满足（`islower` 仍未出现）⇒ 圆括号抑制无效，
  须改为 `#undef islower` + 显式声明 `extern int islower(int)`（或确认 zig 自带 ctype.h 是否含真函数）。

## 四、豁免登记（AUDIT §G3 已定性为编译器/glibc 版本习语，不产生行为差异）

`__strdup`（工厂用 glibc 内部符号）/ `__gmon_start__` / `_ITM_*` / `_Jv_RegisterClasses`（GCC 弱符号）
/ 我方多出的 `strdup`（glibc 新旧导出差异）—— 登记进 GAP 豁免清单即可，**不改源码**。

## 五、回填区（事后填，判据不改）

| 判据 | 结果 | 判定 |
|---|---|---|
| D1 link_audit | （待填） | |
| D2 符号收敛 | （待填） | |
| D3 DIVERGE | （待填） | |
