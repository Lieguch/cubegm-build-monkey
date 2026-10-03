# 簇 A 修复判据（跑云上前先写死，事后只许回填数字）

日期：2026-10-03 ｜ 手段：diff_exec 行为尺（非体积代理） ｜ 云上验证前置

## 一、根因（工厂汇编铁证，非推断）

| 证据 | 行 | 内容 |
|---|---|---|
| 工厂 FilePreEmu | golden/factory.funcs.json:28788-28789 | `mov r8, r0` → `bl @GetFilenameExt`（r0 未覆盖 ⇒ GetFilenameExt(param_1) 传 1 参）|
| 工厂 run_game | golden/factory.funcs.json:1406674/1406682 | `mov r7, r0` → `bl @GetFilenameExt`（r0 未覆盖 ⇒ GetFilenameExt(param_1) 传 1 参）|
| 工厂 FilePreEmu 第二处 | :28910-28914 | `add sl, sp, #12` → `mov r0, sl` → `bl @GetFilenameExt`（传栈缓冲 1 参）|
| 工厂 run_game 第二处 | :1406805-1406810 | `mov r0, sl` → `bl @GetFilenameExt`（传栈缓冲 1 参）|

⇒ **工厂全部 4 处 GetFilenameExt 调用均为 1 参**。

我方缺陷（PROJECT-MEMORY 已登记"同一规则禁止写两处"的同族事故）：
- `src/proprietary/core/FUN_00016f08_FilePreEmu.c:25` = `GetFilenameExt()` **0 参**
- `src/proprietary/core/FUN_002b7510_run_game.c:32`  = `GetFilenameExt()` **0 参**
- `src/compat/proto.h:91`  = `extern gh_u4 FilePreEmu();`（K&R 空参）
- `src/compat/proto.h:210` = `extern char * GetFilenameExt();`（K&R 空参）

diff_exec 行为铁证（report/ladder/report__ab_diff_zig-Os.txt:22-23）：
- 工厂 FilePreEmu[misc] `calls_ext=['strlen','strcpy','strcmp'×8]`（进入 GetCoreIndex 循环）
- 我方 FilePreEmu[misc] `calls_ext=['strlen','strcpy']`（无 strcmp），22 条指令早死于 `R!@0x0 sz=1`

## 二、本轮改动（确定性，机器码级可证伪）

1. `FilePreEmu.c:25`  `GetFilenameExt()`        → `GetFilenameExt(param_1)`
2. `run_game.c:32`    `GetFilenameExt()`        → `GetFilenameExt(param_1)`
3. `proto.h:91`       `FilePreEmu()`            → `FilePreEmu(char *param_1)`
4. `proto.h:210`      `GetFilenameExt()`        → `GetFilenameExt(char *param_1)`

（真原型化后，任何漏参调用点都会在 link_audit 严格编译门禁直接报错，与 proto.h 内
 stbtt_* / mxmlLoadFile 那两批修复同族。）

## 三、预登记判据（跑云上前写死）

- **C1 编译门禁**：link_audit 重编 proprietary = **213/213**，0 fail。
  （真原型化 GetFilenameExt 后，若还有遗漏的 0 参调用点，这里会 FAIL —— 那是发现的信号，不是坏信号。）
- **C2 簇 A 行为收敛**：diff_exec 定点（`--fn FilePreEmu` / `--fn SeletEmuCore`）：
  我侧 FilePreEmu[misc] 的 `calls_ext` 从 `['strlen','strcpy']` 变为**出现 strcmp**（进入 GetCoreIndex 循环），
  向工厂 `['strlen','strcpy','strcmp'×8]` 收敛；或该函数从前 80 DIVERGE 清单消失（转 PASS / 内联等价 INFO）。
- **C3 不引入新发散**：全量 `zig-Os` 腿汇总 `DIVERGE ≤ 18`（上一轮基线 18）。
- **反证条件**：若 C2 不收敛（calls_ext 仍无 strcmp）且 C1 通过 ⇒ 传参**不是**唯一的簇 A 根因，
  须回到 default_core_list（@0x003b0254）数据落位/GetCoreIndex 表读路径另找，**不得**据此宣称已修。

## 四、回填区（事后填，判据不改）

| 判据 | 结果 | 判定 |
|---|---|---|
| C1 link_audit | （待填） | |
| C2 簇A收敛 | （待填） | |
| C3 DIVERGE总数 | （待填） | |
## 六、回填结果（2026-10-03 云上 REBUILD=5 单腿 zig-Os，产物 sha=eb549c69）

| 判据 | 结果 | 判定 |
|---|---|---|
| C1 link_audit | 213/213，0 fail | ✅ 编译门禁通过（传参修复合法） |
| C2 簇A收敛 | 我方 FilePreEmu[misc] calls_ext **仍=['strlen','strcpy']**（无 strcmp），死亡 R!@0x0 sz=1 | ❌ **未收敛** |
| C3 DIVERGE总数 | 18（基线 18，未变） | 无改善 |

**⇒ 反证条件命中**：传参不是簇 A 唯一根因。新根因方向见 `HANDOFF-2026-10-03.md` §5：
我方 `GetCoreIndex` 的 GOT 条目值 = `0x003b0134`（占位符号）≠ `default_core_list` 符号地址 `0x003b0254`，
差 0x120。属"刻度 A 工厂数据符号依赖"的具体实例。
