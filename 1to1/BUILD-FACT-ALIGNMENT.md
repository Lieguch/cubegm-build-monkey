# 构建事实对齐（2026-09-28）

> 触发：接管链接后 `.dynsym` 仍有 **8+6 项**双向差异。逐项追下去，发现它们**不是随机的**，
> 而是由三条**构建事实**决定的。本文每条都给出**可复现的单变量实验**。

---

## 〇、结论表

| # | 事实 | 判定方法（可复现） | 我方旧构建 | 对齐方式 |
|---|---|---|---|---|
| 1 | 工厂用**真 glibc 2.24 头** | mxml 单变量：zig 头 → `putc/getc`；真头 → **`_IO_putc`/`_IO_getc`** | zig 自带 glibc 头 | `-I <bootlin63 sysroot>/usr/include` |
| 2 | 工厂优化档 **≥ -O1（非 -Os）** | 同源四路：真头 **-Os** → `strdup`；真头 **-O1/-O2** → **`__strdup`** | `-Os`（专有）/ `-O1`（上游） | 专有与上游 → `-O2` |
| 3 | GCC 不做 `strcmp(x,"lit")==0` → `bcmp` 变换，**clang 会做** | 同一份 `main.c`：默认 → `bcmp`（r2=长度+1）；`-fno-builtin-strcmp` → **`strcmp`** | 未加该开关，`main`/`mui_InitFont` 产出 `bcmp` | 加 `-fno-builtin-strcmp` |

---

## 一、事实 1/2：头文件 + 优化档（mxml 单变量，四路对照）

`src/upstream/mxml/mxml-file.c`，同工具链、同 flags，只改**头文件**与**优化档**：

| 头文件 | 优化档 | `putc`/`getc` | `strdup` |
|---|---|---|---|
| zig 自带 glibc 头 | `-Os` | `getc` / `putc` | `strdup` |
| zig 自带 glibc 头 | `-O2` | `getc` / `putc` | `strdup` |
| **真头** | `-Os` | **`_IO_getc` / `_IO_putc`** ✓ | `strdup` |
| **真头** | `-O1` | **`_IO_getc` / `_IO_putc`** ✓ | **`__strdup`** ✓ |
| **真头** | `-O2` | **`_IO_getc` / `_IO_putc`** ✓ | **`__strdup`** ✓ |

工厂导入的正是 `_IO_putc` / `_IO_getc` / `__strdup` ⇒ **两个变量必须同时对齐**，缺一不可。

机制（文档级证据，glibc 2.24 `features.h:380-385`，逐字）：

```c
#if __GNUC_PREREQ (2, 7) && defined __OPTIMIZE__ \
    && !defined __OPTIMIZE_SIZE__ && !defined __NO_INLINE__ \
    && defined __extern_inline
# define __USE_EXTERN_INLINES  1
```

⇒ `-Os` 定义 `__OPTIMIZE_SIZE__` ⇒ 关掉 `string.h` 的 extern-inline ⇒ `strdup` 不内联。
（`stdio.h` 的 putc/getc 走另一处门控，故 `-Os` 也内联 —— 两件事的开关不同，实测印证。）

★ 这也**推翻**了我在第 73 轮的做法：把 `_IO_putc` 归因为「工具链头裁剪」并就地放弃追查。
真正的结论是「**头文件 + 优化档**」，而 `zig cc` 换头即可做到，**不需要等 Bootlin 的 GCC**。

## 二、事实 3：`bcmp` 是 clang 对 `strcmp(常量)` 的合法优化

`src/proprietary/main/FUN_00009b58_main.c:51,56` 两处 `strcmp(autorunfile,"...")`，
我方对象里是 `bl bcmp` 且 **`r2 = 0x11 = 17`（字面量长度+1）**、`r2 = 0xe = 14`：

```
0x12c ldr  r1, [pc, #0xb0]   ; r1 = "/USBJoystickTest"
0x130 mov  r2, #0x11         ; r2 = 17
0x140 bl   bcmp              ; ← strcmp(x,"lit")==0 ⇒ bcmp(x,"lit",len+1)
```

单变量（同一份 `main.c`）：

| flags | 比较符号 |
|---|---|
| 默认 | **`bcmp`**（且 `strcmp` 导入**消失**） |
| `-fno-builtin-strcmp` | **`strcmp`** ✓（与工厂一致） |
| `-fno-builtin` | `strcmp` |

## 三、事实 3 的连带：尺子的 `libc_model` 别名表**漏了两个**

按名字查模型 ⇒ 一侧建模、另一侧不建模 ⇒ **假发散**。用工厂**实际导入的 113 个符号**对账
（新工具 `tools/model_coverage.py`）后补上：

| 别名 | 规范化到 | 为什么会需要 |
|---|---|---|
| `_IO_putc` | `putc` | 工厂导入 `_IO_putc`；模型此前**只建了 `_IO_getc`**（漏了 putc） |
| `bcmp` | `memcmp` | clang 变换产生；工厂侧是 `strcmp` ⇒ 只有我方未建模 |

★ 顺带揪出一条**已腐烂的自证锚点**：旧代码用手写集合
`impl = {... 'malloc','free','getc'}` 断言"别名目标都被实现" —— 它把 `getc` 列成已实现，
而模型里**根本没有 getc 处理分支** ⇒ 断言**恒真、从未生效**（补 `_IO_putc` 后才第一次变红）。
已改为**从模型源码机械推导**已实现名（`if name == 'x'` / `if name in (...)`），并加
`NOT_MODELLED` 显式列出"故意不建模"的目标（不得静默）。自证 **34 → 37 条，失败 0**。

## 四、头集合的**顺序**必须正确（两次失败换来的）

直接 `-I <bootlin sysroot>/usr/include` 会连撞两个墙（都已实测）：

| 失败 | 报错 | 原因 | 解法 |
|---|---|---|---|
| 1 | `undefined symbol: libiconv_close` / `converters.h: field has incomplete type 'struct iconv_fallbacks'` | `-I<glibc 头>` 排在**组件自己的 `-I` 之前** ⇒ 盖住 libiconv 自己的 `iconv.h`（glibc 也有同名 `iconv.h`） | 组件的 `-I` 放**最前**（等价 GCC 的「用户 `-I`」） |
| 2 | `error: function-like macro '__GLIBC_USE' is not defined`（zig 的 `general-glibc/limits.h:145`） | 真 glibc 的 `limits.h` 里 `#include_next <limits.h>` 跳进了 **zig 自带的更新版 glibc `limits.h`**；`-nostdinc` **挡不住** zig 注入的内建头 | 按 GCC 原生顺序插入 **GCC 自己的头目录** |

**最终头集合（组件头 → GCC include → GCC include-fixed → sysroot/usr/include）**：

```sh
GI=<bootlin63>/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include
GIF=<bootlin63>/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include-fixed
GD=<bootlin63>/arm-buildroot-linux-gnueabihf/sysroot/usr/include
HDR="-nostdinc -I$GI -I$GIF -I$GD"      # ★ 必须排在组件自己的 -I 之后
```

实测（`-O2` + 该头集合）：

| 组件 | 结果 |
|---|---|
| `mxml-file.c` | ✓ 未定义 = **`_IO_getc` / `_IO_putc` / `__strdup`**（= 工厂集合） |
| `libiconv/iconv.c`（`-O0`） | ✓ 1,305,124 B |
| `libcharset/localcharset.c`（`-O0`） | ✓ 未定义 = **`nl_langinfo`**（= 工厂） |

⇒ 接线改动：`tools/build_upstream.sh` 的额外头路径改**尾置**（`EXTRA_INC_TRAIL`，每条命令末尾）；
`tools/link_audit.sh` 把 XUnzip 的 `-I posix` 提到 `$CFLAGS` 之前。备份 `*.bak_hdr`。

## 五、独立发现（真分歧，已定位到指令级）：`timet2filetime`

| 侧 | 符号 | 大小 | 行为 |
|---|---|---|---|
| 工厂 | `_Z14timet2filetimel` | **12 B** | `str r1,[r0]; str r1,[r0,#4]; bx lr`（两个字段直接写 timer） |
| 我方 | 同上 | **312 B** | 调 **`gmtime`** + 完整年月日时分秒转换 |

**调用点反汇编**（`tools/xref.py` 扫出 `TUnzip::Get` 内 3 处，@0x125a8/0x125cc/0x125f0）：

```
ldr r1, [r8, sl]     ; r1 = timer
mov r0, r7           ; r0 = &temp（8 B sret 缓冲）
bl  timet2filetime
ldm r7, {r0, r1}     ; 取回 FILETIME
stm r3, {r0, r1}     ; 写进 ZIPENTRY 的 mtime/atime/ctime（+0x114/+0x10c/+0x11c）
```

**工厂侧完全没有** `SystemTimeToFileTime` / `DosDateTimeToFileTime`（我方有后者 268 B）
⇒ 工厂的 zip 移植把 Windows 时间转换**整套桩掉**。
⇒ 这也解释了"XUnzip 换回 Wischik 原版反而更差"：原版**有**完整 `gmtime` 路径，
而工厂**两个候选都不是**（原版 20/25 的体积命中是代理指标，行为上被证伪）。

当前判 **DIVERGE**（`calls_ext F=[] O=['gmtime']`，三组输入全分歧）。
对齐工具：`tools/xunzip_t2f_align.py`（含 `--revert`）。

## 六、待办

1. 全量施加事实 1+2+3 后**跑行为尺**——见 `tools/buildfact_align_exp.sh`
   （A=真头+现档；B=真头+`-O2`+`-fno-builtin-strcmp`）。
2. 对胜出臂应用 `tools/xunzip_t2f_align.py`（只需重编 XUnzip + 重链）再测。
3. `tools/model_coverage.py`（**单侧未建模门禁**，已接进 `link_full.sh`，exit 19）+
   `tools/model_asymmetry_ledger.txt`（棘轮台账）——本类假发散会复发。
4. `islower`（工厂有/我方无）与 `mbsinit`（我方有/工厂无）仍待定性：
   `mbsinit` 来自 libiconv 的 `loop_wchar.h`（`HAVE_MBSINIT` 与 glibc extern-inline 相互作用）。

---

## 七、★ 决定性补充（2026-09-28）：工厂是 **per-TU 优化档**（应用 `-Os` / 上游 `-O2`）

### 7.1 文档级证据（真头 = 工厂同期的 glibc 2.24 头）

| 位置 | 事实 |
|---|---|
| `stdio.h:587` | `#define putc(_ch, _fp) _IO_putc (_ch, _fp)` —— **无条件宏**，与优化档无关 |
| `bits/stdio.h:79-81` | `putchar` 是 `__extern_inline` 函数（体 `return _IO_putc (__c, stdout)`）；门控在 `bits/stdio.h:30 #ifdef __USE_EXTERN_INLINES` |
| `features.h:380-385` | `__USE_EXTERN_INLINES` 要求 `__OPTIMIZE__ && !__OPTIMIZE_SIZE__` ⇒ **`-Os` 关掉它** |

工厂**同时**导入 `putchar` 与 `_IO_putc`：
* `_IO_putc` 来自 `putc` 宏（任何优化档都有）；
* `putchar` 仍存在 ⇒ 调用它的那个 TU 的 extern-inline **未生效** ⇒ **不是 -O1+**。

### 7.2 单变量实测（全部可复现）

| 源文件 | 头 | 优化档 | 结果 |
|---|---|---|---|
| `mxml-file.c`（`putc`/`getc`/`strdup`） | zig | -Os / -O2 | `putc` / `getc` / `strdup` |
| 同上 | **真头** | **-Os** | **`_IO_putc` / `_IO_getc`** / `strdup` |
| 同上 | **真头** | **-O1 / -O2** | **`_IO_putc` / `_IO_getc` / `__strdup`** |
| `UpdateROM.c`（`putchar`） | zig | -Os | `putchar` |
| 同上 | **真头** | **-Os** | **`putchar`** |
| 同上 | **真头** | **-O2** | `_IO_putc`（extern-inline 生效） |
| `strupr.c`（`islower`） | 任意 | 任意 | `__ctype_b_loc`（**从不**产出 `islower`） |

⇒ 唯一同时满足「`putchar` 保留」+「`__strdup` 出现」的组合 = **应用 `-Os` + 上游 `-O2`**。
⇒ 这解释了"全 `-O2`"为什么不改善：**实测 DIVERGE 45 → 46**（臂 B）。

### 7.3 目标状态（构建事实）

| 组件 | 头 | 优化档 |
|---|---|---|
| 专有 `src/proprietary` | 真 glibc 2.24 头 | **`-Os`** |
| 上游 mxml / stb / mp3 | 真 glibc 2.24 头 | **`-O2`** |
| libiconv / libcharset | 真 glibc 2.24 头 | **`-O0`**（代码形态普查定案） |
| XUnzip | 真 glibc 2.24 头 | `-O2`（待再证） |
| 全部 | — | **`-fno-builtin-strcmp`**（GCC 不做 `strcmp→bcmp`，clang 会做） |

### 7.4 `islower` 仍未定性（诚实）

工厂导入 `islower`，而 `strupr.c` 在**任何**头/优化档组合下都只产出 `__ctype_b_loc`
（已实测四组）。⇒ 工厂侧 `islower` 的调用点不在我们重建的 `strupr` 里。
**未解决，不计入已收口项。**

---

## 八、执行环境阻塞（2026-09-28，必须由用户处置）

本轮三条执行路径**全部受阻**，且都属环境/平台层，非代码问题：

| 路径 | 现象 | 证据 |
|---|---|---|
| **本机重建** | 沙箱 safe-delete 守卫卡死 ⇒ **删除/覆盖/移动全部被拒** | `rm -f` → `Permission denied`；`mv` → `Permission denied`；`[safe-delete] state lock timeout`；zig 报 `failed to delete '<cache>/tmp/*.o.d': AccessDenied` ⇒ `error: CacheCheckFailed`（**全新缓存目录也一样**） |
| **CNB 交互式工作区** | 容器周期性重启（观测 `up 3 min`）＋ ~15 分钟自动关闭；重启后 `/tmp` 清空、SSH 一度被拒 | `duration≈924s` 后 `status: closed`；拆分上传/执行 ⇒ 命令无任何输出 |
| **CNB 声明式流水线** | 新建的 `1to1-linux-gates` 与**既有** `rkgame-rebuild` **两条流水线都**卡在 `Prepare` 阶段后 `error` | `stages: error,2911,Prepare`；runner 日志到 `t=5s` 后无后续 |

**唯一仍可用的写路径：编辑工具**（shell/Python 的 `>` 覆写与 `rm` 均被拒）。

已推送（CNB `main`，`5fb1127 → b9c05cf → 90c4f1d`）：仓库根 `.cnb.yml` 新增 `1to1-linux-gates`
流水线；`1to1/tools/` 新增 `cnb_gates.sh` / `model_coverage.py` / `xref.py` / `abi_shift_screen.py`。

**需要用户处置（物理动作）**：恢复沙箱的删除/覆写权限（或重置 safe-delete 守卫状态），
否则**本机任何重建都不可能完成**。

---

## 七、臂 C 判决：**per-TU 优化档成立**（本轮主结论）

配置：**真 glibc 2.24 头**（组件头 → GCC include → include-fixed → sysroot/usr/include）
＋ **应用 `-Os` / 上游 `-O2` / libiconv `-O0`** ＋ `-fno-builtin-strcmp`。

| 指标 | 基线（zig 头 + `-Os/-O1`） | 臂 B（真头 + **全 `-O2`**） | **臂 C（真头 + per-TU）** |
|---|---|---|---|
| 共有函数 | 782 | 782 | 782 |
| PASS | 732 | 731 | **733** |
| **DIVERGE** | **45** | 46 | **44** |
| 动态导入 | 111（工厂 113） | — | **110** |
| 工厂有/我方无 | **8** | — | **5** |
| 我方有/工厂无 | **6** | — | **2** |

- 臂 B（全 `-O2`）**无收益**（45→46）⇒ 反证"应用代码应保持 `-Os`"。
- 臂 C 剩下的 5 项：`_ITM_deregisterTMCloneTable` / `_ITM_registerTMCloneTable` /
  `_Jv_RegisterClasses` / `__gmon_start__`（都是 GCC crtbegin 的**弱引用**，运行期解析为 0）
  ＋ `islower`；剩下的 2 项：`gmtime`（`timet2filetime`，已按工厂机器行为对齐）与 `mbsinit`（libiconv 配置）。
- **已固化进主链**：`tools/link_audit.sh` 默认吃真头 + `-fno-builtin-strcmp`（真头缺失即 **exit 4**
  fail-closed）；`tools/build_upstream.sh` `UPOPT` 默认 `-O2`、尾置头默认接上真头集合。
  备份 `tools/*.bak_armC`。

### 7.1 过程中的"自伤"缺陷（都不是平台问题）

| 缺陷 | 现象 | 修法 |
|---|---|---|
| `link_full.sh` 的 `PY="${PY:-python}"` | 回退到**无 pyelftools** 的系统 python ⇒ 门禁抛 `ModuleNotFoundError` ⇒ 被当成"门禁 FAIL"（**假失败**） | 加依赖自检 + 已知 venv 兜底 + 指名报错（exit 5） |
| 并发跑 zig | `error: CacheCheckFailed` ⇒ 对象未产出 ⇒ 下游报 `undefined symbol: TUnzip::*`，根因被掩盖 | zig 作业**串行化**；全局缓存目录按任务隔离 |
| `xunzip_t2f_align.py` 的 `ROOT` 多剥一层 | 写成 `D:/output/src/...` ⇒ `FileNotFoundError`；另有一次 `PermissionError` | 修 ROOT；源文件改用编辑工具写入 |

## 八、CNB 云开发门禁**首跑**（本机永远跑不了的那 6 道）

> 完整报告：**`CNB-GATES-RESULT.md`**；原始日志：`report/cnb_gates/2026-09-28.txt`；
> 一条命令的运行器：`tools/cnb_ws_gates.sh`。

| 门禁 | rc | 结论 |
|---|---|---|
| `scan_symbol_delta` | **0** | 工厂 228 / 我方 228（台账生效） |
| `scan_cxx_abi` | **0** | **62/62，签名不一致 = 0** |
| `scan_livein_args` | **1** | HIGH **6** / LOW 41（台账 1 行已修好，按棘轮删行） |
| `scan_kr_argcount` | **1** | **17 个函数**我方调用点少给参数 |
| `scan_dead_loop` | 3 | 前置缺失（需 `build/obj`） |
| `ci_p2a_stb` | 1 | 首跑因**我的参数错误**（该工具无参数解析） |

★ 平台事实：**CNB「构建」流水线全部卡在 `Prepare`**，平台原文——
`Root Group's events CPU core-hours are insufficient for pre-freezing(Freezing time:5.00 min,
equivalent to 0.67 core-hours)` ⇒ **根组织 CPU 配额耗尽**，与配置无关
（长期存在的 `rkgame-rebuild` 同样失败）。**云开发工作区**走另一条配额路径，可用。
`.cnb.yml` 的 `1to1-linux-gates` **已存在且完整**（deps → `cnb_env.sh` → `cnb_gates.sh` →
报告推 `artifacts-gates`）⇒ **只欠配额**。

★ 新发现：`scan_kr_argcount.py` **在任何 workflow 里都没出现**（又一处"造了闸门没上锁"）。

### 八.1 新纪律 54–56
> **54.** 门禁"失败"先分辨三类：真违例 / **参数或依赖传错（假失败）** / **前置缺失(rc=3)**；
>   混在一起报会误导决策（本轮三次假失败全是自己造成的）。
> **55.** `tar` 经 ssh 管道会返回 rc≠0 但文件完整 ⇒ 判据用**后置条件（文件在 + sha256 相等）**，
>   不要用工具退出码。
> **56.** 平台报错要读**完整链路**（`Prepare` 的 stage 日志才有"配额不足"原文；
>   只看 `status: error` 会误判成配置问题）。

