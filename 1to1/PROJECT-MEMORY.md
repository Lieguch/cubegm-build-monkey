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

## 0. 一句话

把原厂 `rkgame`（闭源 ARM32 菜单引擎）**用我们自己写的源码功能等价地重建**，产物同名覆盖到 SD 卡后**设备能正常开机使用**。
远端仓库 `Lieguch/cubegm-build-monkey`，本地 `D:/output/rkgame-1to1/`。

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

### 2.10 ★★★★★ PT_LOAD 几何畸形 ⇒ 真机上 `exec` 直接失败（GAP 16.69，**首次真机测试的根因**）
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
修复前是 17,331,448 B（含 11.1 MB 空洞）—— **那个产物就是真机开机失败的那一份**。

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

### 9.1 当前阻塞：真机复测（两步）
1. **先试修复版**：`_sdcard_drop/cubegm/rkgame`（5.4 MB，sha256 `278f04fb46e88118`）+ `cubegm/rkgame.probe` 拷到 SD 卡，
   插卡开机**等满 90 秒**。
   - **有日志** ⇒ §2.10 的根因成立，修复有效 → 把 `_diag/` 发回来，继续推进。
   - **仍无日志** ⇒ 做第 2 步。
2. **最小探针**：`rkgame.probe` 改名成 `rkgame` 再跑一次 ⇒ 一票分开"内核拒载" vs "写不出文件"，**不需要再改代码**。
- 回退：把 `rkgame.factory.orig`（用户备份的原厂件）改名回 `rkgame` 即可。**用户实测回退路径有效**。

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
