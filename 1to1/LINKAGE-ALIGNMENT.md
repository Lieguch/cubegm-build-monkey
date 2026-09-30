# 链接对齐（根因）：从 `zig cc` 驱动改为**接管链接** —— 2026-09-28

> 触发：剩余 44 条 DIVERGE 里有一大族形态是 `calls_ext F=['strlen','memset','strcpy','strcmp'…] O=[]`
> 且标注 `(原始名不同)`。先取证，不猜。

---

## 〇、一句话结论

**工厂的 `memcpy/memset/memmove/strlen` 是 `libc.so.6` 的动态导入；我们的是 `.text` 里的
`STB_LOCAL` 静态定义** —— 它们来自 `zig cc` 自动链进来的 `libcompiler_rt`（`libcompiler_rt_zcu.o`）。

机制（可复算）：`zig cc` 的链接行把 `libcompiler_rt.a` 放在 libc **之后**，而该归档里的
"大对象"会被别的符号（`__udivsi3`/`__aeabi_*` …）拉进来；它同时定义了 `mem*/str*`
——**普通目标文件定义按 ELF 规则盖过 DSO 定义**，于是 libc 的动态版本永远用不上。
（zig 源码自己解释了为什么会这样：`lib/compiler_rt.zig:30` 注释 "we prefer weak linkage
because some of the routines we implement here may also be provided by system/dynamic libc"，
但 `ofmt_c == true`（`zig cc`）时 `linkage = .strong`，weak 那份兜不住。）

**根治方式 = 不再让 zig 当链接驱动**：直接驱动 `zig ld.lld`（LLD 21.1.0，实测可达），
按**工厂同期工具链**（Bootlin 2017.05 = GCC 6.3 / **glibc 2.24** / binutils 2.27）的 sysroot
组链接行，并照抄 GCC 的 `-lgcc … -lc -lgcc` 顺序。

---

## 一、取证链（每一步都可复算）

| # | 问题 | 方法 | 结论 |
|---|---|---|---|
| 1 | 那 4 个符号在我方是什么形态？ | pyelftools 读 `.symtab`/`.dynsym` | `memcpy/memset/memmove/strlen` = **STB_LOCAL，在 `.text`**（非导入）；`strcpy/strcmp/strchr` 是导入 |
| 2 | 谁定义它们的？ | 全缓存机械扫描 `.o`（`tools/_find_mem_def.py`） | **`libcompiler_rt_zcu.o`**（zig 的 compiler_rt） |
| 3 | 为什么它盖过 libc？ | `zig cc -v` 打印**真实链接行** | `… libc.so.6 … libc_nonshared.a libcompiler_rt.a`；compiler_rt 是普通目标（单个大对象）⇒ 其定义优先于 DSO |
| 4 | 能不能用 `-lc` 抢回来？ | 单变量：`EXTRA_LDFLAGS="-lc"` / `--no-as-needed -lc` | **无效**（zig 驱动重排/去重；且普通目标优先于 DSO） |
| 5 | 有没有更规范的驱动方式？ | `zig build-exe --help` / `zig ld.lld --version` | `zig ld.lld` **可用**（LLD 21.1.0）⇒ 可完全接管链接行 |
| 6 | 工厂真正的库集是什么？ | `.dynamic` 的 `DT_NEEDED` + `.gnu.version_r` | `libz libdl libm libstdc++ libpthread libgcc_s libc`；需求 `GLIBC_2.4/2.7 · GCC_3.5 · GLIBCXX_3.4` |
| 7 | 工厂的运行时助手长什么样？ | `__aeabi_*` 符号集与尺寸 | 只有 **6 个 LOCAL**：`idiv`0 / `idiv0`16 / `idivmod`32 / `ldiv0`16 / `uidiv`0 / `uidivmod`32 ⇒ **静态 `libgcc.a`** 的 `lib1funcs.S`；同时又动态链 `libgcc_s.so.1`（只为 unwind） |

---

## 二、改动（只有链接层，不动任何源码/判据）

* `tools/link_full.sh`：新增 `LINK_DRIVER`（默认 **`lld`**；`zigcc` 回退到旧行为），
  `lld` 分支直接驱动 `zig ld.lld`，输入 = 同一批对象 + 工厂同期 sysroot 的
  `crt1.o` / `libc.so.6` / `libm` / `libpthread` / `libdl` / `libstdc++.so.6` / `libgcc_s.so.1` /
  `libc_nonshared.a` / `libpthread_nonshared.a` / **静态 `libgcc.a`（前后各一次，照抄 GCC）**。
* `tools/fetch_bootlin63.sh`（新）：幂等抓取 Bootlin 2017.05（`.ok` 判据用 `-f` 而非 `-x`
  —— 第 66 轮的教训）。
* `lld` 模式下**不链 `build/cxx_ops.o`**：它是"没有 libstdc++ 时的静态替身"，
  现在我们真的链了 `libstdc++.so.6` ⇒ 保留只会让 `_Znwj/_Znaj/_ZdlPv/_ZdaPv` 变成我方私有静态定义
  （工厂这 4 个是 libstdc++ 的动态导入）。

---

## 三、收敛（全部实测）

| 指标 | 工厂 | `zig cc`（旧） | **接管链接（新）** |
|---|---|---|---|
| `DT_NEEDED` | 7 | 5 | **7（逐项同序）** |
| 动态导入符号数 | 113 | 92 | **111** |
| 工厂有 / 我方无 | — | 26 | **8** |
| 我方有 / 工厂无 | — | 5 | 6 |
| `memcpy/memset/memmove/strlen` | 动态导入 | 静态 LOCAL | **动态导入** |
| `__aeabi_*` LOCAL | 6 | 69 | 7（**6 项尺寸与工厂逐项相同** + `__aeabi_d2ulz`） |
| `.gnu.version_r` | 6 组 | GLIBC_2.4/2.7 … | **逐项同工厂** |
| 行为尺 `diff_exec --steps 3000` | — | 共有 778 / PASS 729 / **DIVERGE 44** | 共有 **782** / PASS **735** / **DIVERGE 42** / TRUNC 5 / SKIP 0 |
| 体量覆盖门禁 | — | SHORT 0 | SHORT 0（INFO 6 = 工具链助手） |

* 交付产物：`build/rkgame.rebuilt.elf` **5,513,544 B**，
  sha256 `a4820bd68faf9ccebc502752a4dc4b46d0c74f8c1fdb3bdc080566d00b016db3`；
  `_sdcard_drop7/` 已按此重出（MANIFEST 与实文件 sha256 逐项核对一致）。
* 主链端到端：`rc=0`，八道门禁（dyn_audit / PT_LOAD 几何 / RELRO / 常量混淆 / MMIO 宽度 /
  设备访存类级 / 体量覆盖 / 编译期 UB）**全 PASS**。

### 3.1 中途抓到的**真缺陷**（第一版）

第一版接管链接**漏了 CRT**（没链 `crt1.o`），而我又带着 `-z undefs`（允许未定义符号）
⇒ `_start` 静默未解析 ⇒ **`e_entry = 0x0`**，产物根本不可执行。
被 `tools/dyn_audit.py` 的 `e_entry ∈ 可执行 PT_LOAD` 判据当场抓住。
修法：链入工厂同期 `crt1.o`，并**去掉 `-z undefs`** —— 去掉后本配置**无任何未定义符号**。

---

## 四、诚实：这次改动**曝光**了 5 个以前被掩盖的分歧

DIVERGE 计数 44 → 42，但**构成变了**：

* **消失 5 个**（真修好）：`GetFilenameExt` / `LoadMenuLog` / `get_from_line` / `main_Menu` / `myStrrstr`
  —— 全是 `calls_ext F=['strlen','memset'…] O=[]` 这一族（我方缺 libc 调用绑定）。
* **新增 4-5 个**（本来就存在、只是以前看不见）：
  | 函数 | 形态 | 性质 |
  |---|---|---|
  | `ClearBuffer` | `calls_ext F=[] O=['memset']` | 工厂把它**内联**了，我们调 `memset` ⇒ 编译期 codegen 差异 |
  | `get_item_from_line` | `strlen/__ctype_b_loc` 各调 **2 次** vs 工厂 1 次 | codegen（无 CSE）差异 |
  | `mui_search` / `mui_setting` | `DisplayThumbnailflag+0:**4**B:R` vs 我方 **1**B | ★ **源码类型声明可疑**（真缺陷） |
  | `progress` | 工厂对 `0x003e19a0` 有 8B 读+写，我方**没有** | ★ 疑似**漏实现**（真缺陷） |
  | `run_game` | 工厂读 `log_file_initialized`，我方没有 | ★ 疑似漏实现（真缺陷） |

以前它们"看不见"，是因为我方 `memset/strlen` 是**二进制内部调用**（不计入 `calls_ext`）。
这属于"把假绿换成真账"，方向正确但要如实记账。

---

## 五、仍然存在的两个方向性差异（**下一靶子**）

| 方向 | 清单 | 根因（已定位） |
|---|---|---|
| 工厂有 / 我方无（8） | `_IO_putc` `_IO_getc` `__strdup` `islower` | **编译期头文件不同**：glibc 2.24 的 extern-inline / `bits/string2.h` 只在 **GCC + 真 glibc 头**下生效；zig 自带 glibc 头把它裁掉了 |
| 同上 | `_ITM_deregisterTMCloneTable` `_ITM_registerTMCloneTable` `_Jv_RegisterClasses` `__gmon_start__` | GCC 的 **`crtbegin.o`/`crtend.o`** 的弱引用 ⇒ 需要把 GCC 的 CRT 一并纳入 |
| 我方有 / 工厂无（6） | `putc` `getc` `strdup` `mbsinit` `gmtime` `bcmp` | 与第一行**同一个根因**（头文件） |

⇒ 这两张表指向**同一个根修的下一步**：**把编译也切换到工厂同期 GCC 6.3 + glibc 2.24 头**
（bootlin63 已在仓库缓存里，`fidelity_matrix.sh` 已证明它能编过全部源码）。
注意：第 67 轮"换 GCC 更差"的 A/B **混淆了编译器与 libc 两个变量**，现在 libc 已对齐到 2.24，
那组 A/B 需在**这个基础上**重做。

---

## 六、门禁改动（防这类问题再发生）

`tools/size_coverage_gate.py` 增加**分桶**：只对"**由我方对象定义**"的函数判 SHORT
（判据 = 名字是否出现在 `build/obj/*.o`、`build/upstream/*.o`、`XUnzip.o`、`factory_local.o`、
`crt_init.o` 的已定义函数符号里）。接管链接会静态带进 `libgcc.a` 的运行时助手
（`__udivsi3` 0.34× / `__divsi3` 0.40×），不分桶会把正确产物判成 FAIL（假 FAIL）。

* 非我方对象定义的共有函数 → **INFO，换行公示清单**（当前 6 个，其中 4 个尺寸与工厂**完全相同**）。
* **读不到任何我方对象 ⇒ `exit 3` fail-closed**，绝不"默认全放行"。
* 自证锚点 8 → **11 条，失败 0**（含"`__udivsi3` 不在我方对象集里"这类反例）。

---

## 七、回退方式

```sh
LINK_DRIVER=zigcc sh tools/link_full.sh build/rkgame.rebuilt.elf   # 回到旧链
cp tools/link_full.sh.bak_lld tools/link_full.sh                    # 回到旧脚本
```

旧产物已留档：`build/rkgame.rebuilt.zigcc.elf`（5,747,156 B）。

---

## 八、新纪律

> **46.** **链接行本身也是"构建事实"**：用哪个驱动、库以什么顺序出现、有没有 `compiler_rt`，
>   都会改变产物（`DT_NEEDED`、符号绑定、`.gnu.version_r`）。对齐工厂不止是对齐编译器与版本，
>   **链接层必须一并取证并对齐**。
> **47.** **`-z undefs`（允许未定义符号）会静默吞掉"入口/关键符号缺失"**：第一版正是它把
>   `_start` 未解析变成"链接成功"，留下 `e_entry=0x0` 的废产物。凡用允许未定义的链接，
>   必须另设"关键符号必须已定义"的判据（本次是 `dyn_audit` 的 `e_entry` 判据救的场）。
> **48.** 门禁**分桶必须用机械判据**（"是否我方对象所定义"），**不得**用名字白名单
>   （白名单会掩盖真缺体）；且**读不到分类依据时 fail-closed**。

---

## 九、第 77 轮追加（2026-09-28）：**尺子两处缺陷**（都在 `read_width_only`）

> 触发：`mui_search` / `mui_setting` 的报告行看起来正是文档（GAP 17.18）所说
> "同址同对象、仅访存宽度不同 ⇒ 合法窄化 ⇒ 应降 INFO"，但实际仍判 DIVERGE。
> 新增调试钩子 `CGM_DBG_RW=1` 打印**原始键**，一次看清：

### 9.1 缺陷甲：`'LN'`（具名全局）形式**取错宽度下标**
两种键布局不同：
```
'LN' 形 = ('LN', name, off, w, rw)   ← 宽度在 k[3]
'A'  形 = ('A',  addr, w, rw)        ← 宽度在 k[2]
```
旧实现统一 `k[2]` 取"宽度" ⇒ 对 `'LN'` 取到的是**偏移**（两侧通常都是 0）
⇒ 比较恒等 ⇒ `diff` 恒空 ⇒ `bool(diff)` 恒 False ⇒ **`rw_only` 永远为 False**
⇒ 文档里写明的"合法窄化降级 INFO"对**所有具名全局变量的访问**从未生效。

### 9.2 缺陷乙：`'LN'` 的 ident **丢掉偏移** ⇒ 误放"少读/多读"
`ident` 旧实现 `k[:2] + k[4:]` ⇒ `('LN', name, rw)`（无 off）⇒
"同一对象不同偏移"被合并 ⇒ 一侧**少读几个偏移**也会被当成"仅宽度不同"而放过。
实证（`popwindows`）：工厂读 `m_ui+60` **五次**，我方**一次都没有** —— 被这条误判成 INFO。

### 9.3 修法（同时收紧，防放宽被滥用）
1. 宽度按形态取：`'LN' → k[3]`，`'A' → k[2]`；
2. ident **保留偏移**：`'LN' → (kind,name,off,rw)`、`'A' → (kind,addr,rw)`；
3. **次数必须相同**才谈"仅宽度不同"（否则就是少读/多读 ⇒ 照旧报发散）；
4. 自证锚点 **77 → 82 条，失败 0**（新增 5 条：4 条 `'LN'` 形态 + 1 条 count）。
   ★ 顺带更正一条**标签与内容不符**的旧锚点：`反例 次数不同` 实际比较的是
   `0x10 vs 0x3BC40C` ⇒ 它测的是"地址集合不同"，对 count 语义**从未覆盖**。

### 9.4 效果（诚实：数字**变大**了，因为以前在漏报）

| 项 | 旧尺子 | **修好后** |
|---|---|---|
| 共有函数 | 782 | 782 |
| PASS | 735 | **732** |
| **DIVERGE** | 42 | **45** |
| TRUNC / SKIP | 5 / 0 | 5 / 0 |
| 自洽 | ✓ | ✓ |

* **降为 INFO（本来就是"仅宽度不同"）**：`mui_search`、`mui_setting`、`mui_type`（3 个函数）。
* **新报为 DIVERGE（本来就被漏放的真差异）**：`mui_DisplayInputBuffer`、`mui_DisplayLine_t`、
  `outputblankxy`、`popoffwindows`、`popwindows`（5 个函数；形态均为 `仅F=[...m_ui+N...] 仅O=[]`）。
* ⇒ 交付**产物未变**（sha256 仍 `a4820bd6…`）；变的是**测量的诚实度**。
  这正是本项目的口径：**宁可数字变大，也不要假绿/漏报。**

---

## 十、顺带修掉两类"交付机制"缺陷（同一个"半成品"家族）

| # | 缺陷 | 证据 | 修法 |
|---|---|---|---|
| 1 | **投放包 README 的行为尺数字是硬编码的** | `_sdcard_drop7/READ-ME-FIRST.txt` 写着 `PASS 727 / DIVERGE 46 / 共 778`（早已过期） | `stage_sd_round7.py` 新增 `ruler_stats()`，从 `report/_deliver_diff.txt` **实时解析**（PASS/DIVERGE/TRUNC/SKIP/共有 + 自洽断言）；**解析不到就中止出包**（fail-closed）。重出后 README 自动显示 `PASS 732 ｜ DIVERGE 45 ｜ TRUNC 5 ｜ SKIP 0（共 782，自洽 ✓）` |
| 2 | **投放脚本在 `rmtree` 被拦时继续跑，产出不完整的包** | 实测：safe-delete 守卫让 `rmtree` 静默失败，脚本照常往下写 ⇒ 包里**缺 `READ-ME-FIRST.txt`** | `stage_sd_round7.py` 在删除后**再判一次目录是否还在**，还在就 `SystemExit`（禁止产出半成品包） |

---

## 十一、编译器对齐实验：**已就绪，只能在 Linux 跑**（本轮未执行）

`tools/compiler_align_exp.sh`（新）—— 单变量：只把编译器换成**工厂同期 GCC 6.3**，
链接驱动/sysroot/库/优化档/源码全不动。

* **平台事实（实测，不猜）**：`cache_tc/bootlin63/bin/arm-buildroot-linux-gnueabihf-gcc`
  是 **x86-64 Linux ELF** ⇒ 在 Windows 上 `cannot execute binary file: Exec format error`。
  脚本非 Linux 时 **fail-closed（exit 4）**（本机已实测 rc=4）。
* 判据（写死在脚本里，防止事后凑结论）：
  ① 213/213 编译成功；② link rc=0 且 `DT_NEEDED` 仍 7 项同序；
  ③ `.dynsym`"工厂有/我方无"从 **8** 降到 **≤4**（extern-inline 那 4 项被补上）；
  ④ **行为尺 DIVERGE 必须 < 45**，否则**回退编译器**并把原因写进
  `report/compiler_align_verdict.txt`。
* 为支持单变量对比，给三个脚本加了**目录旋钮**（互不污染主链）：
  `link_audit.sh`：`OBJD` / `UPOBJD` / `XUPOBJ`；`link_full.sh`：`UPOBJD`。
