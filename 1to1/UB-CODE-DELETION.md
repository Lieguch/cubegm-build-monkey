# 根因报告：**编译期 UB 让优化器静默删掉整段实现**（2026-09-27）

> 触发：上一轮新加的 `tools/size_coverage_gate.py` 报出 `UpdateROM` 体量 0.115×
> （我方 112 B / 工厂 976 B）。**行为尺判它 PASS** —— 因为输入从没走进那段代码。
> 本文把这一类追到底，并给出**两个真缺陷的根修**与**两道新门禁**。

---

## 一、类的定义（一句话）

**Ghidra 把"一块缓冲"反编译成"多个独立小对象"** ⇒ 源码里只有其中一个被写、
其余在编译器看来**从未被写**（读未初始化值）或**写到越界** ⇒ **UB** ⇒
clang 在 `-O1` 及以上可以据此**判定其后代码不可达并整段删除**。

**而我们的构建一直用 `-w` 屏蔽全部警告** ⇒ 这类 UB 从来没人看见；
**行为尺也看不见**（被删的代码从不执行 ⇒ 两侧"都正常返回"）。
⇒ 这是一个**双盲区**：编译器不报、尺子不测。

---

## 二、两个已证实例

### 2.1 `UpdateROM`（flash 写固件）

| 优化档 | 修前 | 修后 | 工厂 |
|---|---|---|---|
| `-O0` | 2660 B | 3044 B | 976 B |
| `-O1` | **116 B** | 696 B | 976 B |
| `-Os` | **112 B** | **680 B** | 976 B |
| `-O2` | **116 B** | 696 B | 976 B |

复现：`python tools/func_size_probe.py <源文件> <函数名> <工厂字节数>`

**根因（两处叠加，均已修）**

| # | 形态 | 编译器原话 / 证据 |
|---|---|---|
| a | `gh_u1 auStack_158[4]`（假尺寸）却 `memset(auStack_158, 0, 0x130)` | `'memset' will always overflow; destination buffer has size 4, but size argument is 304` |
| b | **一块 3 字节缓冲被拆成三个独立 `char`**：`local_15c / local_15b / local_15a`；只有 `local_15c` 被 `fread` 写过 | 另两个"从未被写"⇒ 读未初始化 ⇒ clang 取"条件恒真" ⇒ **删掉 `fread` 之后整段**（含闪写 + CRC 校验 + 安全区写 + `sync` + `reboot`，约 **864 B**） |

**b 的旁证**：工厂导入 `reboot` / `sync`，我们的产物**两个都没有** —— 因为那条调用链根本没进二进制。

**修法**：把三字节缓冲合并回一块真缓冲（`char local_magic[3]`）并按字节读；
`auStack_158` 声明恢复到真实尺寸 `0x130`。**不改语义、不改判据、不放宽门禁。**

### 2.2 `ReadUSBJoy`（USB 手柄输入）

| 优化档 | 修前 | 修后 | 工厂 |
|---|---|---|---|
| `-O0` | 14744 B | 18496 B | 1196 B |
| `-Os` | **520 B** | **1072 B** | 1196 B |

**根因**：`read(iVar1, auStack_40, 8)` 的目标块被 Ghidra 拆成
`gh_u1 auStack_40[4]` + `short local_3c` + `char local_3a` + `gh_byte local_39`
⇒ 只有 4 字节可见，另三个字段"从未被写" ⇒ 同一 UB。
编译器原话：`warning: variable 'local_3c' is uninitialized when used here [-Wuninitialized]`

**布局取证（**联网核实**，不是猜）**：Linux 内核官方文档 `Documentation/input/joydev/joystick-api.rst`
（[kernel.org](https://origin.kernel.org/doc/html/v5.17/input/joydev/joystick-api.html)）逐字给出：

```c
struct js_event { __u32 time; __s16 value; __u8 type; __u8 number; };   /* 8 字节，偏移 0/4/6/7 */
#define JS_EVENT_BUTTON 0x01    /* button pressed/released */
#define JS_EVENT_AXIS   0x02    /* joystick moved */
```

**反向交叉验证**：我方源码里 `local_3a == '\x02'` 分支使用 `local_3c` 作**轴值**、
`local_3a == '\x01'` 分支使用 `local_39` 作**按钮号** —— 与文档的
`JS_EVENT_AXIS=0x02`（轴）/ `JS_EVENT_BUTTON=0x01`（按钮）**逐项吻合**；
再加上 `read(..., 8)` 的字节数与 `local_3c` 作 `short` 的宽度 ⇒ 偏移 0/4/6/7 与对象尺寸 8 B
由**独立来源**证实（Ghidra 栈名序号随地址升高而减小的推断与之自洽）。

---

## 三、类的规模与**闭环**（机械普查，不是抽样）

`tools/ub_census.py`（`-fsyntax-only` 过全部 **213** 个专有源文件，只开三类高危警告：
对象越界 / 数组越界 / 字符串越界）：

| 阶段 | 命中文件数 |
|---|---|
| 首轮普查 | **6** |
| 修掉 `UpdateROM` 后 | 5 |
| **全部修完后** | **0** ✅ |

**已修的 6 处**（同一类：Ghidra 把一块缓冲拆小 / 声明假尺寸）：

| # | 文件 | 形态 | 修法 |
|---|---|---|---|
| 1 | `flash/FUN_0000ac44_UpdateROM.c` | 3 字节缓冲拆成 3 个 `char` + `[4]` 却 memset 0x130 | 合并为 `char local_magic[3]`；缓冲恢复 `0x130` |
| 2 | `input/FUN_0000c150_ReadUSBJoy.c` | 8 字节 `struct js_event` 拆成 4 份 | 合并为 `gh_u1 ev_buf[8]` + 三个偏移视图 |
| 3 | `misc/FUN_002b4e20_gpsp_unzip.c` | `[296]` 却 memset 0x130(=304) | 恢复 `[0x130]` |
| 4 | `core/FUN_002b7510_run_game.c` | `int local_158` 当 0x130 缓冲用 | 恢复 `gh_u1 local_158[0x130]` |
| 5 | `core/FUN_00016f08_FilePreEmu.c` | 同上 | 同上 |
| 6 | `mui/FUN_0001bf80_mui_DisplayGameSum.c` | `sprintf` 写 8 字节进 4 字节 `gh_u4` | 恢复 16 字节缓冲 |
| 7 | `mui/FUN_000171f8_mui_LoadSetting.c` + `globals.h` | 4 字节指针却 memset 0x50 | 恢复 `gh_u1 DAT_003af2bc[0x50]` + 显式转换 |

**结果**：`ub_census` **命中 0**；`link_full.sh` 的 `exit 18` 门禁通过。

### 3.1 端到端验证（全量重编后实测）

| 门禁 | 结果 |
|---|---|
| 专有对象编译 | **213/213 成功** |
| **体量覆盖门禁** | **SHORT 0**（原 2 个缺体绝迹） |
| **动态导入** | **`reboot` / `sync` 由"缺失"变为"与工厂一致"** ✅ ← `UpdateROM` 修复的直接证据 |
| ABI | PASS |
| 行为尺 | PASS 727 ｜ DIVERGE 46 ｜ TRUNC 5 ｜ SKIP 0（自洽 778 ✓） |

---

## 四、本轮新增的两道门禁（钉进 `link_full.sh`，fail-closed）

| 门禁 | 判据 | 退出码 | 防的是什么 |
|---|---|---|---|
| `tools/size_coverage_gate.py` | 共有函数 `ours_size/factory_size < 0.5` ⇒ SHORT | **17** | **后果**：空壳/缺体（行为尺看不见） |
| `tools/ub_census.py` | 高危 UB 警告命中数须为 0 | **18** | **成因**：UB 让优化器删代码（编译器可见、但被 `-w` 屏蔽） |

`size_coverage_gate` 自证 8 条锚点 0 失败；`ub_census` 可直接复跑。

---

## 五、边界与诚实声明

1. 修后 `UpdateROM` = 680 B（工厂 976 B，**0.697×**）、`ReadUSBJoy` = 1072 B（工厂 1196 B，**0.896×**）。
   **仍不是 1.0×** —— 剩余差异来自编译器族（clang vs GCC 6.2），本轮**没有**把它归零。
2. 本轮**没有**上机验证这两个函数在设备上的行为（闪写与手柄都是硬件相关路径）。
3. `ub_census` 只覆盖三类**高危** UB 警告；Ghidra 产物里大量 `-Wuninitialized` 属常态语义，
   **未**纳入判据（否则闸门会被噪声淹没）。这是**已知的判据边界**，不是"已全覆盖"。
4. 修后的改动**尚未上机**：`UpdateROM`（闪写/reboot）与 `ReadUSBJoy`（手柄）都是硬件相关路径，
   设备行为未验证；本轮只验证了**体量恢复 + 导入符号与工厂一致 + 无回归**。
5. `DAT_003af2bc` 的真实对象尺寸（0x50）取自 Ghidra 的 `memset` 实参；若原始 `memset` 长度
   本身被 Ghidra 读错，则该尺寸也需要重新取证 —— 本轮**未**交叉验证这一点。

---

## 六、纪律

> **41.** 编译告警**不得**用 `-w` 一律屏蔽：UB 类告警必须定点开启并作为门禁 ——
> 被 `-w` 吞掉的不是噪声，是"优化器删代码"的授权书。
> **42.** **"行为尺 PASS" ≠ "代码在"**。任何 PASS 都要有**体量覆盖**背书；
> 两道门禁互为交叉验证（成因侧 + 后果侧），缺一不可。
