# PROJECT-MEMORY — rkgame 1:1 复刻（**权威项目记忆**）

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

### 9.1 当前阻塞：**A 线产物 exec 成功、但在初始化阶段崩**（真机实测已定案到这一层）

**探针 v2 的真机结果（2026-09-22，用户实测，决定性）**

| 候选 | 结局 | 判定 |
|---|---|---|
| 1 原厂 `rkgame.bak` | 存活至超时 | ✅ **阳性对照通过** ⇒ 探针结论可信 |
| 2 B 线 v15 | 存活至超时 | exec 成功（但见 §0 澄清：其功能深度很浅） |
| 3 **t4 最小动态 ELF**（2,628 B） | **正常退出 exit_code=0** | ✅ **动态链接链路完全正常** |
| 4 **A 线 rebuilt**（5.4 MB） | **被信号终止 signal=7** | ★ **SIGBUS（总线错误）** |
| 5 **A 线 diag**（5.7 MB） | **被信号终止 signal=11** | ★ **SIGSEGV（段错误）** |

★ 全程**没有任何 `EXECVE-FAILED`** ⇒ **内核与 ld.so 都放行了** ⇒ 加载层（含内核、`.interp`、
NEEDED、重定位、RELRO）**全部无责**。崩在**程序自己的初始化阶段**，且在写第一行日志之前。

**设备环境事实（探针带回，权威）**
| 项 | 值 |
|---|---|
| `vm.mmap_min_addr` | **32768 (0x8000)** ← 原厂最低 vaddr 正好贴线；我们 `0x9000` 更安全 |
| kernel | **Linux 4.4.194**（Linaro GCC 6.3.1，编译于 2022-11-07） |
| 根文件系统 | `/dev/root` **squashfs ro** |
| SD 卡 | `/dev/mmcblk0p1` → **`/mnt/sdcard`** `vfat rw,noatime,uid=1000,gid=1000,fmask=0022,dmask=0022` |
| `/dev/shm` | `tmpfs rw,mode=777`（可用） |
| `/sdcard` | 存在且可写（探针写 `/sdcard/...` 全部成功；应是指向 `/mnt/sdcard` 的链接或同挂载） |
| 静态 ELF 的映射 | 探针自身 4 段：`0x10000/0x20000/0x31000/0x41000` —— **段间 64 KB 间隔** |

**下一步：探针 v3（抓崩溃现场）—— 投放包 `_sdcard_drop3/`**

| 目标 | 内容 | sha256 前 16 |
|---|---|---|
| `cubegm/rkgame` | **探针 v3**（9,440 B，`ptrace` 版） | `4df33d7f2dcb40da` |
| `cubegm/rkgame.t4` | 最小动态 ELF（2,628 B） | `40c21f787db83e9f` |
| `cubegm/rkgame.t1` | A 线 rebuilt 5.4 MB（SIGBUS） | `b6b4ee6d8364e7e9` |
| `cubegm/rkgame.t2` | A 线 diag 5.7 MB（SIGSEGV） | `278f04fb46e88118` |
| `cubegm/rkgame.t5` | B 线 v15（对照） | `5dce646b9ce3a1ed` |
| `cubegm/rkgame.bak` | **阳性对照**（原厂，须已在卡上） | — |

v3 新增四项能力（v2 做不到）：
1. `ptrace` 让父进程当 tracer ⇒ **exec 成功后停在第一条用户指令**，dump 此时**完整 `/proc/PID/maps`**
   ⇒ 直接看出**有没有段没映射上**；
2. 崩溃时 `PTRACE_GETSIGINFO` 取 **`si_addr`**、`PTRACE_GETREGS` 取 **PC/LR/SP** ⇒ **可离线符号化到函数**；
3. 子进程 **stdout/stderr 重定向到 `_diag/p3_<N>_out.txt`** ⇒ 目标程序与 glibc 的错误全部落盘；
4. 传 `LD_DEBUG=libs,init` + `LD_DEBUG_OUTPUT` ⇒ ld.so 自己的步骤日志（`_diag/ldd_<pid>`）。

**要取回的文件**：`_diag/PROBE3.txt`（主）+ `_diag/p3_0..5_out.txt` + `_diag/ldd_*`（若有）。

**已排除项（不要再重复查）**：PT_LOAD 几何、`GNU_STACK`、`DT_INIT/DT_FINI`、跨段页冲突、
文本重定位、NEEDED/INTERP 存在性、`mmap_min_addr`。逐条证据见 §2.14(b)。

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
| 2026-09-22 | ★★ **用户澄清：B 线是已废弃的浅实现**（只实现背景图 + 几条日志），并批评我「拿它当可用版本」是懒。更正 §0/§7.0，新增 §2.14（自报覆盖率不是证据 + 结构推演一轮连错 5 次）。探针 v2 真机定案：exec 成功、A 线 SIGBUS/SIGSEGV ⇒ 转向探针 v3 抓崩溃现场。 |
| 2026-09-22 | ★ **发现 B 线 `rkgame-rebuild/`**（见 §0）：此前记忆**完全没有这条线**，导致"替代差距评估"片面。同时收到用户真机实测结果（动态零日志 / 静态成功）⇒ §9.1 重写；**更正 §2.10**（PT_LOAD 不是根因）。新增 §5.1 SD 卡盘符（=`L:`）、§5.2 本地资产地图、§5.3 远端结构。 |
