# PROJECT-MEMORY — rkgame 1:1 复刻（**权威项目记忆**）

> ★★★ **最新（2026-09-22 第二轮真机定案）**：两个**已定位并已修**的根因 ——
> ① `PT_GNU_RELRO` 把 `.data` 圈成只读（写全局变量即 SIGSEGV；真机 `si_addr=0x4e1010`）；
> ② 工厂 `movw r1,#44100` 被 Ghidra 反编译成符号 `UpdateROM` ⇒ 采样率变成 5,128,288
> ⇒ `hwparams -22(EINVAL)`（原厂同处只是无害的 -32）。
> 详见本文件 §「2026-09-22 第二轮真机定案」与 `GAP.md` 16.70-16.74；
> 期间我的一处**假缺陷**（`sfc_init` 的 mmap 参数）已公开更正（16.70/16.73）。



> ## 本文件的使用契约（先读这段）
> - 这是**本项目唯一的权威长期记忆**，位于**项目文件夹内** ⇒ **不受会话注入长度限制**。
> - **纪律：只增不删、不为省空间而压缩。** 需要精简时**另建摘要**，**不要删这里的证据**。
> - `D:\output\.workbuddy\memory\MEMORY.md` **只是一个 3 KB 的指针**，不要往那里写项目细节
>   （它每轮被自动注入，超长会被**从尾部静默截断** —— 历史教训：我为此反复压缩、并因此丢失过上下文）。
> - `~/.workbuddy/MEMORY.md` 只放**跨项目用户偏好**，**不放本项目内容**。
> - 维护动作：每个实质轮次结束时，更新 §7 现状快照 + §9 待办；新踩的坑追加到 §2。
>
> ## 配套文件（细节一律外链，本文件只放"承重结论 + 指向"）
> | 文件 | 内容 |
> |---|---|
> | `GAP.md` | 逐坑证据链，编号 `16.x`（**唯一权威**，含对我错误结论的公开更正） |
> | `STATUS.md` | 逐轮台账（189 KB，第 1–54 轮） |
> | `GAP-TO-REPLACEMENT.md` | 替代差距评估（"还差多少能直接替代"的逐项清单） |
> | `DIAG-RUNBOOK.md` | 设备端诊断仪使用手册（字段含义、被拦截符号、已知限制） |
> | `_sdcard_drop/READ-ME-FIRST.txt` | 真机投放步骤（**给用户看的**） |
> | 技能 `ghidra-arm-decompile/SKILL.md` | 判据/仪器通用纪律（20+ 条，**跨项目可复用**） |

---

## 0. 一句话 + ★★ 两条并行线（2026-09-22 发现，此前记忆的**重大盲点**）

目标：把原厂 `rkgame`（闭源 ARM32 菜单引擎）**用我们自己写的源码功能等价地重建**，
产物同名覆盖 SD 卡的 `cubegm/rkgame` 后**设备能正常开机使用**。
远端仓库 `Lieguch/cubegm-build-monkey`，本地 `D:/output/rkgame-1to1/`。

★★★ **同一仓库里存在两条独立的重建线** —— 本记忆此前只记了 A 线，这是一个**重大盲点**
（导致我给用户的"替代差距评估"是片面的）。

> ### ★★★ 2026-09-22 用户澄清（**权威，优先于任何自评文档**）
> **B 线（`rkgame-rebuild/`）是一条已被废弃的路。** 它**只实现了一个背景图和几条日志**，
> **和原厂原功能根本不是一个量级**；**正因为这条路的失败，才开启了 1:1 复刻原厂的项目**。
>
> ⇒ 我此前基于 B 线自己的 `gap-audit-v6.md`（"覆盖率 ~96%，22/23 项真实现"）和
>   `build.yml` 的 qemu e2e PASS，就推断它"成熟得多、可能直接可用" —— **这是错的，
>   而且用户直接批评这种方式是"懒"**。
> ⇒ **教训（已写进 §2.14）：自报覆盖率不是证据。** 「22 项真实现」的**深度**可能只是
>   "写了几行日志 / 画了张背景图"。评估一条线的成熟度，必须看**它实际能做什么**，
>   而不是它给自己打的分。**不要拿别人的自评当自己的结论。**

| | **A 线：`1to1/`**（本记忆主线） | **B 线：`rkgame-rebuild/`**（2026-09-22 才发现） |
|---|---|---|
| 目标 | **逐函数保真**（对齐原厂地址 / 符号 / 反汇编） | **功能等价**（不追求字节级一致；明确接受"格式替代"） |
| 构建 | `tools/link_audit.sh` + `zig cc` | `rkgame-rebuild/build.sh` + `CMakeLists.txt` + `arm-linux-gnueabihf-gcc` |
| 规模 | `src/proprietary/*.c` 213 文件 + 上游库 | **`rkgame-rebuild/src/` 90+ 源文件**：完整 `ui_*.c` 一整套 / `cpd.c`（.cpd=ZIP 资源）/ `sram.c` / `evdev.c` / `disp.c` / `audio.c`(minimp3) / `font.c`(stb_truetype) / `game_list.c` / `thumbnail.c` / `dbg_overlay.c` |
| CI | `1to1-verify` + `1to1-qemu-behav` ⚠（**文件名与线名相反，勿混**） | `build.yml`（workflow name = **`rkgame-rebuild`**） |
| 产物 | `build/rkgame.rebuilt.elf` 5.4 MB | `output/rkgame` **1,031,860 B** |
| **真机状态** | **从未成功**（零日志 —— 见 §2.10 / §9） | **已上机过**：有 `V15-ARM-GATE-CHECKLIST.md`（真机验证清单，引用 pre-v15 的设备日志 `J:\cubegm\rkgame.log`）；设备侧 `recent.lst` / `favorites.lst` / `setting.xml` 即其产物所写 |
| 自评覆盖 | 符号落位 92.2%（§7） | **`gap-audit-v6.md` 自报 ~96%（22/23 项真实现）** |
| 活跃度 | **活跃**（2026-09-21/22 连续迭代） | 停在 **v15（2026-09-10）**；但 `build.yml` **每次 push 仍自动跑 qemu e2e 并 PASS**，产物持续写入 `artifacts` 分支 |

- 提交者：`Lieguch`（用户本人）**与 `WorkBuddy Agent`** ⇒ 修订 §1 红线 4：
  **这个仓库不止一个 agent 在推送过**（2026-09-09/10 那批是另一条线的工作）。
- B 线自报的"可接受偏离"举例：`menu.log` 原厂是**二进制**，B 线改为 `recent.lst` + `favorites.lst`（CSV）。
- B 线的 e2e **断言本身不假**（那 8 条硬断言确实逐条执行了），但 **断言深度只到「进程活着 + 有重绘」**
  —— **没有一条触碰真实功能** ⇒ 对"功能是否可用"这个问题而言，它仍然是**假绿**
  （探针深度不足，同 §2.6 的 `font.ttf` 问题）。
- ⇒ **结论更正**：`GAP-TO-REPLACEMENT.md` 里凡引用 B 线成熟度的表述**一律作废**；
  "能否替代"只看 **A 线（本项目）** 的进展与真机结果。
- ⇒ B 线在真机上"跑过"这件事，**不能**作为"它接近可用"的证据 —— 它是一条**被放弃的浅实现**，
  只实现了背景图 + 几条日志（用户 2026-09-22 澄清）。

---

## 0.1 ★★★★★ 路线判据（2026-09-22 用户质疑后的纠正）—— **这是本项目最重要的一条纪律**

> **用户原话**：「怎么我感觉你的路线往以前放弃那个方案推进？而不是 1:1 复刻的路线？」
> **用户是对的。** 被放弃的 `rkgame-rebuild` 那条路，判据是「**造一个能跑的程序**」。
> 本项目是 **1:1 复刻**，判据应当是「**产物与原厂的差异收敛**」。

### 我偏到哪去了（自查，有据）
2026-09-20 ~ 09-22 我的产出：探针 v1/v2/v3、`t4` 最小动态 ELF、崩溃地址符号化、PT_LOAD 几何 /
`GNU_STACK` / `DT_INIT` / 页冲突 / 文本重定位的逐一排查 —— **全部是「可用性/通用 ELF 合法性」判据**，
**没有一件是「忠实度」判据**。而这期间 A 线的结构性偏离（9 段、`GNU_STACK` 16 MB/NX、空
`DT_INIT_ARRAY`）我一直在把它们当「失败原因假设」去猜，**而不是当「忠实度缺陷」去消**。

### 根本矛盾（**这是架构层的，不是细节**）
| 项 | 体积 | 说明 |
|---|---|---|
| `.fimg_text`（**工厂机器码**） | **2,957,704 B** | 符号类型是 **OBJECT**（FUNC = 0）——它被当作**数据**嵌在产物里 |
| `.fimg_rodata` | 856,920 B | 工厂只读数据 |
| `.fimg_data*` / `.fimg_bss*` | 274,283 B | 工厂可写/零页 |
| **`.fimg_*` 合计** | **4,088,907 B（3.90 MB）** | |
| **自有全部核心节** | **1,388,528 B（1.32 MB）** | 其中自有 `.text` 仅 **520,216 B** |
| **自有 `.text` 里指向 `.fimg_*` 的地址常量** | **9,997 个**（`.fimg_text` 占 8,672） | |

⇒ **产物 = 「重建的代码（1.32 MB）」+「工厂地址空间镜像（3.90 MB）」的混合体**，
   且为「逐位复刻工厂绝对地址」而把只读/可写区在地址上交错 ⇒
   **数学上不可能再得到原厂的 2 段连续装载结构**（原厂 `[R-X]`+`[RW-]`）。
   **而「能不能被加载/跑起来」恰恰依赖装载结构** ⇒ 这个架构在对抗它自己。

★★★ **依赖面的真实构成（源码级统计，2026-09-22）**：
| 类别 | 量 |
|---|---|
| `UNK_*`（工厂**代码区**地址） | **仅 3 个符号 / 12 次出现** ⇒ **几乎不执行工厂机器码** |
| `DAT_*`（工厂**数据区**地址） | 2,893 个符号 / 5,758 次出现 |
| **实际使用点**（排除 `globals.h` 声明表与 `factory_image.S` 定义） | **175 个符号 / 2,548 处** |
| 归属：`.fimg_data` 147 · `.fimg_rodata` 20 · `.fimg_bss` 5 · **`.fimg_text` 3** | |

⇒ **真正的依赖是「工厂的全局数据布局」（175 个符号），不是「工厂机器码」。**
   而那 **2.96 MB 的 `.fimg_text` 机器码镜像基本不被执行**，却为「保证任何工厂地址都能解析」
   被完整嵌着 —— **它是段结构无法对齐的直接原因**。

### 正确的判据（已做成可复现工具 `tools/fidelity_audit.py`）
| 刻度 | 现值（2026-09-22） | 目标 |
|---|---|---|
| **A. 工厂符号依赖数**（源码里对 `UNK_*`/`DAT_*` 的引用，已排除声明表与定义文件） | **175 个符号 / 2,548 处使用**<br>其中落在 `.fimg_text`（工厂**机器码**区）的**仅 3 个符号** | **0** |
| **B. 与原厂结构差异** | **7 项**：`PT_LOAD` 9→2、`GNU_STACK` `RW-/16MB`→`RWX/0`、`DT_INIT_ARRAYSZ` 0→4、`DT_FINI_ARRAYSZ` 4→8、`DT_FLAGS` 0x8→0x0、NEEDED 5→7 | **0 项** |
| **C. 工厂函数落位** | 743 自有 / **92 未重编**（总 835） | 835 全自有 |

★ **判据口诀：刻度 A 收敛到 0 + 刻度 B 全一致 = 1:1 达成。**
★ **「产物能不能 exec / 能不能跑」属可用性判据，不得当忠实度刻度**（同 §2.2「别用静态体积比当进度刻度」）。

### 正确的路线（**收敛顺序**）
1. **把那 175 个「工厂数据符号」搬进我们自己的段**（`.data`/`.rodata`，内容保留原厂初始值，
   但**不再钉死在工厂绝对地址**）⇒ 代码改为**符号引用**而不是硬编地址；
2. 依赖数 → 0 ⇒ **`.fimg_*` 整体可移除** ⇒ 只读区/可写区自然连续
   ⇒ **段结构自然对齐原厂的 2 段**（不需为「让它能加载」做任何适配）；
3. 期间随时用 `tools/fidelity_audit.py` 核对三刻度。
   ★ 那 3 个落在 `.fimg_text` 的符号要单独确认是否在热路径上（若在，先补那部分代码）。

### ★★★★ 关于「刻度 A」的**第二次公开更正**（2026-09-23，第 57 轮）—— 我上一轮写的 175 是错的

| 口径 | 值 | 判定 |
|---|---|---|
| 二进制区间法（旧 `fidelity_audit.py`） | 10007 | **无效**（vaddr 当文件偏移 + 区间重叠误报） |
| 源码级·代码口径 ★ | **162 个符号 / 2534 处** | **权威，收敛目标** |
| 我 2026-09-22 写下的 | 175 个 / 2548 处 | **错**：多算了 13 个「源码引用了、但编译期被消除」的死引用 |

分项：`.fimg_data 135 · .fimg_rodata 20 · .fimg_bss 5 · .fimg_text **2**`。
★ `.fimg_text` 段内**只有 2 个 `UNK_`**（第 3 个是容器 `__f_text_base`）⇒「几乎不执行工厂机器码」成立。
★ 仪器改为 `tools/fidelity_source_deps.py`（符号清单取**产物 ELF 的 `.fimg_*` 段符号**；排除
`globals.h` 与 `factory_image.S`；带 9 条正反自证 + "被引用但无定义"诊断通道）。

### ★★ 关于「刻度 A」的一次公开更正（2026-09-22）
初版 `fidelity_audit.py` 报出的「工厂镜像引用数 = 9,997」**是无效数字**，两处缺陷：
① 把 `.text` 的 **vaddr 当文件偏移**用（vaddr `0x4e4000` vs 真实偏移 `0x4bd000`）；
② 「4 字节值落在大区间」会**大量误报**（字符串字节恰好落在 `.fimg_text` 的 2.9 MB 区间内）。
⇒ 我只凭「有效区间重叠」和双对数尺度便宣布结论（**未做自证**），这正是 SOUL.md 里
「green 不等于 correct，判据必须先自证」的反面。改为**符号级统计**后真数字是 **175 个符号 / 2,548 处**。
**纪律：任何新判据上线前，必须用一个已知答案的样本做正反双向自证。**

### ★★★★ 方法论纪律（2026-09-22 教训，比技术结论更重要）
**在动手改任何东西之前，先把「用户已给的全部数据」读完。**
本轮我连续提出并证伪 **6 个假设**（PT_LOAD 几何 / `GNU_STACK` / `DT_INIT` / 跨段页冲突 /
文本重定位 / 工厂镜像引用），**全部基于 ELF 结构推演**；而真正的原因
**就在用户给的 `p3_*_out.txt`（程序自己的 stdout/stderr）里，一眼可见**
（原厂 `snd_pcm_start: -32` vs 我们 `apply hwparams: -22`）。
⇒ **代价**：6 轮无效推演 + 2 次给用户错误数字（9,997 与「8,672 处调用未重编函数」），
   还改了两次记忆。**这就是「边看边下结论」的代价。**
⇒ **纪律**：① 数据先读全（含每个附件、每个日志的**尾部**）；② 一次整体分析；
   ③ 再动手；④ 新判据上线前用已知答案的样本做**正反双向自证**。

### 明确不再做的事
- ✗ 为「让它跑」而做的结构适配（例如把 `.fimg_text` 段改成 `R-X` 让工厂机器码可执行）——
  那是「造能跑的混合体」，**正是被放弃那条路的方向**。
- ✗ 把 B 线（`rkgame-rebuild/`）的产物当候选/参考（用户已明确指出它是被放弃的浅实现）。
- ✓ 探针/崩溃诊断**不是白做**：它们给出了「崩在 `cgm_diag_boot+0x184`（写 `g_lvl`）」与
  「崩在 `sfc_init+0x6c`」两个函数级事实（见 §9.1），**但不作为主线**。

---

## 0.2 ★★★★★ 需求与路线**锁定**（2026-09-23 用户原话澄清）—— 此前我反复问的岔路已关闭

> **用户原话**：「我的需求是 **1:1 复刻 rkgame**，目的是两个：1. 能承接原厂系统所有资源和操作，
> 对于用户来说没有什么改变；2. **我们掌握了原始代码**，就可以在原厂基础上进行功能升级，
> 如 evdev 驱动的即插即用的手柄、如策略游戏的 **SRAM 存取**功能。」

**⇒ 两条硬约束由此确定，`rev.ng` 一类"提升式重编译"路线被排除**（它产出的是提升后的 IR，
代码进一个 `root` 调度循环 —— 恰好**不可读不可改**，与目的 2 直接冲突）。

| 约束 | 含义 | 对判据的影响 |
|---|---|---|
| **drop-in 替代** | 承接原厂全部资源与操作，用户无感 | 目标 1 就是验收标准；`_sdcard_drop` 真机复测仍是唯一终局判据 |
| **自有可维护源码** | 必须能读懂、能改，才能做功能升级 | 排除 rev.ng / 二进制打补丁 / 提升式 IR；**"用我们自己写的源码"这条不可妥协** |

**⇒ 因此出口不是某个工具，而是「差异类别收敛 + 每类上机械门禁」**：
每发现一类静默差异就把它变成一道自证的机械门禁；类别表清零 = 1:1 达成。
**现阶段已门禁的类别**（截至第 57 轮）：陈旧对象 16.56 · 编译口径 16.33 · 栈槽当循环边界 16.36 ·
延时循环被删 16.39 · 变参丢参 16.38 · `DT_INIT=0` 16.65 · 门禁缺陷态 16.66/16.67 · PT_LOAD 几何 16.69 ·
**RELRO 覆盖 .data 16.71** · **MMIO 宽度窄化（SIGBUS）16.76** · **volatile 分级 16.83** ·
**UB-DCE（工厂数据引用被 -Os 消除）16.99** · **重生成回退手工修复 17.01**。

★ **目的 2 的两个具体功能给出了升级靶子**（复刻收敛后即可动工，现只登记不实施）：
① **evdev 即插即用手柄** ⇒ 落点在输入层（现走 `read(/dev/input/jsN)` 的老式接口）；
② **策略游戏 SRAM 存取** ⇒ 落点在存档层（`retro_save_state`/`retro_load_state` + `.srm` 语义）。

**★ 新仪器（第 57 轮）：`tools/factory_fn_stack.py`** —— 离线反汇编**工厂函数**并按
`sp/fp` 常量位移分类统计**栈槽读/写**（capstone，自证 6 条）。
★ 已知局限（必须记住，别用它下过度结论）：**它只认 `[sp,#imm]` 直读**；工厂大量使用
`add rX, sp, #k` **把帧地址当指针**（`fjp` 不一定是帧指针 —— 实测 rkgame 里 `fp` 是 GOT 基址！
`add fp,pc,fp`），这类访问需要**帧指针别名数据流**才能判，当前会漏。**⇒ 仅用于分诊，不作判据。**

## 0.3 ⏸ **暂停点（2026-09-23 23:35 → 用户约定 13 小时后继续：2026-09-24 ≈ 12:35）**

**恢复后第一件事（按顺序，别跳）**：
1. `git`/推送通道已可用：远端 main = **`8143c074`**（推送由 `tools/push_1to1.py` 走 Contents API，本机无 `.git`）。
2. **查 `8143c074` 的 CI 是否全绿** —— 我在暂停前 3 分钟才推，`1to1-verify` 之前那轮（`afc6fa86`）已 success，
   这一轮要复核（尤其新增的 3 道门禁是否在 CI 上稳定）。命令模板见 `tools/` 里的既有做法或直接用 REST API `actions/runs`。
3. **本地复跑门禁确认产物未被中断的编辑破坏**：
   `PY=<python> sh tools/link_audit.sh report/link_audit.txt` → `sh tools/link_full.sh build/rkgame.rebuilt.elf`
   → 逐条跑 `mmio_*` / `elf_load_audit` / `relro_audit` / `abi_check` / `dyn_audit` / `check_obj_fresh` /
   `lint_const_args` / `verify_layout` / `prop_equiv` / `dce_ref_diff` / `check_regen_contract`。
   **期望**：`MISSING 0`、`★FAIL 0`、产物 **5,664,348 B**、10 个地址物化 10/10。
4. **然后继续主线（差异类别收敛）**。当前**未清的项**，按优先级：
   - **P1｜`prop_equiv` 的 8 个 WARN + 2 个 MISSING**（`run_process.constprop.0` 1.722、
     `GetZipItemA` 0.654、`ClearBuffer` 0.625、`popoffwindows` 0.620、`sunxi_gpio_output/set_cfgpin` 0.603、
     **`popwindows` 0.552**、**`ReadUSBJoy` 0.476**；MISSING = `code_convert.constprop.22`、
     `mui_outputxy_length.isra.19`）。其中 `popwindows`/`ReadUSBJoy` 已被标注"疑编译器分段 **或真的少实现**"
     ⇒ **必须到工厂反汇编核对**（现在有工具了）。
   - **P2｜`FBA_Load` 修后 size 比 = 1.356**（工厂 708 / 我们 960）—— 刚过 p95(1.33)。
     要确认我按「10 槽数组」还原是否**过头**（工厂那 10 个引用里可能真有死槽）⇒ 用
     `tools/factory_fn_stack.py --fn FBA_Load` 看工厂实际读了哪些槽。
   - **P3｜Δ 债务表 13 条**（已定性为低风险，保守保留）。清它需要"帧指针别名数据流"判据，成本高、收益低
     ⇒ **排在 P1/P2 之后**。
5. **真机仍是唯一终局判据**：`_sdcard_drop*/` 投放包与「t3（修复后）的 PC 是否还落在 0x501bXX」判据未变，
   等你要上机时再说 —— 但**在 P1/P2 清完前不建议再上机**（否则又是一轮只暴露一个错）。

**本轮新增/已入库的工具**（恢复后直接用，别重写）：
`tools/fidelity_source_deps.py`（刻度 A 正确仪器）· `tools/dce_ref_diff.py`（Δ 门禁 + 债务表）·
`tools/check_regen_contract.py`（重生成契约）· **`tools/factory_fn_stack.py`（工厂函数栈槽读/写，capstone）**。
★ 环境依赖：capstone 已装进隔离 venv；`D:/output/rkgame/decompiled/02-ghidra-c/03-per-function/`
有**Ghidra 逐函数原始 C 输出**（判定"我们是否改丢了东西"的权威对照，本轮才发现，务必用起来）。

## 1. 绝对红线（触犯即不可逆）

1. 原厂二进制 / 启动链**一律不动**：`icube` / `rkgame` / `driver.so` / 原厂 `cores/` / `autorun` / `avp.uImage` / SD 卡其余原厂文件。
2. **只覆盖我们自己构建的同名文件**；对抗原厂进程用 kill / SIGSTOP。
3. 改原厂文件前必须**先说「改什么 / 怎么改 / 如何回退」**。
4. 本仓**只有本 agent 在推送**。看到"没记得推过的提交"，先怀疑**上下文压缩丢记录**，**勿臆造外部 actor**。
5. 权威一手资料（§5）**只读，绝不可修改**。

---

## 2. 坑与"不要重复"（★ 数量 = 曾付出的代价）

### 2.1 ★★★★★ 构建产物一律不入库；缓存必须在「源 × 工具链 × flags」三元组上失效（GAP 16.56）
- `XUnzip.o` **从未被重编**。仓里那个是 **`-O1` 时代遗留**：`-O1` 编同一份 `unzip.cpp` = **147,896 B（逐字节同尺寸）**；`-Os` = **39,476 B**。
- 失效机制：记账哈希 == 当前源码哈希 ⇒ 每轮判"无需重编"。**GAP 16.33 的 `-Os` 修复在整个 XUnzip 库上从未生效。**
- 传染链（**同一根因 3 次复发，每次"修好"只是把失效点挪了个位置**）：
  ① 只在 `.o` 缺失时编 → ② `-nt` 比时间戳（checkout 后两侧 mtime 相同，判定不可靠）→ ③ 源码哈希缓存 + 为 `.o` 开"必须入库"例外。
- **代价**：所有基于"产物"的判据（symbol size / 反汇编 / 重定位 / 等价性差分）**不报错、只给出方向相反的结论**。
  我因此把"上游库版本不对"当根因，做了一次**完全没必要的大改**（GAP 16.54 已公开更正）。
- **纪律**：① 构建产物不入库、不进推送白名单；② **编译够便宜就不要缓存**（本项目单文件 **0.96 秒**）；
  真要缓存，键必须是**三元组**而非源哈希；③ **编译失败必须硬失败**（`exit 1` + 删目标对象），
  旧写法 `... && echo 已编译 || echo 失败` 会让链接器照样链旧对象 ⇒ 陈旧对象被永久钉死；
  ④ 门禁 = **现编一份，与磁盘对象 / 链接产物逐符号对拍**（`tools/check_obj_fresh.py`），
  并**反向自证**（喂 `-O1` 对象必须 FAIL）。
- **效果**：修后 zip 层符号命中工厂 ±15% 从 **11/41 → 27/41**（7 个精确到字节）。

### 2.2 ★★★★★ 别用静态体积比当进度刻度（GAP 16.43）
它只答"字节像不像"，对"哪条分支判反了"完全无感。
**可用刻度** = 执行集合差集 + 里程碑矩阵 + 轨迹对齐 + **符号落位率**。
实测：±15% 命中仅 **53%（393/741）**，348 个超差 —— 绝大多数是编译器习语，**不反映功能差距**。

### 2.3 ★★★★★ 看到"我们多执行 N 个函数"时，先查参照侧是不是早死了
执行集合是**集合**（无序、不含"谁先退出"）⇒ 一侧提前崩，另一侧就"凭空中多出"一整套它**本该也执行**的函数。
**固定动作**：① 先看两侧终止状态 + **控制组**（同一份参照二进制复跑 —— 唯一能区分"环境缺陷 / 行为分歧"的仪器）；
② 再做**纯 guest stdout** 的事件序列对齐找**首个分歧点**（★ 别混入即时输出的 stderr / 日志钩子）；
③ 最后才回源码看那个分支。**顺序反了就会去改本来正确的代码。**

### 2.4 ★★★★ 门禁不得依赖"可能不在 CI 里的文件"；一条门禁只留一条硬判据；上线前做三态自证（GAP 16.57）
- 新门禁连挂两轮，失败全在**辅助判据**，两次都是**依赖了 CI 里不存在的文件**（`1to1/.gitignore` 位置不对；`push_1to1.py` **含 token 不入库**）⇒ 判据恒假。
- 代价：两轮 CI 全废 + **每轮 10 个观测场景被 skipped**。
- **三态自证**：① 正常态 PASS ② 缺陷态 FAIL ③ **CI 近似态（挪走 CI 里不存在的文件）仍 PASS**。
- 推论：**一条脆弱的辅助判据把整轮 CI 烧掉，代价远大于它防的风险** ⇒ 辅助判据一律降级为提示。

### 2.5 ★★★★★ "看起来正常"的输出最危险 —— 七个仪器静默失效（GAP 16.52 / 16.63 / 16.66 / 16.67）
| # | 失效形态 | 纪律 |
|---|---|---|
| ① | 连续两次 `write` 用同一原始串 ⇒ 第二次**覆盖**第一次而脚本**照样打印 ✓** | 累积替换要**最后只写一次 + 写完读回 grep 校验** |
| ② | shell heredoc 把 `\\` 变 `\` ⇒ Python 三引号里 `\<换行>` 是**行接续**（吞换行）⇒ 锚点永不匹配 | 带反斜杠的补丁**写成文件再执行**，别走 heredoc |
| ③ | 关键地址必须 **8 位十六进制**：6 位 `010fec` 与轨迹 `/00010fec/` 不等 ⇒ **恒 0 命中**，而"0 命中"**看起来恰等于**"分支没走到" ⇒ 结论反向 | 一律 `'%08x'` |
| ④ | **0 命中必须有阳性对照** | 天然对照 = `00017dac` `mui_LoadUIResource` / `00012ebc` `FindZipItemA` 入口 |
| ⑤ | **"入口命中数" ≠ "调用次数"** —— GCC 内联会破坏它 | 我曾据此推出错误结论（GAP 16.63）；论"次数"必须配不可内联的旁证（strace syscall 计数） |
| ⑥ | **门禁的缺陷态必须用"会被引用"的对象** —— 无人引用的假符号**不会**报错 ⇒ 假绿 | GAP 16.66：`--wrap=X` 只在有东西**引用** X 时才产生未定义符号 |
| ⑦ | **门禁必须能区分"判据不成立"与"判据没跑起来"** | 读不到源文件也要**硬失败**（GAP 16.67；`exit 11`） |

### 2.6 ★★★★ 判据的探针必须是"该环境里确实应当存在"的对象
旧 `M6` 的探针 `font.ttf` **本就不在包里**（`ui_cn.zip` 只有 6 个条目，无字体文件）⇒ 三侧恒真 ⇒ 把唯一真实分歧抹平。
已加 **M6R**（只查包内应存在的 `ui.cfg` / `menu.raw`）。

### 2.7 ★★ 两个不同二进制对齐执行轨迹不能从下标 0 比（GAP 16.50）
CRT / loader 前导天然不同 ⇒ 必然立刻分歧。⇒ **锚点对齐**（默认 `main`）；**定不到锚 ⇒ INCONCLUSIVE**，绝不输出假绿。

### 2.8 ★ 加了硬失败必须去「所有调用点」查返回码（GAP 16.59）
CI 构建步骤用 `|| echo "[warn]"` 吞掉 `link_audit.sh` 的 rc ⇒ 新加的 `exit 1` 在那处**不生效**。
**兜底 = 基于文件存在性的断言**（`[ -s src/upstream/xunzip/XUnzip.o ] || exit 1`），不看 rc。

### 2.9 ★ 台账的 `status` 列不可当刻度
`ledger/functions.csv` **223 行全部仍是 `TODO`**（从未维护），而 213 个源文件已实装 ⇒ 进度只能用**符号落位 / 等价性**量。

### 2.10 ★★★★★ PT_LOAD 几何畸形（**真缺陷、已修 —— 但它不是真机失败的根因**）〔GAP 16.69 + 2026-09-22 更正〕
- 症状：**用户实测 16.6 MB 产物无法开机，`_diag/` 零日志**（"零"= 代码根本没执行到写日志那一步）。
- 根因：`linker/factory.ld` 把自有节**钉死在任意高地址**（`.data 0x01000000` / `.bss 0x02000000` / `.text 0x05000000`）。
  带写属性的 `.fini_array` 落在 `.rodata` 末尾（VMA `0x4e00e0`），lld 把它与 `.data` 归进**同一个 RW 段**
  ⇒ 该段必须跨过中间 **11.1 MB 地址空洞** ⇒ `p_filesz = 11,669,876`，且该段**吞掉承载全部代码的 `.text` 段**。
- 后果：内核 `set_brk` 取 `max(p_vaddr+p_filesz)` ⇒ brk 被推到 **268 MB**；叠加段地址重叠（后续段 `MAP_FIXED` 覆盖前段映射）
  ⇒ 2×Cortex-A7 小内存盒子**直接 `exec` 失败，失败发生在 `_start` 之前 ⇒ 一条日志都不产生**。
- 修复：去掉三个钉死地址，自有节紧接 `.rodata` 连续排布。**文件 17,331,448 → 5,663,812 B**，
  最高 vaddr **268 MB → 5 MB**，空洞 **11.1 MB → 172 KB**，真重叠 **0**。
- **为什么 14 道门禁全绿还是死了**（本轮最重要的元教训）：
  `abi_check` 只看 ELF 头 4 字段；`dyn_audit` 只看动态段；`verify_layout` 只看"符号是否落在 PT_LOAD 内"——
  **畸形段也是 PT_LOAD，符号照样"在里面"**；qemu / PC 内核对重叠段与超大 brk **都容忍**，行为差分照常 PASS。
  ⇒ **这些判据都只回答"地址对不对"，没有一个回答"这份 ELF 能不能被加载"。**
  新增第 15 道门禁 `tools/elf_load_audit.py`（6 条判据），并**直接钉进 `tools/link_full.sh` 末尾**（本地/CI 都绕不过，失败 `exit 12`）。
- **门禁自身两个坑（已修，GAP 16.69 内记录）**：
  ① A1 第一版把**合法的 NOBITS 跳段**判成跨洞 ⇒ **正常态直接 FAIL**（判据基准必须是"段必须覆盖的最外跨度"）；
  ② 只注入**一个**缺陷态就验证全部判据 ⇒ 误判"门禁未生效"；改成**每条判据各有缺陷态**后 4/4 命中。
- ★★★★ **2026-09-22 更正（必须记住）**：修掉 11 MB 空洞后的 5.4 MB 产物**在真机上仍然零日志**。
  ⇒ 这个几何缺陷**是真实的、值得修的**（它确实让 ELF 畸形、13 道门禁都没查过它），
  但**它不是我宣称的"根因"**。我当时把一个**未经验证的因果**当成了结论写下来 —— 这是本项目反复出现的
  同一类错误（对比 §2.1、"判据换刻度"）。
  **教训**：**"找到一个真缺陷" ≠ "找到根因"**。修完必须回真机复测，才允许写"根因"二字。

### 2.14 ★★★★★ 自报覆盖率不是证据；**"结构推演"也会一轮连错五次**

**（a）自报覆盖率不是证据。** 我把 B 线的 `gap-audit-v6.md`（自报 96%、"22/23 项真实现"）
当成了"成熟"的依据，但用户澄清：那条线**只实现了一个背景图和几条日志**。
⇒ 一条线的成熟度必须看**它实际能做什么**，不能看**它给自己打的分**。
同类风险：`ledger/functions.csv` 的 `status` 列（§2.9）、任何"自评报告"。

**（b）2026-09-22 一轮内我连续提出并**全部证伪**的 5 个假设**（每个都基于 ELF 结构反推行为）：

| # | 假设 | 证伪方式 |
|---|---|---|
| 1 | `PT_LOAD` 9 段 / 几何畸形导致内核拒载 | 设备实测：**exec 成功**（被信号杀，不是 errno）⇒ 加载层无责 |
| 2 | `GNU_STACK memsz=16MB / 栈 NX` 导致失败 | 同上；且 `mmap_min_addr=32768` 下 `0x9000` 无碍 |
| 3 | `DT_INIT` 指向 `.text` 段首（假的函数指针） | 本地核对：`DT_INIT = _init`，指令 `e92d4008 e8bd8008` = 合法空函数 |
| 4 | 跨段**共享页**导致数据错乱 | 页级精确计算：A 线**冲突页 = 0**（原厂/B线/探针也都是 0） |
| 5 | `.rel.dyn` 落在只读段 = 文本重定位而 `DF_TEXTREL=0` | 本地核对：A 线**全部落在可写段**（反而能跑的 B 线有 3 个文本重定位且正确设了 `DF_TEXTREL=1`） |

**⇒ 纪律**：**一旦「exec 已成功」，任何从 ELF 结构反推"加载失败"的分析都是错的方向。**
   剩下的只有**运行期观测**：崩溃地址（`ptrace` + `PTRACE_GETSIGINFO`）、PC/LR/SP、
   完整 `/proc/PID/maps`、程序自身的 stdout/stderr、`LD_DEBUG`。
   ★ 这是本项目第三次撞上同一堵墙（前两次：§2.1 用产物判据得出反向结论、§2.2 静态体积比当刻度）。

### 2.11 实验纪律
与历史数字对比**必须逐字复刻历史那组的完整开关集**（含旁路注入如 `CGM_KEY2_SEED`），否则不是单变量。

### 2.12 工具链坑（zig / MSYS）
- `CC_ARM` 是 zig 时**必须带 `-target`**；给 **native `zig.exe` 的路径必须是 Windows 形式**（`D:/...`）——
  MSYS `/tmp`、`/d/...` ⇒ **静默不产出文件** / `CacheCheckFailed`。
- ★ **zig 只认单横线 `-Wl,-wrap=<sym>`**，`--wrap=` 会被驱动层直接拒绝（GAP 16.65）。GCC 走 `--wrap=`。
  自证方式：加 wrap 后产物的**未定义符号里该符号消失**（不是"参数被接受"）。
- 桩构建脚本**必须给 outdir**。CNB 容器**空闲即回收** ⇒ 先 `sh tools/cnb_env.sh`（幂等）、实验**攒成一条命令**；
  **编译与链接必须同一个 zig**。
- Shell 环境偶发损坏（PATH 丢失）⇒ 用 Python 直接读写文件，或改用 PowerShell。

### 2.13 推送
- 新文件必须登记进 `push_1to1.py` 的 `FILES`（**仓库根级文件不在 `os.walk` 目录里**）。
  walk 目录 = `src / upstream / ledger / tools / docs / linker`。★ `golden/` **不在其中**。
- 改 workflow YAML 后**必须重跑解析校验**（`tools/lint_workflow_continuation.py`）。
- 纯文档推送已用 `paths: !1to1/*.md` 排除。
- ★ Artifact 可本地分析：`actions/artifacts/<id>/zip`（302 签名 URL 要去掉 `Authorization` 头）。

---

### ★★★★★ 2.15 「工厂数据引用被 -Os 整体消除」—— 静态门禁**完全看不见**的一类（2026-09-23，GAP 16.99）

**根因**：Ghidra 把工厂栈上**一个连续缓冲**按类型拆成若干独立局部量，而原指令用
`p = &local_150; p = p + 1` **跨对象步进** ⇒ C 的**未定义行为** ⇒ 编译器把后续槽的写入**整体删除**。
实测 `core/FUN_002b6c14_FBA_Load.c`：`-O0` 有 11 个工厂数据引用、`-Os` 只剩 2 个 ⇒
原厂「10 条候选 core 路径」退化成 1 条，而**编译/链接/ABI/布局/几何全绿**。

**修法**：按工厂**真实结构**还原成一个数组（偏移与总字节数不变）⇒ 步进合法、引用全保留。
**门禁**：`tools/dce_ref_diff.py`，判据 = Δ = `UNDEF(-O0)` 减去 `UNDEF(-Os)` 的工厂符号；
自证 9 条；存量 13 个文件登记在工具内 `ALLOW`（**必须缩小**），表外新增即失败。

### ★★★★★ 2.16 「重生成会静默回退手工修复」+ 生成器与产物必须做**幂等**验证（2026-09-23，GAP 17.01）

`tools/regen_data.sh` 重写 `linker/factory.ld` 与 `src/data/factory_image.S`，而这两份含手工修复
（16.69 不再钉死运行时区地址 / 16.71 RELRO 族拆分 + 页对齐）。生成器没跟上 ⇒
**每跑一次 regen 就静默回退一次**（实测复现）。另：Windows 上生成器会把文本产物写成 CRLF。
**纪律**：凡"生成物含手工修复"，① 生成器必须与修复版**逐字节一致**；② 每次生成后做
**幂等性验证**（重生成 vs 已提交版本 diff = 0）；③ 上契约门禁（`tools/check_regen_contract.py`，自证 7 条）。

### ★★★★★ 2.17 「口径错」与「真缺陷」长得一样 —— 判据的**代表元**与**名字归一化**是两个独立失效点（2026-09-24，GAP 17.03）

一天之内连踩两次，**两次都先被我自己的仪器误导**：
1. **代表元错**：`prop_equiv` 归一化后只取"指令数最多"的**一个克隆**（我们侧还先按原名取）
   ⇒ 两侧都不是"组内求和" ⇒ 当 GCC/clang **对称地**把函数拆块时，"我们偏小"可能纯属伪影。
   修法：`tools/equiv_group_sum.py` 组内求和后再比（自证 13 条）。实测 `run_process`、
   `GetZipItemA` 在组求和后**转 OK**。
2. **名字归一化漏一种写法**：我们的 C 标识符不能带点 ⇒ 转录 `code_convert.constprop.22` 时
   写成 `code_convert_constprop_22`；而 `norm_name` 只剥**点号**形式 ⇒ 我方永远配不上
   ⇒ 被误报 **MISSING**（实测 2 个，真实体量比 1.139 / 1.108，**都是 OK**）。
   ★ 纪律：归一化必须**双向自证**（工厂点号形式 ↔ 我方下划线形式），并**锚定名字结尾**，
   否则会误伤正常名（如 `foo_part_bar`）。

**★ 结论性判据（本轮定案，写进判据体系）**：
> 体量比偏小 **不能**单独定性为"少实现"。必须再叠一条**源码级**证据：
> **我们的源码是 Ghidra 逐函数输出的逐行转写（恒定 +5 行），且调用总数不减少**
> （门禁 `tools/src_transcript_parity.py`）。满足 ⇒ 定性为 **codegen 差异**，不阻塞替代。

### ★★★★★ 2.18 新门禁的判据**首版必然过严或过松** —— 必须在全量数据上跑一遍再定阈值（2026-09-24，GAP 17.04）

`src_transcript_parity.py` 首版拿"调用**名集合**不同"当 FAIL ⇒ 全量跑出 5 个**假阳性**
（`OpenZipU` G5/O5、`GetZipItemA` G2/O2、`FindZipItemA` G2/O2、`UnzipItem` G2/O2、`CloseZipU` G4/O4
—— **总数完全相同**，只是 C++ 成员函数 / `new`/`delete` 的写法改名）。
⇒ 收紧为「**调用总数变少**才 FAIL」，名不同归 INFO，语句数偏少归"待核"。
**纪律**：新判据先跑全量、看假阳性分布、再定阈值；**别用单样本的直觉定阈值**。

## 3. CI / GitHub 铁律

- `push_1to1.py` 增量推送；**无变更必须早退**（POST 空 tree ⇒ 422 不可重试）。
- 门禁步骤**不得带 `continue-on-error`**；关键计数显式硬断言（`exit 1` + `::error::`）。
- **Token 绝不入库**，从 `.pat` / 环境变量读。
- 本机 **FastGithub MITM** 拦截 GitHub 域名（TLS `Server: FastGithub`）⇒ urllib 必须 + `ssl._create_unverified_context()`。
  （完整环境坑与绕过配方见 `~/.workbuddy/MEMORY.md` 的"本机 GitHub 推送环境"节。）
- Actions 月预算 **2000 分钟** ⇒ 每轮必须有信息增量；**并发 run 要及时取消被覆盖的那些**。
- 工作流：`.github/workflows/1to1-verify.yml`（静态门禁）+ `1to1-qemu-behav.yml`（9 场景行为差分 + 普查）。

---

## 4. 设备事实（权威）

- 形态 = **游戏盒子**（HDMI + 内置扬声器），**无命令行** ⇒ 真机验收 = SD 部署 + 设备自写 `menu.log`。
- SoC **RK3036G**（2×Cortex-A7 @1008MHz / Mali-400MP），kernel 4.4，busybox 1.27.2。
- 全部 ELF = **ARM32 hard-float**：`e_machine=0x28`、`e_flags=0x05000400`。
- **glibc 2.29** ⇒ `zig cc -target arm-linux-gnueabihf.2.29`；
  `PT_INTERP` 必须 `/lib/ld-linux-armhf.so.3`（写错 ⇒ 内核 ENOENT **静默拒载**）。
- 启动链：`U-Boot → kernel → init → rcS → S80icube → exec /sdcard/cubegm/icube → rkgame`。
  挂载点 `/sdcard`。
- ★★ **唯一注入点 = `LD_LIBRARY_PATH` 抢占** —— 但设备启动链全原厂，**我们改不了任何环节**
  ⇒ **`LD_PRELOAD` / 环境变量方案在真机上无注入点，不存在**。
  ⇒ **诊断能力只能编进 rkgame 自己**（见 §8）。
- 本机**无 qemu、无 Docker**，`wsl.exe` 被拦 ⇒ 行为差分只能跑 CI 或 **CNB 云容器**。

---

## 5. 权威一手资料（优先于任何推断；**只读，绝不可修改**）

- `F:\OTHER\D20游戏机\解包归档\`：`org.bin`(8MB GPT 固件) + `rootfs解包/` + `原厂SD卡/`
- `D:\output\原厂SD卡根目录结构\`：整张原厂 TF 卡（`000`–`008` + `cubegm/` + `root.dat`(725KB)
  + **`fileinfo_decoded.txt`(2.37MB) = 真实 `fileinfo.txt` 内容**）
- `golden/sdcard_min/`（CI 用最小 SD）：
  - **`ui_cn.zip` 4,951,281 B = 原厂同尺寸真文件**，**标准 ZIP**，6 条目 =
    `ui.cfg` / `menu.raw` / `search.raw` / `setting.raw` / `type.raw` / `game.raw`
  - ⇒ **`font.ttf` 不在包内**
  - 结构实测：`EOCD@4,951,259`、`offset_central_dir=4,950,716`、`size_central_dir=543`、`comment=0`
- `golden/device_rootfs_min/`（设备精确 sysroot，13 文件 / 3.82 MB）；生成器 `tools/make_device_sysroot.py`
- `golden/factory.rkgame.bin`（原厂 rkgame，3,921,108 B）+ `golden/factory.funcs.json`（Ghidra 反汇编缓存）
- ★ **sysroot 是一等实验变量**：device(2.29) vs jammy(2.35) **执行路径实质不同**，结论必须标口径。
- ★ `root.dat` / `NNN.dat` **不是标准 ZIP**：4 字节伪装签名（本地头 `57 51 57 03`、EOCD `57 51 57 01`），
  字段未混淆、CRC 逐位过。

### 5.1 ★ SD 卡盘符与设备侧写入痕迹（2026-09-22 实测）

- **SD 卡 = `L:` 盘**（顶层：`000`–`008` / `cubegm` / `Roms` / `root.dat`）。
  ⚠ 过去清单里的 `J:` 已不存在；**每次都要重新确认盘符**，别按记忆里的字母找。
- **设备侧写入的文件 mtime = `01-01 00:00`（或 1980-01-01）** ⇒ 设备时钟未设置，
  这正是**"这个文件是设备写的、不是电脑拷的"的判据**（电脑拷入的文件是当前时间）。
- `L:/cubegm/` 里由**设备侧**写出的文件（⇒ 说明曾有产物成功跑起来）：
  `recent.lst`(5,580 B) · `favorites.lst`(1,779 B) · `setting.xml`(819 B) · `menu.log`(444 B) · `PROBE.txt`(422 B)
- `L:/cubegm/rkgame.bak` = **3,921,108 B = 原厂 rkgame**（用户已备份 ✓，可作阳性对照）。
- `L:/cubegm/rkgame` 会随每次投放被覆盖 ⇒ **读它之前先记 size/sha256**，否则无法回溯测的是哪一版。

### 5.2 本地资产地图（`D:/output/` 下与本项目相关的目录）

| 目录 | 内容 |
|---|---|
| `rkgame-1to1/` | **本记忆所在（A 线主仓）** |
| `rkgame/` | 早期工作区：原厂 `rkgame`(3,921,108 B) + `decompiled/` + `ghidra_proj/` + `icube_analysis/` + `sramshim/` |
| `rkgame-rebuild/` · `cnb-rkgame/` · `cnb-rkgame-final/` | **B 线**的三个本地副本 |
| `rkgame-first-successful-build/` | B 线 2026-09-09 一天内 6 次迭代的产物（rkgame / v2 / v3 / v4 / v5 / v7） |
| `v15-rkgame/` | **B 线 v15 产物**（1,031,860 B）+ **`V15-ARM-GATE-CHECKLIST.md`（真机验证清单）** |
| `v9-backup/` · `v10-backup/` · `v12push/` · `v13push/` | B 线历史版本与**推送工具链**（`push_v13/v14/v15.py` + `monitor_ci.py` + 构建日志 152/180 KB） |
| `qemu_art70..75` · `_art*` | 各轮 CI artifact 的本地解包 |
| `_pristine/` | 上游 `unzip.cpp` 原版（对比基准） |
| `原厂SD卡根目录结构/` | 整张原厂 TF 卡快照 |

### 5.3 远端仓库结构（⚠ 与本地路径**不是**一一对应）

| 远端 | 说明 |
|---|---|
| `1to1/**` | A 线全部内容（由 `tools/push_1to1.py` 从本地 `rkgame-1to1/` 推上去） |
| `rkgame-rebuild/**` | B 线源码 + `output/rkgame` |
| `.github/workflows/`（**根级**） | 三个 workflow：`1to1-verify.yml`、`1to1-qemu-behav.yml`、`build.yml`。★ **根级 workflow 也由 `push_1to1.py` 推送**（本地 `.github/workflows/*.yml` → 远端**根级**同路径；第 92–93 行显式登记 + 第 196 行 glob 自动纳入）⇒ **本地没有的 workflow 就是"孤儿"，无法维护** |
| `artifacts` 分支 | **B 线的 `build.yml` 自动写入**：`auto: rkgame build artifact (N bytes)` + `auto: qemu e2e test PASS/FAIL` |

- ★ `build.yml` 的 `on: push: branches: [main]` **没有 paths 过滤** ⇒ 每次推送（含纯文档）都会跑一轮（实测约 1 分钟）。
  **这不是浪费**：它是 B 线唯一的持续验证；且带 `concurrency: cancel-in-progress: true` ⇒ 连续推送不会累积。
  **结论：不要为了省这一分钟去改它**（改它 = 破坏 B 线的验证链，且它有既定的设计意图）。

---

## 6. 工程布局与常用命令

```
D:/output/rkgame-1to1/
  linker/factory.ld        链接脚本（自有节连续排布；勿再钉死地址 —— 见 §2.10）
  src/proprietary/*.c      213 个专有函数重建（526,629 B，中位 1,163 B，无空壳）
  src/upstream/xunzip/     上游 zip 库（现用源 + 项目 CFLAGS 现编）
  src/compat/              crt / 桩
  src/diag/                设备端诊断仪（cgm_diag.c / cgm_wrap.c / cgm_diag.h）
  src/probe/               最小探针（probe.c / start.S，3,572 B，静态无 interp）
  tools/                   编译、门禁、推送、符号化、投放（见下表）
  golden/                  CI 用最小 SD + 设备 sysroot + 原厂 rkgame
  build/                   产物（不入库）
  _sdcard_drop/            投放包（给用户拷卡）
  _diag/                   设备端日志输出（运行时生成）
```

**本地全量重建（判据秒级可跑）**
```sh
ZIG="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe"
export CC="$ZIG cc" OPT=-Os
export PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
export ZIG_GLOBAL_CACHE_DIR="C:/Users/Administrator/AppData/Local/Temp/zgc3"
PY="$PY" sh tools/link_audit.sh report/link_audit.txt   # 编译全部源 + 对象新鲜度
PY="$PY" sh tools/link_full.sh   build/rkgame.rebuilt.elf  # 只做链接 + 几何门禁
sh tools/build_diag.sh   build/rkgame.diag              # 诊断版（≈2 分钟）
sh tools/build_probe.sh  build/rkgame.probe             # 最小探针
PY="$PY" sh tools/stage_sd_diag.py                      # 生成 _sdcard_drop/
```

**15 道门禁（`tools/`）**
| 工具 | 判据 |
|---|---|
| `link_audit.py` | 未定义 / 重复定义符号 |
| `link_audit.sh` | 编译 + **XUnzip.o 每次必重编** + 失败 `exit 1` |
| `check_obj_fresh.py` | **现编对象 vs 磁盘对象 / 链接产物逐符号对拍**（三态自证） |
| `abi_check.py` | `e_machine` / `e_flags` / `interp` / glibc 版本 |
| `dyn_audit.py` | 动态段 / 初始化链（`DT_INIT` 曾为 0 ⇒ SIGILL） |
| `verify_layout.py` | 符号是否落在 PT_LOAD 内 + 工厂全局映射 |
| **`elf_load_audit.py`** | **PT_LOAD 几何 6 条**（跨洞 / 重叠 / 对齐 / 最高 vaddr / 段数 / 文件大小）**⇒ 钉进 link_full.sh** |
| `prop_equiv.py` | 213 个专有函数逐函数静态等价性 |
| `exec_set_diff.py` | 9 场景执行集合差集 |
| `milestones.py` | 13 锚点里程碑矩阵 |
| `scan_varargs_fns.py` | `log_dummy` 丢变参 |
| `scan_dead_loop.py` / `scan_delay_loops.py` | 死循环 / 延时循环被当死代码删 |
| `lint_workflow_continuation.py` | workflow YAML 续行 / 结构校验 |
| `diag_wraps.sh` | DIAG `--wrap` 列表 ↔ `cgm_wrap.c` 实现**一一对应**（编译前跑，失败 `exit 11`） |
| `_diag_gate_selftest.py` | 上述门禁的**三态自证** |

**判决性仪器**：`CGM_TRACE_ADDRS`（逐地址 `grep -c`，**必须 8 位十六进制 + 阳性对照**）。

---

## 7. 现状快照（滚动更新 · 最后更新：第 55 轮 / 2026-09-22）

**权威进度口径**：工厂 **804** 有名函数 = **581 上游开源**（61.3%）+ **223 专有**（38.7%，122,922 B）。

| 口径 | 实测 | 工具 |
|---|---|---|
| 工厂函数落到**我们的 `.text`** | **741 / 804 = 92.2%**（0 个仍指向 `.fimg_text`；63 "缺失"几乎全是 GCC `.constprop/.isra/.part` 特化，**非真缺失**） | 符号落位（§7.1） |
| 专有函数重建 | **213 / 223** 源文件实装（526,629 B、中位 1,163 B、**无空壳**） | `find src/proprietary -name '*.c'` |
| 静态等价性 | **213/213，★FAIL 0，p50 = 1.03** | `tools/prop_equiv.py` |
| 执行集合差集（9 场景） | **7/9 同步**；仅工厂执行 = **2 个**（`ClearBuffer` = 我们的 memset 尾调用 / `run_process.constprop.0` = 内联） | `tools/exec_set_diff.py` |
| 里程碑（13 锚点） | **7/9 同步**；仅 C5/J 差集 = {M6R, M7}；**M7「菜单存活」已达成** | `tools/milestones.py` |
| ABI / 链路 / 动态段 / **PT_LOAD 几何** | 全 **PASS**（未定义 0、重复定义 0、`e_flags`/`interp` 字段级一致、几何 6/6） | 见 §6 门禁表 |
| 验收矩阵 N1–N6 | N1/N2/N3 **PASS**；N4/N5 进行中；**N6 真机验收：2026-09-21 首次做 = 失败（§2.10），已修，待复测** | `STATUS.md` §四 |

**体积**：工厂 3,921,108 B（动态链接，7 个 `DT_NEEDED`）；修复后重建 **5,663,812 B**（5 个 NEEDED，少 `libstdc++`/`libgcc_s`，已登记可接受）。
修复前是 17,331,448 B（含 11.1 MB 空洞）—— 那个产物是真机开机失败的第一份。

### 7.0 ★★ 两条线的真机成绩（**这是"能否替代"的最关键一行**）

| 线 | 产物 | 真机结果 |
|---|---|---|
| **A 线（本仓 `1to1/`）** | 5.4 MB / 5.7 MB | **从未成功**：17.3 MB 与 5.4 MB 两次上机均**零日志**；只有 3.5 KB 的**静态探针**能跑（见 §9.1） |
| **B 线（`rkgame-rebuild/`）** | 1,031,860 B | **已上机跑过**（`V15-ARM-GATE-CHECKLIST.md` 引用 pre-v15 设备日志；设备侧 `recent.lst`/`favorites.lst`/`setting.xml` 为其所写） |

⇒ **在"设备能不能正常用"这个问题上，B 线是领先的一方。** A 线的领先项只有"结构忠实度"。

### 7.1 符号落位算法（可复用刻度）
工厂 symtab 每个 `FUNC` 名 → 查产物 symtab 的 `st_value`：
落在产物 `.text` 即"已由我们重编"；落在 `.fimg_text`（嵌入的工厂原码）即"未替换"。
实测 **741 重编 / 0 落在 fimg / 63 "缺失"**。

### 7.2 唯一瓶颈 = 观测窗口（**不是代码**）
- 沙箱下**工厂侧**读不出 UI 资源包（工厂 9 场景 `exit=139`；我们 124）。
- 定位链已被两轮普查收进单函数：`SearchCentralDir` 命中 ✓ → `unzOpenInternal`(4) → `unzGoToFirstFile`(1)
  → `GetCurrentFileInfoInternal`(1) → **`Compare` = 0 / `GoToNextFile` = 0 / `unzLocateFile` = 4**
  ⇒ 精确吻合原版 `unzip.cpp:3247` 的 `if(!s->current_file_ok) return UNZ_END_OF_LIST_OF_FILE;` 早退。
- ★ 但 **GAP 16.62–16.64 推翻了我早期的定位链**：
  ① 工厂的 `GetCurrentFileInfoInternal` **根本没有 magic 比对**（厂商删掉了，反汇编逐条证实）
     ⇒ "magic 比对失败"这个头号嫌疑**不成立**；
  ② `CGM_TRACE_ADDRS` 的**"入口命中数"不能当调用次数**（GCC 内联会破坏它）
     ⇒ 我"4 次 open 有 3 次提前失败"的推断**建立在它之上，因此不可靠**；
  ③ 唯一站得住的是**内核 strace**（模型无关）：两侧 IO **前 12 步逐条相同**；工厂 **6 种 seek 目标** vs rebuild **82 种**；
     **工厂从未顺序读资源数据**（rebuild 有 12,288 B 步长的顺序读）。
     且**两侧都从未 seek 到真实中央目录偏移**（都只 seek 到 `filesize−3313`）⇒ zip 访问**很可能是内存模式**。
- ★ 判定：我们侧**不是缺陷** ⇒ **不阻塞替代、只阻塞验证**。
- ★ 结论：**不要再在沙箱里挖了** —— 沙箱里工厂自己就崩，沙箱不是验收场；
  继续挖得到的是"沙箱缺什么"的知识，不是"能不能替代"的知识。**下一步只能靠真机。**

### 7.3 已修的真缺陷（证据全在 `GAP.md`）
陈旧对象 16.56 · 编译口径 `-Os` 16.33 · Ghidra 栈槽当循环边界 16.36 · 延时循环被当死代码删 16.39 ·
`log_dummy` 丢变参 16.38 · 判据换刻度 16.43 · `DT_INIT=0` ⇒ SIGILL · **zig 只认 `-Wl,-wrap=`** 16.65 ·
门禁缺陷态 16.66 / 16.67 · **PT_LOAD 几何畸形** 16.69。

### 7.4 已登记豁免的编译器习语（清单见 GAP）
`ClearBuffer` 0.625（memset 尾调用）· `sunxi_gpio_output/set_cfgpin` 0.603（条件执行融合）·
`UpdateROM` 0.123（编译器分段）· `TUnzip::Unzip/Get`（GCC 冷热分割）· `mxmlSaveFile` 34.3×（内联）。
**待核（非豁免）**：`popwindows` 0.552 · `ReadUSBJoy` 0.476（疑编译器分段）。

### 7.5 xunzip 上游
- 口径已对齐：**现用源 + 项目 CFLAGS 现编** ⇒ 命中工厂 **27/41**，**不需换版本**。
- `TUnzip::Unzip` 已按工厂改（工厂**不用 `len`** 参数）；`.o` 不再入库。
- 已登记的唯一保真度差异：工厂 `lufread` **内存分支**有一个 `spi_memcpy` 钩子（工厂侧是**空 4 B 函数**），
  我们的移植硬编码成了 `memcpy`。**只在 `flags==1`（内存模式）走** ⇒ 不是 C5 失败原因，
  ★ 但 16.64 的内核证据（zip 可能走内存模式）**重新激活了这个假设，必须复查**。

---

## 8. 设备端诊断仪（DIAG）—— 设备无 CLI 时唯一的取信息手段

**为什么必须"编进自己"**：设备启动链全原厂（红线）⇒ **没有任何地方能注入 `LD_PRELOAD` / 环境变量**。

**两条零源码改动的注入**（都是编译/链接期开关）：
| 手段 | 粒度 | 抓到什么 |
|---|---|---|
| `-finstrument-functions` | 函数级 | 每个函数进入/退出 → **65536 帧环形缓冲**（768 KB）＝崩溃前约 3.2 万次调用的完整历史 |
| `-Wl,-wrap=<sym>` × **65** | 调用级 | 文件 open/read/write/lseek/stat · **`ioctl`（DRM/KMS/ALSA/evdev 全走这里）** · mmap · `dlopen`/`dlsym` · 线程 · 时间 · 信号 |
| 信号处理器（只用 async-signal-safe 调用） | 崩溃级 | 信号 / `si_addr` · 全部寄存器 · fp 链 · **栈扫描** · `/proc/self/maps`（离线符号化必需）· 打开的文件列表 |
| 心跳 + 每 5 s 快照 | 存活级 | **区分"卡死"与"崩溃"**；卡死或断电也**不丢最近历史** |
| 启动横幅 | 环境级 | environ / cmdline / maps / auxv / status / meminfo / cpuinfo / mounts |

- 级别在 `_diag/cfg.ini`（**默认 3 = 最全**）。
- `sh tools/build_diag.sh`（≈2 分钟）→ `sh tools/stage_sd_diag.py` → `_sdcard_drop/`；
  取回日志后 `tools/diag_symbolize.py build/rkgame.diag <frames.bin>` 符号化（用法见 `DIAG-RUNBOOK.md`）。
- ★ **最小探针** `sh tools/build_probe.sh`（3,572 B，**静态、无 `.interp`、无 NEEDED**）：
  一进去就用**原始系统调用**往 7 个路径写文件 + 涂帧缓冲，用来分开
  **"内核不肯 exec 我们的产物"** vs **"跑了但写不出文件"** —— 这条判据不依赖任何库。

**已知限制（诚实登记）**：
① `.fimg_text`（嵌入的工厂原码，是**数据**）不会被插桩 —— 但 741/804 个工厂函数已由我们自己的 `.text` 提供；
② fp 链可能不可用（交付口径 `-Os` 默认省帧指针）⇒ 已用**栈扫描 + 环形缓冲**兜底；
③ 上游库（mxml / stb / xmp3）未插桩，只做了 libc 级 wrap。

---

## 9. 待办与下一步

### 9.1 ★★★★★ **已确证根因：音频（ALSA）初始化序列与原厂不同**（2026-09-22，看完设备全部数据后）

**证据来源**：程序**自己打印的** stdout/stderr（探针 v3 把子进程 fd1/fd2 重定向落盘）
= `_diag/p3_<N>_out.txt`。★ 这是最直接的一手证据 —— **一眼就能看出差异**。

| 候选 | 程序自身输出（关键行） | 结局 |
|---|---|---|
| **原厂 `rkgame.bak`** | `rkgame v1.42` → `open driver.so sucess` → `video_driver_setting 0 1 1` → `open drm!` → **`snd_pcm_start failed: -32`** | **存活至超时** |
| **t1 = A 线 rebuilt** | 同样 `open driver.so sucess` → `open drm!` → **`failed to apply hwparams: -22`** | **SIGBUS(7)** |
| **t2 = A 线 diag** | 同上 | **SIGSEGV(11)** |
| **t5 = B 线 v15** | `=== rkgame rebuild starting ===` ×2 → **`failed to apply hwparams: -22`** | 存活（但**根本没走到 DRM/音频**） |

ld.so 侧（`_diag/ldd_.*`）同一时刻的轨迹：

```
calling init: /mnt/sdcard/cubegm//driver.so        ← driver.so 打开**成功**
calling init: /lib/libnss_files.so.2
/usr/lib/libasound.so.2: error: symbol lookup error:
    undefined symbol: _snd_pcm_rate_linear_open_conf (fatal)
```

**⇒ 根因链（已确证）**
1. A 线产物**成功**打开 `driver.so`、**成功**初始化 DRM，走到了 **ALSA 音频初始化**；
2. 设备上的 `libasound.so.2` **缺少插件符号 `_snd_pcm_rate_linear_open_conf`**（`(fatal)`）；
3. 我们的调用序列命中了这个缺口 ⇒ `apply hwparams` 返回 **-22 (EINVAL)** ⇒ 进程被杀（SIGBUS/SIGSEGV）；
4. **原厂在同一个位置只报 `snd_pcm_start: -32 (EPIPE)` 并继续存活** ⇒
   **我们的 ALSA 调用序列与原厂不同** ⇒ **这就是 1:1 该对齐的点**。

**★★ 重要反转（必须记住）**：**A 线不是"坏"，而是"走得更远才崩"。**
它走到了 `driver.so` + DRM + 音频；而 B 线 v15 连 DRM/音频都没走到
（只有 `rkgame rebuild starting` 两行）⇒ 所以 B 线"看起来能跑"。
**A 线功能比 B 线深得多** —— 这正是 1:1 复刻该走的深度。

**★ 崩溃现场（探针 v3，保留为事实）**
- t1：`SIGBUS(7)`，PC = **`sfc_init+0x6c`**，`si_addr = 0xB6F2B02C`
- t2：`SIGSEGV(11)`，PC = **`cgm_diag_boot+0x184`**（`str r0,[r1]`），`si_addr = 0x4e1010` = `g_lvl`
- ⚠ 探针抓的 `/proc/PID/maps` 只取到 1 行（ptrace-stop 状态下读取不完整之嫌）⇒ **maps 不作为证据**。

**★★★ 下一步（1:1 方向，明确且很小）**
**对齐原厂的 ALSA 初始化序列**：把原厂反汇编里 `snd_pcm_*` 的调用顺序/参数
与 `src/proprietary/*` 里的实现逐条对照，差异即缺陷。
（相关入口：`FUN_0000d678_InitDisplay.c` 等 `hw/` 下的音频初始化路径；
`dlopen(..., 2)` 的 2 = `RTLD_NOW`，需与原厂（反汇编里的 flags）核对。）

### 9.1b ★ 另一条更有希望的捷径（B 线）
B 线（`rkgame-rebuild/`）**已在真机跑过**、产物 1,031,860 B、qemu e2e 每次 push 都 PASS、自报覆盖 96%。
⇒ **在 A 线继续攻坚前，值得先确认 B 线的产物在设备上的实际表现**（它有 `V15-ARM-GATE-CHECKLIST.md`
列出的 3 个具体 bug 的修复版）。这可能**直接给出"能用的版本"**，而 A 线的价值在于"结构忠实度"。

### 9.2 后续（真机通了之后）
| 序 | 事项 | 状态 |
|---|---|---|
| 3 | 中文 UI / 全菜单 / 起始屏幕走查 | 未开始 |
| 4 | 游戏启动（`cores/config.xml` 已注册核心） | 未开始 |
| 5 | 存档 / 记忆卡 | 未开始 |
| 6 | 音频 BGM | 未开始 |
| 7 | 8 个静态 WARN 复核（`popwindows` 0.552 / `ReadUSBJoy` 0.476） | 待核 |

### 9.3 判定：1:1 可分两种，结论相反
- **字节级 1:1**（逐字节相同）：**不可行，且不该追求**。已登记 5+ 处**编译器习语**差异（工具链版本/内联策略的产物，不是代码错误）；
  项目在 GAP 16.43 已主动把"体积比"从刻度里删掉。
- **功能/语义 1:1**（可替代运行）：**可行**，代码侧已走 **92.2%**，无已知结构性障碍。

### 9.4 诚实声明（不要忘）
- 修复（§2.10）**尚未在真机验证过** —— 投放包就是去验它的。
- 曾经把**从未上机测过**的 16.6 MB 产物交给用户，那是真正的失误；**这类缺陷只有真机会暴露**，
  而真机验收（N6）恰是项目里长期缺的那一格。
- "741/804 已重编" ≠ "功能正确"：它只证明符号落位。语义等价目前只有两份证据：
  `prop_equiv`（**只能当探针**）+ 沙箱行为差集（窗口有限）。
- 沙箱里"我们 124 vs 工厂 139"**不是我们更强** —— 是工厂侧在沙箱缺一环而早死。拿它当"更接近原厂"是错误解读。

---

## 10. 本记忆的迁移史（防止再被压缩）

| 时间 | 事件 |
|---|---|
| 2026-09-22 | **用户指出 `MEMORY.md` 不该记单项目内容**。本项目记忆从 `D:\output\.workbuddy\memory\MEMORY.md`（长期被压到 12.7 KB、仍超 3,000 字符限制、尾部注入时被截断）**迁到本文件**（项目文件夹内，不受限制）。workspace 那份改为**指针**；`~/.workbuddy/MEMORY.md` 中的 CubeGM 项目内容同步迁往 `C:\Users\Administrator\cubegm-work\PROJECT-MEMORY.md`，只留跨项目偏好。 |
| 2026-09-22 | ★★★★★ **用户质疑路线偏移**（「往以前放弃那个方案推进？而不是 1:1 复刻」）→ 新增 **§0.1 路线判据**：把「忠实度差异收敛」立为唯一判据（刻度 A/B/C，工具 `tools/fidelity_audit.py`），明确「能不能跑」不得当刻度；定位到架构级矛盾（3.90 MB 工厂镜像 vs 1.32 MB 自有；9,997 处引用；92 函数未重编）。探针 v3 定案：崩在 `cgm_diag_boot+0x184` / `sfc_init+0x6c`。 |
| 2026-09-22 | ★★ **用户澄清：B 线是已废弃的浅实现**（只实现背景图 + 几条日志），并批评我「拿它当可用版本」是懒。更正 §0/§7.0，新增 §2.14（自报覆盖率不是证据 + 结构推演一轮连错 5 次）。探针 v2 真机定案：exec 成功、A 线 SIGBUS/SIGSEGV ⇒ 转向探针 v3 抓崩溃现场。 |
| 2026-09-22 | ★ **发现 B 线 `rkgame-rebuild/`**（见 §0）：此前记忆**完全没有这条线**，导致"替代差距评估"片面。同时收到用户真机实测结果（动态零日志 / 静态成功）⇒ §9.1 重写；**更正 §2.10**（PT_LOAD 不是根因）。新增 §5.1 SD 卡盘符（=`L:`）、§5.2 本地资产地图、§5.3 远端结构。 |

## ★ 2026-09-22 第二轮真机定案（本轮最新，前置于此前的 §2.10-§2.14 之上）

### A. 两个根因（都已修，机器码级证据）

| # | 根因 | 证据 | 修法 | 新门禁 |
|---|---|---|---|---|
| **A** | **`PT_GNU_RELRO` 覆盖 `.data`** ⇒ 内核页取整后 `.data` 页只读 ⇒ **写自己的全局变量即 SIGSEGV** | 真机 t2：`SIGSEGV si_addr=0x4e1010`（= diag 的 `g_lvl`）、PC `cgm_diag_boot+0x184`；本地 `PT_GNU_RELRO=0x4e00e0+10940`（页区间 0x4e0000-0x4e3000）而 `.data`@0x4e1000 在内。**原厂是正确范例**：RELRO 终点 0x3aefe0 恰停在页对齐的 `.data`(0x3af000) 之前 | `.data.rel.ro`/`.got`/`.dynamic` 各自成段排在 `.data` **之前**；`.data` 页对齐。修后 RELRO 页区间 0x4e0000-0x4e2000、`.data`@0x4e2000 可写 | `tools/relro_audit.py`（页面级，三态自证）→ `link_full.sh` exit 13 |
| **B** | **工厂的立即数 44100 被反编译成符号 `UpdateROM`** ⇒ 传 `driver.so` 的采样率 ≈5,128,288 ⇒ `snd_pcm_hw_params` **-22(EINVAL)** | 工厂 `InitSound` @0xdb54 是 `movw r1,#44100`；`44100==0xAC44` **恰等于**工厂 `UpdateROM` 的地址。真机：原厂 `snd_pcm_start -32`（无害）vs 我们 `failed to apply hwparams: -22`（致命） | `(*sound_driver_init)(USE_HDMI_OUT,44100,2)`；修后机器码 `movw r1,#0xac44` 与工厂逐条一致 | `tools/lint_const_args.py`（213 函数对拍）→ `link_full.sh` exit 14 |

**A 为何此前 15 道门禁全绿**：所有判据都在看"地址对不对、符号在不在段里"，
**没有一条看「可写节是否落在 RELRO 页里」** —— 而它决定"运行期第一秒是否就死"。

### B. 一处必须记住的自我更正（工具假缺陷）

我曾断言「`sfc_init` 的 `mmap` 第 6 实参（偏移 0x10208000）没入栈、是垃圾值 ⇒ SIGBUS」。
**作废**：`0xE1CD60F0` 是 **`strd r6, r7, [sp, #0]`**（64 位存储），被我的 `arm_dis.py`
误解成 `strh r6, [sp, #0]`（把 bits[7:4]==0xF 归进半字分支）。`sfc_init` 与工厂**逐条等价**。
已修解码器 + 加 4 条编码回归自证。
⇒ **纪律**：**用工具产出的"缺陷"，必须先验证工具本身**（已知编码回归 + 每分支一条正例）。
   t1 的 SIGBUS 因此**仍未定**，下一轮用修好的探针 v3 重新采集。

### C. 本轮门禁总表（共 18 道；新增 3 道全部钉进 `link_full.sh`，本地/CI 都绕不过）

`elf_load_audit`(exit 12) · **`relro_audit`(exit 13)** · **`lint_const_args`(exit 14)** ·
`link_audit` · `abi_check` · `dyn_audit` · `verify_layout` · `check_obj_fresh` ·
`prop_equiv` · `scan_varargs_fns` · `scan_dead_loop` · `scan_delay_loops` …
修后本地全绿（`prop_equiv` ★FAIL 0；`lint_const_args` 213 函数对拍 0 命中）。

### D. 下一步（唯一动作）

**第 4 轮真机投放**（`_sdcard_drop4/`，说明见其中 `READ-ME-FIRST.txt`）：

| 目标 | 内容 | sha256 前 16 | 期望 |
|---|---|---|---|
| `cubegm/rkgame` | 探针 v3（已修：无符号十六进制、maps 上限 3800、补印 r1-r12） | `ddfa476cef1c420e` | 给出候选的 errno/信号/崩溃现场 |
| `cubegm/rkgame.t1` | ★ 修复后的交付版 | `65118fa2f8331bfd` | **能起、能进菜单** |
| `cubegm/rkgame.t2` | ★ 修复后的诊断版 | `fe4520d0291b86ea` | **这次应真的写出 `_diag/` 日志** |
| `cubegm/rkgame.t4` | 最小动态 ELF（对照） | `40c21f787db83e9f` | 已知 exit=0 |
| `cubegm/rkgame.t5` | B 线 v15（对照） | `5dce646b9ce3a1ed` | 已知存活 |
| `cubegm/rkgame.bak` | 原厂（阳性对照，**必须已在卡上**） | — | 已知存活 |

判读：t1 起来 ⇒ 进入逐项走查（菜单/游戏/存档/音频）；仍崩但有 `_diag/` 日志 ⇒
按符号表定位到源码；连 t2 都零日志 ⇒ 崩在 init_array 之前，继续收敛。

## ★ 2026-09-22 第二轮真机定案（续：读全设备数据后）

### A. 设备实测确认（第 4 轮，`_sdcard_drop4` = 探针 v3 + 修复版 t1/t2）

| 项 | 结果 |
|---|---|
| **采样率 44100 修复** | ★ **被真机证实**：应用自己打印 `snd_pcm_start failed: -32` —— 与**原厂逐字相同**（此前是致命的 `failed to apply hwparams: -22`）；ld.so 侧 `undefined symbol: _snd_pcm_rate_linear_open_conf` 的 fatal 随之消失 |
| **RELRO 修复** | ★ **被真机证实**：诊断版这次**真的跑起来了**（`env.txt`/`trace.log`/`maps.start.txt`/`frames.snap.bin` 全写出；maps 里 `.data` 为 `rw-p`）；帧序列 = `main → get_executable_path → GetConfig → dispmeninfo → InitDisplay` |
| 剩余阻塞 | `t1` 崩在 `sfc_init` 读 SFC 寄存器：`SIGBUS(7) si_addr=<mmap基址>+0x2C PC=sfc_init+0x6c`，`r7=0x10208000 r0=mmap基址` |

### B. 第三/四个根因（本轮已修，机器码级证据）

| # | 根因 | 证据 | 修法 | 新门禁 |
|---|---|---|---|---|
| **C** | **MMIO 访存宽度被编译器窄化** | 工厂 `ldr r3,[r2,#44]`（32 位读 SFC+0x2C）+ **先写后读**；我们成了 `ldrh r1,[r0,#44]`（16 位）+ **先读后写**（同一惯用法在 `sfc_request` 里还有一处，9 个调用者） | 设备寄存器指针一律 `volatile`：`sfc_init` 局部 `regs`、`globals.h` 的 `g_sfc_reg`、`sfc_request` 的 `puVar3/puVar5` | `tools/mmio_width_audit.py`（对照工厂访存宽度直方图，三态自证）→ `link_full.sh` **exit 15** |
| **D** | **诊断仪自身：AArch32 上 `va_list` 被当普通实参转发** | `trace.log` 全参数错位 + `SIGSEGV PC=vfmt+0x1c4 si_addr=0x32323534` | 拆 `vfmt_ap(...va_list)` + 薄包装 `vfmt(...)`；并给 `cgm_putline` 加 `format(printf,2,3)` 属性（此前 `-Wformat` 对它**完全不检查**） | 编译期 format 检查（现 0 警告） |

★ **D 类缺陷在 x86-64 上不复现**（那边 va_list 是数组）⇒ 只能靠设备端证据抓。

### C. 联网核实的硬件事实

`0x10208000` = **RK3036 SFC**（`sfc: spi@10208000`，`compatible = "rockchip,sfc"`，
**`status = "disabled"`**）；时钟 `hclk_sfc` = `CLKGATE_CON(3) bit14`、`sclk_sfc` = `CLKGATE_CON(10) bit5`。
厂商写的 `CRU+0xF0`（"CLKGATE8_CON"）**与 SFC 时钟无关** ⇒ 厂商并未自行开 SFC 时钟，
说明这些寄存器在设备上本来可达 ⇒ 方向应是**"访问方式与工厂一致"**，而不是"补时钟"。

### D. B 线的设备实证（供参考，不用于 A 线决策）

`rkgame.log`（B 线自己写的 10,413 行日志，28 个会话、单会话最长 205 s）反复打印
`sfc_init: stub (no SFC hardware; …)` / `spi_driver_init: stub` ⇒ ① 当时就判定"无 SFC 硬件"并跳过，
照样进菜单；② 它也证实 `driver.so`/`setting.xml`/`joystick.zip`/菜单渲染在本机都正常。
**A 线仍按"与工厂逐条等价"处理**（不开跳过先例）。

### E. 下一步（唯一动作）

第 5 轮真机投放 `_sdcard_drop5/`：`cubegm/rkgame`=探针 v3、`rkgame.t1`=三处修复后的交付版、
`rkgame.t2`=修复后的诊断版（**这次应写出 `_diag/` 全套日志**）、t4/t5 对照、`rkgame.bak` 阳性对照。
判读：t1 进菜单 ⇒ 进入逐项走查；仍崩但有 `crash.txt`/`frames.bin` ⇒ 直接按符号表定位。

---

## ★ 路线决策（2026-09-22）：停止"逐个差异 → 当根因 → 上机 → 再找一个"

**详细分析在 `ROUTE-DECISION.md`**（本文件只留结论与纪律）。用户质疑「确认不是在转圈？」
⇒ **是转圈**，机制：从「重编后机器码与原厂在**硬件可观测语义**上不同」这个**类**里，
每轮采样一个成员当根因。两个结构性成因：
① 门禁是**抽样式**的（`mmio_width_audit` 硬判只有 2 个函数白名单）；
② 沙箱**不能复现真机硬件约束**（SIGBUS 只在真机出现）⇒ 每次判定耗一次上机。

**工厂工具链指纹（实证，GAP 16.80）**：
- 工厂 = **GCC 6.2.0**（`.comment`）+ 启动文件 Linaro 4.9.4 + **GNU gold 1.12**（`.note.gnu.gold-version`）
- 我们 = **clang 21.1.0**（zig 0.16.0）+ **lld**
- ⇒ **跨编译器家族 + 跨链接器**的差异，不是版本号差异
- ★ **`tools/cnb_env.sh` 第 38 行本来就会装 `gcc-arm-linux-gnueabihf`** —— 这条工具链一直在手边，
  本项目**从未用过**（构建脚本默认值就是 `CC="${CC:-arm-linux-gnueabihf-gcc}"`）。
  已登记为"单命令可做的对照实验"（compile-only 对拍，不涉链接 ⇒ 绕开 GCC 对象 + zig 链接的 glibc 冲突）

**类的边界（量化）**：真正做设备寄存器访问的只有 **2 个文件**（`sfc_init.c`、`sunxi_gpio_init.c`），
机械推导出 **11 个函数**；213 个 `.c` 里只有 **3 个**出现过 `volatile`（17 次）。⇒ **面很小，本该一轮做完。**

**纪律（本轮新增，全部有实证）**：
1. **凡从 `mmap` 设备基址派生的指针，声明与所有派生游标必须"整块" `volatile`。**
   ★ **只对单次访问强转 `volatile` 挡不住重排**（GAP 16.81 的 C 变体实证：宽度锁住了、顺序仍错）。
2. **缺陷态必须与真实代码形状逐字同构**（16.83）：我第一版实验让上半字参与运算 ⇒ 复现不出窄化。
3. **只修"已被证实的"，对"未证实的同类"建检测器让它自己说话** —— 避免把"理论风险"当缺陷改。
4. **`volatile` 不是 MMIO 的完备解**（LKML/内核实证）：要走**内联汇编访问原语**才能与编译器解耦。
5. 单条脆弱的辅助判据会烧掉整轮 CI（16.57）⇒ 类级门禁的噪声必须"只登记不判决"。

**新增门禁（2 道，均已钉进 `link_full.sh`）**：

| 门禁 | 类型 | 自证 | 失败码 |
|---|---|---|---|
| `tools/mmio_semantics_test.py` | **法条级**：4 条断言（窄化可见 / 整块 volatile 正确 / 单次强转是反例 / 原语零自由度） | 正常 exit0 · `--selftest` 通过 · 注入坏源码 exit 11 | — |
| `tools/mmio_access_audit.py` | **类级**：函数集机械推导（11 个）+ 单向判据"不得比工厂更窄" | 自证①修复前产物报 3 处 · 自证②自比零差异 | **16** |

**剩余缺口（如实登记）**：① "访问**顺序**"目前只有法条级断言，未做全函数顺序对拍；
② 沙箱仍不能复现 SIGBUS（方向：QEMU memory region `.valid.accepts` 拒绝窄访问 ⇒ machine check）；
③ 换 GCC 的对照实验未做。

---

## ★ 工具链与协作平台（2026-09-23 实测结论）

### 工厂编译器指纹（`.comment` + `.note.gnu.gold-version`）
- 工厂 = **GCC 6.2.0**（+ 启动文件 Linaro 4.9.4）+ **GNU gold 1.12**
- 我们 = **zig 0.16.0 → clang 21.1.0** + **lld**
- ⇒ 差异是**跨编译器家族**，不是版本号差异。

### ★ 判决实验：**换 GCC 不是方向**（已证伪，别再花时间）
| 编译器 | ±15% 命中 | 中位体积比 | 直方图 L1 中位 |
|---|---|---|---|
| clang 21.1.0（现用） | **77.6%** | **0.965** | **0.443** |
| GCC 13.3（Ubuntu） | 1.9% | 0.553 | 2.000 |
复现：GitHub Actions workflow `gcc-vs-clang-fidelity`（`tools/gcc_fidelity.sh` + `tools/fidelity_compare.py`）。
⇒ **保真度杠杆在源码层语义，不在编译器**（与 ROUTE-DECISION §五①② 一致，现在有实证）。
口径：工厂是 GCC 6.2.0，实验用的是 13.3 ⇒ 只证明"13.3 更差"，不证明"GCC 家族都不行"。

### AC Git 镜像（git.acwing.com/lieguch/cubegm-rkgame，GitLab 14.2.3-ee）
- **CI 不可用**：实例**无任何 Runner**（`/runners`=[]；untagged + 10 种 tag 的作业 25 分钟无人领走）。
  要跑构建必须**先注册 Runner**（项目级即可）。`/help` 对 API token 返回 401，程序读不到。
- 密钥身份 = 项目机器人 `project_45404_bot`（仓库 45404 的 Project Access Token），角色 **Maintainer(40)** ⇒ 可直推受保护的 `main`。
- **镜像已落地 1282 文件**（含 `golden/` 金标准、`1to1/` 全量、`.gitlab-ci.yml`）；安全核对：`.pat`/`push_1to1.py` 不在库。
- 同步命令：`ACGIT_TOKEN=... python tools/sync_acgit.py [--dry-run]`（清单复用 `push_1to1.py --list-only`）。

### ★ 两条 Windows 特有的 git 坑（都踩过）
1. `git fetch <url> <ref>` **必须带凭据** —— 只给 push 带凭据 ⇒ fetch 静默失败 ⇒ `origin/main` 陈旧 ⇒ push 被 `non-fast-forward` 拒。
2. Windows **没有真实 exec 位**（`core.filemode=false`）⇒ `chmod` 不生效；要写进树必须是 `git update-index --chmod=+x`。

### CI 红色事件的复盘（8d6fbe1e → b293276c）
- `1to1-verify` 红：我把 `volatile` 加在**全局**上 ⇒ 严格口径 2 处"丢弃限定符"类型错。
  修法见 GAP 16.86（设备块指针 volatile / RAM 游标不加 / 非访问点显式转型 / **拆分被 Ghidra 复用的变量**）。
- `1to1-qemu-behav` 红：`mmio_width_audit.py` 只找 `golden/factory.funcs.json`，而**仓库里只有 `.gz`**。
  治理：建 `tools/factory_data.py` 作**唯一**加载入口；并立纪律"**CI 近似态自证**（藏掉本地独有文件后再跑一遍）"。

### 第 50 轮（2026-09-23）关键结论（**只增不删**）

- **SIGBUS 根因闭环（机器码级）**：`sfc_init+0x6c` = `e1d012bc` = `ldrh r1,[r0,#0x2c]`
  —— 在 mmap 的 `/dev/mem`（SFC 寄存器，物理 `0x10208000`）上做 **16 位访问** ⇒ 总线外部中止 ⇒ SIGBUS。
  修复版同点为 `str r4,[r0]`（先写）+ `ldr r1,[r0,#0x2c]`（32 位读）。**MMIO 必须 `volatile` + 32 位宽度 + 顺序对齐工厂。**
- **唯一改动函数是 `sfc_request`**（676→704 B）；`sfc_init` 逐字节相同、仅平移 +0x1C。
  ⇒ 查"改了没生效"**必须用整体符号级差分**（`tools/elfdiff.py`），不能只 diff 目标函数。
- **构建确定性**：`link_full.sh` 重建 `rkgame.rebuilt.elf` → 同一 sha256 `b5a25a13758b1cbbc19a`。
  ★ 但 **`link_full.sh` 不能用于诊断版输出**（会把 diag 覆盖成非 diag）；diag 必须用 `build_diag.sh`。
- **投放纪律（新增硬规则）**：投放前必须做「设备文件 ↔ 本地产物」**尺寸/sha256 逐项对账**，
  并写进 `DEPLOY-MANIFEST.txt`（`tools/stage_sd_probe4.py` 已机械产出）。
  上一轮整轮设备成本白花，就因为投放的是修复前的产物。
- **仪器纪律（强化）**：① 探针 maps 上限必须容得下崩溃时的全部映射（`/dev/mem`+`libnss`+4×6MB `/dev/dri`+7.5MB 匿名 ≈ >7 KB）；
  ② 崩溃现场必须带**栈**，否则拿不到调用链；③ **先证明仪器可信，再读仪器给的数**
  （`VARCHK` 自证行：期望值与实测值并列）。
- **垫片坑**：`cfg.ini` 解析**必须跳过注释行**（注释里的同名键会劫持真值）；
  `vfmt_ap` **会丢弃格式串里的 `\n`**（横幅之类的多行输出要自己补）；中文字面量**编译后在设备上会乱码** ⇒ 仪器输出一律 ASCII。
- **真机事实**：`t4`(2,628 B) exit=0、`t5`(B 线 1,031,860 B) 存活至超时 ⇒
  **内核 exec + `ld.so` 动态链接 + 我们自己的代码在真机上都 OK**；
  A 线 t1 的 stdout 与原厂**逐行相同**（直到 `snd_pcm_start failed: -32` 之后才分岔）。
  原厂 stdout 里的 `Unknown format 875713089` = `0x34325258` = `DRM_FORMAT_XRGB8888`。

### 第 51 轮（2026-09-23）平台分工定案（**只增不删**）

- ★ **三件套（用户口径，定案）**：**cnb.cool 托管 + cnb.cool 云开发 + GitHub 构建**。
  项目仓库 = **`cnb.cool/lieguch/cubeGM`**；AC Git 降级为归档（无 Runner，非主路径）。
- **CNB 云开发 = 本机缺 qemu 的解法**：`cnb workspace start-workspace --repo lieguch/cubeGM --branch main`
  启动后**可直接 SSH**（出站，不开本机端口）：`ssh cnb-uq8-1k36cqrdk-001.…@cnb.space`；
  容器 8 核 / 16 G / root / apt。进入项目根 `/workspace/rkgame-1to1/1to1` 跑
  **`RUN_DIFF=1 sh tools/cnb_env.sh`** ⇒ qemu-arm-static 10.0.13 + sysroot + /sdcard + 差分全通。
  ★ 云端用 **GCC**（重建产物 17 MB），本地用 **zig**（5.6 MB）⇒ **产物不可跨环境混用**。
- **同步工具**：`tools/sync_mirror.py --remote cnb|acgit`（复用 `push_1to1.py --list-only` 同一清单，
  dry-run 区分"纯新增 / 非纯新增"）。首次落地：`cubeGM` main `c666bc5..2dc38af`，1288 文件**纯新增**，
  B 线原有内容（`.cnb.yml` / `rkgame-rebuild/` / `rkgame-debug-28800`）**全部保留**；
  **安全核对 `.pat` / `push_1to1.py` 均不在库**。
- **三条 git 坑（务必别再踩）**：
  ① `credential.helper` 自定义命令**必须 `!` 前缀**（否则 git 调 `git credential-<name>`）；
  ② `git push HEAD:main` / `git fetch <refspec>` **单参数会被当成仓库名** ⇒ `ssh: Could not resolve
  hostname head`；必须显式给远端名；
  ③ 同步脚本里的 `reset --soft origin/main` 会**吞掉未推送的提交**（dry-run 之后要重新 commit）。
- **CNB 凭据**：`cnb login` 的 token 在 `~/.cnb/token`（`access_token` 前缀 `cnb_at_`），
  git 侧走助手 `credential.https://cnb.cool.helper = '!cnb git-credential'`。


---

## ★ 启动链模拟已跑通（2026-09-23，第 52 轮）—— 平台与方法的定案

**一句话**：**qemu 里能跑通原厂完整启动链**（kernel → busybox init → rcS → S80icube → icube → driver.so → **rkgame v1.42**），
全链路 ≈ **1 秒**，**可无限重跑、不占真机、不碰 SD 卡**。用户口径「不要再靠插卡穷举」由此成立。

- **入口**：`sh tools/bootchain.sh [秒数]`（在 CNB 云开发环境的仓库 1to1/ 目录下）
- **材料**：`bootchain/assets/`（11 MB，已入库）或 `tools/extract_bootchain_assets.py` 从 F: 归档重建
- **U-Boot 层**：正式定案为**跳过**（`-kernel/-initrd/-append` 是其职责的等价替换，且它在 qemu 上必挂）
- **不可再犯**：`-nodefaults`（无串口输出）／手写 cpio padding（差 2 字节）／`vmlinuz-virt`（404，正确名是 `vmlinuz-lts`）／
  `setsid` 后台 + ssh 轮询（CNB 环境闲置 3–5 分钟即回收）
- **下一跳**：`gr_init` @ driver.so+0x3ca8 的 `ldr r3,[r3]`，r3=0 ⇒ 查 libdrm 桩是否被采用


---

## ★ 启动链第一个卡点闭环（2026-09-23）—— `gr_init` → `open_drm()` 返回 NULL

**根因（离线静态分析，指令级）**：
`driver.so` 的 `gr_init` 调 **`open_drm()`（driver.so 自身实现，非 libdrm）**，
`open_drm()` 直接 `open("/dev/dri/card0")` + `ioctl()` ⇒ 沙箱无该设备 ⇒ 返回 NULL
⇒ 存入 `.bss(0x171cc)` ⇒ `0x3ca8 ldr r3,[r3]`（`0xe5933000`）解引用 NULL ⇒ 崩。

**已实测排除的错误方向**：把 `libdrm.so.2` / `libkms.so.1` / `libasound.so.2` 桩
覆盖到沙箱 `/usr/lib` 后，**崩点逐字不变** ⇒ `open_drm()` 不走 libdrm API ⇒ **桩拦不住**。

**下一跳**：给 `tools/guest_shim/fake_mem.c` 加 `/dev/dri/card0` 的 `open()`/`ioctl()` 拦截
（系统调用层伪造），而不是继续做 libdrm 桩。

**方法学收获（可复用）**：
- ARM32 `.plt` 的项长需**实测**：本项目 `driver.so` 是 **PLT0=20 B（含字面量）+ 每项 12 B**，
  共 71 项与 `.rel.plt` 一一对应 ⇒ 才能把 `bl <plt_va>` 精确落到外部符号。
- PLT 三元组的匹配掩码必须**掩掉 bit0-11(imm12)**：`(w0&0xfffff000)==0xe28fc000`、
  `(w1&0xfffff000)==0xe28cc000`、`(w2&0xfffff000)==0xe5bcf000`（我曾用 `0xffff0fff` 而 0 命中）。
- **判定"某库桩是否被采用"不能只看行为**：要直接解析调用点落到哪个符号；
  本次正是靠这一步发现"崩因根本不是 libdrm 桩"。


---

## ★ 真实设备路线（2026-09-23）—— 用户"不要假桩"的落地

**原则转变**：不再用 shim「让硬件初始化假成功」，改为**用真实内核驱动提供真实设备**。

| 需求 | 真实方案（非桩） | 实测证据 |
|---|---|---|
| DRM | `-global virtio-mmio.force-legacy=false -device virtio-gpu-device` + 内核 `virtio_gpu` | `/dev/dri/card0` major 226、`[drm] Initialized virtio_gpu` |
| ALSA | 内核 `snd-dummy` | `/dev/snd/controlC0` + `pcmC0D0p` |
| 模块来源 | `tools/fetch_kmods.sh`（Alpine modloop-lts 同版本同构建） | 2449 .ko |
| 注入 | 新增 `/etc/init.d/S00cgmmod` | 不动任何原厂文件 |

**突破**：`cannot find/open drm` 21→**0**、`gr_init` 崩 21→**0**、`DRM_IOCTL` 0→**63**、rkgame 进入 **21 轮主循环**。
**新卡点**：`DRM_IOCTL_MODE_CREATE_DUMB failed ret=-1`（需取 errno）→ `Unknown format XR24` → `double free`。
**下一跳**：ARM32 探针取 errno；若因 virtio-gpu 能力不足 ⇒ 需 qemu 侧 RK VOP 模型。

**关键判据（已实测）**：`-global virtio-mmio.force-legacy=false` 是**必须的**（qemu 默认 legacy ⇒ 不加 `VIRTIO_F_VERSION_1`
⇒ 内核 `virtgpu_kms.c:110` 拒绝加载 ⇒ `/dev/dri` 永不出现）。加后 `virtio0.status` 由 `0x83` → **`0x0f`**。


---

## ★ qemu-sim 套件已交付（2026-09-23）—— 跨项目复用

**用户要求**：把整套 qemu 模拟仿真系统（流程/所需文件/环境参数）复制到
`cnb.cool/lieguch/CubeGM_RetroArch`，写好使用文档，供另一 Agent 推进对应项目。

**已交付**（CNB `lieguch/CubeGM_RetroArch` main，提交 `20785ce` + `365732e`）：

```
qemu-sim/
├── README.md / ENVIRONMENT.md / ASSETS.md / PITFALLS.md / HANDOFF.md   5 份文档
├── .gitattributes         ★ 固化 LF（本仓库 core.autocrlf=true，否则 .sh 检出变 CRLF 不可执行）
├── run.sh                 一键：装依赖 → 取内核/模块 → 解 rootfs → 组装 → 启动 → 9 条里程碑判定
├── scripts/               fetch_kernel.sh / fetch_kmods.sh / mk_initramfs.sh / extract_assets.py
├── templates/S00cgmmod    新增式加载脚本（不动任何原厂文件）
└── assets/                11 MB 材料 + sha256（kernel.zImage / rootfs.sqsh / rk3036.dtb / sdcard/）
```

**文档中主动指出的冲突**（证据驱动，非断言）：本套件从**原厂 org.bin** 实测设备 glibc = **2.29**
（`lib/libc-2.29.so` + 版本串 `GNU C Library (Buildroot) stable release version 2.29.`），
而该项目既有文档写「glibc ≤ 2.17」⇒ 已在 README §0 列出证据链，请接手方复核其 `verify_target_abi.sh`。
（用户已确认：**同一设备、不同系统方向，设备信息以原厂 1:1 这条线的资料为准**。）

**交付质量动作（可复用清单）**：
1. 每个 `.sh`/`.py` 过 `sh -n` / `ast.parse`
2. 材料带 sha256，可逐字节对账
3. **检查 `core.autocrlf`**：本仓库为 `true` ⇒ 必须在本子树加 `.gitattributes` 固化 LF
4. 文档每条参数都写"为什么"，并单列"**明确的限制**"（哪些行为不具参考性）
5. 单列"**未完成项**"与判据（不要让下一个 Agent 重新发现）
