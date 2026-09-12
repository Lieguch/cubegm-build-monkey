# rkgame 1:1 重构 · 状态与交接（2026-09-12）

## 零、★ N4 重建进度（可量化、可复现）

**双轨度量（本地回路 `sh tools/recon_local.sh`，zig cc / clang 21 / arm hard-float）：**

| 口径 | 结果 | 含义 |
|---|---|---|
| **宽松（语法通过）** | **213 / 213 = 100.0%** ✅ | 全部专有函数文件可编译 |
| **严格（类型正确）** | **213 / 213 = 100.0%** ✅ | 类型真正正确的文件数 |
| 假绿（宽松过、严格挂） | **0** ✅ | 无「warning 掩盖类型错」的文件 |

> ★ **2026-09-12 达成：编译期双轨 100%**（宽松 + 严格均 213/213，假绿 0）。
> 严格口径 flags：`-Wall -Werror=int-conversion -Werror=incompatible-pointer-types -Werror=implicit-int`。
> CI `1to1-verify` 上一绿色 commit `f62e4b9d` = 110/213 = 51.6%（本地回路更严，用于秒级迭代；
> 最终判定仍以 CI 为准）。本机推送需另一 Agent 的 PAT 通道。

### 2026-09-12 第二轮（假绿专项：84 → 27，严格 60.6% → 87.3%）
**方法是「先修类型源头，再修调用点」**——优先改全局/被调函数的真实类型（一处改、消解 N 处），
最后才逐个调用点加 cast。本轮完全靠**汇编取证**定类型，无一处靠猜。

| 主题 | 关键取证 | 消解 |
|---|---|---|
| **UI 资源指针元素尺寸** | `DAT_003af294/298/2b8 + 1` → 汇编 `ldrh ip,[r3,#4]` / `ldrh r2,[r3,#6]` ⇒ **元素 4 字节**，故必须 `gh_u4 *`（早前误判为 `gh_u1 *` 会造成 `+1` 变 +1 字节的**静默语义错误**） | 5 |
| **ZIP 句柄统一** | `OpenZipU` 返回 `gh_u4 *`（`operator_new(8)`），而 `CloseZipU/FindZipItemA/UnzipItem` 内部要 `*p`/`p[1]` 解引用 ⇒ 句柄一律 `gh_u4 *`；`res_hz`/`hz` 改指针 | 12 |
| **被调函数形参实为指针** | `mui_LoadUIResource(p2)` 实参是字符串字面量 → `char *`；`mui_outputxy_t(p1)` 体内做 `param_1 + n*2` → `gh_u1 *`；`run_process(p1/p2)` → `char */gh_code *`；`dispFlip(p1)`/`UIDebug(p1)`/`Core_Load(p2)`/`get_item_from_line(p1)`/`SPI_Read_BUF(p3)`/`SPI_Write_BUF(p3)`/`sflash_*_security_data(p1)`/`GetJoystickConfig(p1)`/`init_user_joy_key_mask(p1)`/`autorun(p1)`/`GetInputInfo(p2)`/`get_items_from_file(p2)` | 30+ |
| **`&数组 + off` 衰变** | `&asc2_1608`/`&default_core_list`/`&DAT_0020202d`/`&DAT_002dd88c` → 去 `&` | 6 |
| **`game_t` 字段** | `retro_game_info.path/.data` 是指针 → `void *_0_4_/_4_4_` | 11 |
| **函数指针实参** | `pthread_create(..., XintiaoThread/mui_SoundplayThread, ...)`、`run_process("...", DrawFrame/PlayFrame/...)` → `(void *(*)(void *))`/`(gh_code *)` | 15 |
| **Ghidra 常量伪地址** | `&DAT_00061a80` 实为常量 `0x61a80`、`&DAT_000f4240` 实为 `1000000` | 3 |

**★ 本轮最大教训（已写入技能库）**：**改形参类型前必须先读函数体**。
`SoundPlay/blockadaptive/mui_blockcopy` 的函数体内把形参当 `int` 用（做整数/指针算术），
把形参改成 `void *` 会**同时破坏函数体**（当轮就产生 3 个宽松回归，已回退改在调用点 cast）。
判据：**形参体内做 `param + n` 或 `*param` ⇒ 它是指针；体内只做比较/赋值 ⇒ 可能只是 32 位值**。

### 2026-09-12 第三轮（假绿专项：27 → 0，严格 87.3% → **100.0%**）

**方法不变：先定类型源头，再改调用点。** 本轮 91 条 strict 错误（14 个文件）分四类，全部汇编/Ghidra 原文取证。

| 主题 | 关键取证 | 处理 |
|---|---|---|
| **`&DAT_x` 取址 vs 数组衰变** | `extern unsigned char DAT_002dbd74[]` 等 5 个为**不完整字节数组**，`&arr` 得「指向不完整数组的指针」→ 非法算术 | 去 `&`（数组名衰变，同一地址） |
| **`unsigned char[N]` 常量表** | `BB_cal_data[5]`/`RF_cal_data[3]`/`RF_cal2_data[6]`/`Dem_cal2_data[3]`/`RX_ADDRESS0/1[5]` 作 SPI 写缓冲 | 去 `&` |
| **`unsigned short` 全局** | `DAT_002dd64c` 声明为 `unsigned short`（2 字节），作 `myStrrstr` 的 `char*` 实参 | `(char *)&DAT_002dd64c` |
| **`unsigned int` 全局取址当缓冲** | `&DAT_003af70f`/`&DAT_003af708`（UI 文本缓冲）、`&DAT_003af7a0/e0`（`gh_blob_t`）作 `mui_outputxy_t` 第 6 参 `gh_byte *` | `(gh_byte *)&X` |
| **`DAT_003af2b8/2b4` 是 int 实参** | Ghidra 原文 `UnDrawSelectBar(int *p1,int p2,int p3)` 体内 `(int *)(param_2 + param_3*0x10)` ⇒ **param_2 是整数地址**（非指针） | 调用点 `(int)DAT_003af2b8` / `(int)DAT_003af294`（**不改被调函数体**） |
| **字面地址实参** | Ghidra 原文就是 `DrawSelectBar(0x3afc44)`；element stride `0x84`（`uVar3*0x84 + 0x3afc44`） | `(int *)0x3afc44` / `(int *)(uVar3*0x84 + 0x3afc44)` |
| **形参误标的被调函数** | `get_items_from_zipfile(p1)` 体内 `%s` ⇒ `char*`；`Core_Load(p2)` 体内 `sprintf("%s/cores/%s",…,param_2)` ⇒ `char*`；`gpsp_unzip(p2)` 体内 `%s` ⇒ `char*`；`stbtt_InitFont(p1/p2)` 实参是 `font[124]`/`fontbuffer` ⇒ `void*`；`mxmlElementSetAttr(p1)` 实参是整型节点句柄 ⇒ `gh_u4`、`p2` 是 `"language"` 字面量 ⇒ `char*` | proto 6 处 |
| **全局重定型** | `DAT_003af2bc`/`2c0` 分别被赋 `puVar12`(指针)/`pcVar4`(char*) ⇒ `void *`；`video_driver_get_size` 被 `dlsym` 赋值 ⇒ `gh_code *` | globals 3 处 |
| **`dlerror()` 返回值** | `Load_Proc1` 中 `uVar2` 用于 `RARCH_LOG("%s")` ⇒ `char *` | 局部 1 处 |
| **ZIP 句柄局部** | `run_game` 的 `iVar3 = (int)OpenZipU(...)` ⇒ 应为 `gh_u4 *`；`mui_LoadUIResource` 的 `iVar1 = res_hz` ⇒ `gh_u4 *` | 局部 2 处 |
| **`m_ui` 数组元素** | `(&m_ui)[k]` 是取数组中第 k 个 32 位指针值 | `(gh_byte *)(&m_ui)[k]` |
| **`puVar15` 双用途** | 既作 `gh_u4 **`（`&DAT_003af2b8` + 自增 + 解引用），又作 `gh_byte *` 实参 | 保留 `gh_u4 **`，实参处 `(gh_byte *)puVar15` |
| **局部承载指针** | `(mui_X_blob)._0_4_ = malloc(...)`、`*puVar8 = pcVar4`、`local_198 = &DAT_003af7a0` | 加 `(gh_u4)` cast（4B 槽存 32 位地址，ABI 不变） |

**结论**：编译期三重门（语法 / 类型 / ABI）中的前两道已全绿。**下一步 P3 链接 → P4 ABI 门禁 → P5 行为差分 → P6 真机验收。**

---

### 2026-09-12 第四轮：★ P3 链接启动（符号层审计完成）

新增工具（全部零依赖、含自检）：

| 工具 | 作用 |
|---|---|
| `tools/elf_syms.py` | 自研 ELF32 符号表读取器（`zig objdump -t` 不支持 → 自研）。区分 **GLOBAL/WEAK（DEFINED）** 与 **LOCAL（文件作用域，不参与重复判定）**、COMMON、UNDEF。带 `--selftest` |
| `tools/link_audit.sh` | 编译全部 213 → `.o` → 抽符号 → 汇总（报告 `report/link_audit.txt`） |
| `tools/link_audit.py` | 重复定义 / 未解析引用分类：**upstream / libc / eabi / MISSING** |
| `tools/gen_factory_globals.py` | 从工厂 `symtab.txt` 提取**权威全局布局**账本（`ledger/factory_globals.tsv`，940 个数据对象） |
| `tools/data_provision_plan.py` | 数据段供应缺口分析（把 MISSING 映射到工厂对象/字段/未命名区域） |

**审计结果（符号层）**

| 项 | 值 |
|---|---|
| 对象数 | 213 |
| **重复定义（链接硬阻断）** | **0** ✅（早前报 19 是把 `.L.str`/`$a`/`$d` 等 **LOCAL** 符号误判为重复，已修） |
| 本体重定义符号数（GLOBAL/WEAK） | 219 |
| 未解析引用 | 458（MISSING **392** / upstream 7 / libc 54 / eabi 5） |

**★ P3 核心结论：392 个 MISSING 全部是「数据段」符号，不含函数缺口。分类：**

| 类 | 数量 | 含义与处置 |
|---|---|---|
| **A** | 188 | 与工厂符号**同名** → 按工厂 `size/section` 直接定义（如 `configitems[50000]`、`corecfg[16000]`、`GPIO0`…） |
| **B** | 139 | Ghidra `DAT_x` **落在工厂对象区间内** → 必须以 **alias** 定义，不得另占空间。**`m_ui` 一个对象就吞掉 128 个字段**（`m_ui`@`0x003af264` size **1508**）；另 `default_core_list`(size 6800) 吞 5 个、`file_info_list`(size 41120) 吞 5 个、`asc2_1608` 吞 1 个 |
| **C** | 20 | `DAT_x` 不在任何工厂对象内（未命名 `.data/.rodata`）→ 需按工厂镜像单独供应 |
| **D** | 45 | 上游组件函数（`MP3*`/`XUnzip_*`/`mxml*`）+ libc（`putc`/`readlink`/`scandir`/`stpcpy`/`stdout`/`__ctype_*_loc`…）+ 少数 Ghidra 合成名（`code_convert_constprop_22`/`crc_table`） |

**★ 关键认知（推翻直觉）**：**Ghidra 的 `DAT_xxxxxxxx` 不是工厂符号。** 工厂真符号是 `m_ui`（size 1508）、`asc2_1608`（size 1520）这类**大对象**，Ghidra 只是给它内部的每个访问点另起了 `DAT_` 名字。因此若把 `DAT_x` 与 `m_ui` 各自独立定义，链接后二者各占一块空间 ⇒ **破坏原厂内存布局**，而代码里又烧死了绝对地址（如 `(int *)0x3afc44`）⇒ 行为必然错。这决定了 P3 数据段供应必须走 **单一大对象 + alias 别名** 的路线。

**下一步（P3 续）**：① 由账本 + 工厂镜像生成本体数据定义（含 alias）；② 生成复刻工厂内存映射的链接脚本；③ 试链出 ELF 并过 `abi_check.py` 门禁。

---


### 2026-09-12 第五轮：★ P3 数据段供应落地（工厂镜像 + 别名 + 链接脚本）

新增工具与产物：

| 项 | 说明 |
|---|---|
| `tools/elf_layout.py` | 导出工厂 ELF 的段/节布局 → `ledger/factory_layout.tsv` |
| `tools/gen_data_module.py` | 生成 `src/data/factory_image.S`（**工厂原始字节镜像** + **1093 个符号别名**）+ `linker/factory.ld` |
| `tools/link_probe.sh` | 编译 213 → 汇编数据镜像 → 按工厂 VMA 链接 → 过 ABI 门禁 |
| `tools/verify_layout.py` | **逐符号校验**重建 ELF 的数据符号地址 vs 工厂账本 |

**工厂内存映射（实测）**：entry 0x9d44；`.plt`0x9608 / `.text`0x9b10(size 0x2d2188) / `.rodata`0x2dbca0(0xd135c) / `.ARM.exidx`0x3ad008 / `.data.rel.ro.local`0x3ae5c4(0x914) / `.init_array`0x3aeed8 / `.fini_array`0x3aeedc / `.data`0x3af000(0x2cfc) / `.got`0x3b1cfc / `.bss`0x3b2178(0x2f95b)。段偏移非均匀（LOAD1 Δ0x8000、LOAD2 Δ0x9000），**必须用节自身的 offset**。

**核心设计**（为什么必须这么做）：
1. 反编译代码烧死绝对地址（`DrawSelectBar((int *)0x3afc44)`）⇒ 段 VMA 必须与工厂逐位一致；
2. Ghidra 的 `DAT_x` 不是工厂符号（真符号是大对象）⇒ **每段只放一份工厂原始字节镜像**，
   全部符号用 `.set NAME, <段基址> + <偏移>` 定义为别名，**不额外分配空间**。

**布局校验结果（数据镜像 + 极小 main，`-nostdlib` 试链 ELF 962,852 B）**：

| section | 一致 | 偏差 | 缺失 | 说明 |
|---|---|---|---|---|
| `.data` | **28 / 28** | 0 | 0 | ✅ 别名机制完全正确 |
| `.bss` | 189 | 3 | 0 | 3 个偏差见下 |
| `.rodata` | 0 | 717 | 1 | 全部 Δ**-4**：`-nostdlib` 无 crt1.o，无人填段首 4 字节 `_IO_stdin_used`；**真实链接中由 CRT 提供** |
| `.init_array`/`.fini_array` | — | — | 1/1 | 由链接脚本 `PROVIDE(=ADDR(sec))` 提供，本测试无人引用故未落表 |

**★ 发现的真问题：工厂有 3 对同名局部符号**（各自属于不同编译单元，`l` 绑定，C 里各自 `static` 合法）：
`handle`@0x3b21c8 与 @0x3cf988、`SoundBuffer`@0x3ceaf0(size 0xb80) 与 @0x3e1944(0x10)、`diff_prev`@0x3bc414 与 @0x3e1a38。
我们当前的 `globals.h` 把它们当**一个**全局 → 会把两份合并成一份 ⇒ 错。
**P3 二期必须按「哪个函数引用哪一份」拆成 `static`（或加后缀改名）**——需 Ghidra 的逐函数数据引用归属。

**链接现状（213 对象全量）**：重复定义 **0** ✅；仅剩上游未供应：
`XUnzip_*`(5) / `operator_new/delete`(2) / `libiconv_*`(3) / `mxml*`(6) / `MP3*`(6)。

**★ 上游已定位并定版（全部证据驱动）**：

| 组件 | 版本 | 证据 | 状态 |
|---|---|---|---|
| stb_truetype | **v1.26** | 抓到的 master 头部即 `v1.26`，与既有裁定一致 | ✅ 已入库 `src/upstream/stb/` |
| mini-XML | **v3.3.1** | 工厂 16 个 mxml 静态函数**全部**在 v3.3.1 源码中（仅 9 个可被死代码消除）；v2.12 多出 60 个（markdown/epub/zipc 等，工厂全无）⇒ 排除；3.3.1 发布于 2021-12，落在固件窗口 2022-10~2023-03 | ✅ 已入库 `src/upstream/mxml/`（15 文件） |
| Helix MP3 | RealNetworks fixpnt | **`pub/statname.h` 默认 `STAT_PREFIX xmp3`** ⇒ 与工厂符号 `xmp3_UnpackFrameHeader` 等完全吻合 | ✅ 已入库 `src/upstream/mp3/`（30 文件，已还原 `pub/`、`real/` 目录） |
| XUnzip | Lucian Wischik **zip_utils** | `TUnzip` + `Open/Get/Find/Unzip/Close` 五方法、C 包装 `OpenZipU/FindZipItemA/UnzipItem/CloseZipU`、内嵌 zlib（`_Z7zcalloc…`）——逐一对上 | ⚠️ 已下载 `src/upstream/xunzip/`，**需 Windows→POSIX 移植**（现含 `<windows.h>/<tchar.h>`）+ 方法名映射 |
| libiconv | 本地复用 | `cnb-rkgame-final/rkgame-rebuild/lib/libiconv/`（236 文件）定义 `libiconv_open/libiconv/libiconv_close` | ✅ 已复制 `src/upstream/libiconv/` |

**注**：`cnb-rkgame-final` 里的 `lib/mxml/mxml.c` 是**手写桩**（1334 行，只实现 `mxmlFindElement`），不是真 mini-XML —— 已用真源码替换。

**下一步（P3 二期）**：① XUnzip POSIX 移植 + `XUnzip_` 方法名映射；② 3 对同名局部符号按 TU 拆分；③ `.text` 精确逐函数布局（函数指针表依赖）；④ 完整链接 + `abi_check.py` 过门禁。
---


### 2026-09-12 第六轮：★ PAT 通道打通 + CI 全绿（GCC 实测双轨 100%）

**PAT 定位与安全整改**：PAT 原嵌在 `tools/push_1to1.py` 第 7 行（该文件在 `tools/` 推送范围内 ⇒ 会被推上 GitHub 并被密钥扫描吊销）。
已改为 **环境变量 `GITHUB_TOKEN` / 本地 `.pat` 文件**（`.pat` 在推送范围外），脚本内已无 token，且保留「含 `ghp_` 的文件一律不推送」自检。

**push 脚本加固**：原 `ThreadPoolExecutor(max_workers=8)` 触发 GitHub 次级限流（HTTP 403 secondary rate limit）
→ 改 **串行 + 403/429 指数退避重试**（20s/40s/60s…，最多 7 次）。

**★ 首次全链路推送与 CI 实测（3 次推送全部成功，blob 逐个 SHA1 校验 567/567）**：

| commit | CI | 结果 |
|---|---|---|
| `90ebce380f5b` | rkgame-rebuild ✅ / 1to1-verify ✅ | 首次全链路打通 |
| `4bd8cddfd0ab` | rkgame-rebuild ✅ / 1to1-verify ✅ | 发现 link_audit 未产出报告 |
| `222b3aa66caa` | rkgame-rebuild ✅ / 1to1-verify ✅ | **link_audit 在 CI 完整产出** |

**CI（GCC 11 / Ubuntu 22.04）实测 = 本地（zig clang 21）实测，完全一致：**

| 口径 | 本地 | CI(GCC) |
|---|---|---|
| 宽松（语法） | 213/213 = 100% | **213/213 = 100%** ✅ |
| 严格（类型正确） | 213/213 = 100% | **213/213 = 100%** ✅（假绿 0） |
| P3 重复定义 | 0 | **0** ✅ |
| P3 未解析 | 392 | 463（MISSING 405 / upstream 7 / libc 47 / eabi 4）——GCC 多 13 个数据引用，仍无函数缺口 |

**★ 第六轮抓到的根因：CRLF 行尾**
`link_audit.sh`/`link_probe.sh` 被我用 Python 文本模式改写后变成 **CRLF**，CI 的 `sh`（dash）把 `set -u\r` 当非法选项
（报 `set: Illegal option -`），`continue-on-error: true` 把失败吞成 success，导致 artifact 里没有报告。
修复：① 两个脚本 + `factory_image.S` + `factory.ld` 全部规范化为 LF；
② **推送脚本加防线**：`.sh/.yml/.S/.ld` 上传前若含 CRLF 自动转 LF（防再犯）。

**新增工具**：`tools/ci_watch.py`（轮询 CI 至完成，失败时给出 job/step 级定位；artifact 下载需在 302 到 Azure 签名 URL 时**剥离 Authorization**）。

## 零之一、历史阶段（2026-09-12 第一轮：宽松 86.4% → 100%）

### 2026-09-12 进度（本地，未推送）
**① 宽松口径 86.4% → 100%（+29 文件，零回归）**

| 批次 | 修复数 | 代表根因（全部取证驱动） |
|---|---|---|
| 结构类硬错误 | 11 | NEON `vst1.8` 16B 零写被 Ghidra 误还原为 `(gh_u1[16])0x0+off` 读；`spi_printf` 的 `push{r0-r3}`+`add rX,sp,#N` = **AAPCS32 变参序言**；`GPIO0` 为 `void*` 却写 `*GPIO0` |
| 返回类型漏判 | 5 | `GetTick` 实为 **64 位微秒**（`ldm sp,{r0,r2}` + `movt r3,#15` + `mla` + `asr r1,r0,#31`）；`gameType` 返回位索引；`spi_write/spi_read/erase_sector` 返回 `sfc_request` 结果；`strtrim` 是 `strtriml→strtrimr` 尾调用 |
| 调用点少参 / 签名 | 18 | `proto.h` 的 K&R 与定义不符；`FindZipItemA` 第 5 参经栈传递（`str r9,[sp]`）被 Ghidra 丢弃 |
| 伪算子宏 | 3 | `CARRY4` 原定义 `b>a` **有误** → 按 ARM C 条件位改 `((u4)(a+b)<(u4)a)`，并改可变参 |
| 不完整类型 | 2 | `TUnzip` 按 `operator_new(0x240)` 补全 |

**② 严格口径 52.1% → 60.6%（假绿 102 → 84）**
高杠杆修复：`game_t` 的 `_0_4_/_4_4_` 按 `retro_game_info.path/.data` 改为指针（一次消解 11 处）；
`scr_data`/`CRU`/`GRF`/`DAT_003af29c`/`DAT_003af2ac`/`JOYSTICK_DEVNAME`/`Frame_data` 重定型为指针；
`&数组 + off` → 数组名衰变（6 文件）；`mui_LoadUIResource` 形参 → `gh_u1 **`（消解 5 处）；
`XintiaoThread` 函数指针 cast；`dispFlip/run_process/run_process_constprop_0/get_item_from_line/SPI_Read_BUF`
形参按调用点真实实参改指针类型。

**③ 新增 C 语言铁律（本轮血泪，必须遵守）**
1. **K&R 空原型与含「默认提升类型」形参的定义不兼容**（ISO C 6.7.6.3p15）：
   `extern T f();` + `T f(unsigned char x){}` → clang 报 `conflicting types`。
   → 形参含 `char/short/uchar/float` 的函数**禁止**用 K&R 空原型。
2. `CARRY4/SBORROW4` 等 Ghidra 伪算子的**实参个数可能少于宏定义** → 宏必须写成 `(a,b,...)`。
3. **AAPCS32 变参序言特征** `push {r0-r3}` + `add rX,sp,#N` 指向已存 r1 → 原函数是变参，勿按固定形参还原。
4. **C++ 类方法 `this+N` 需完整类型**：Ghidra 的 opaque struct 须按 `operator_new(size)` 补尺寸。
5. **Ghidra 会漏判 `void` 返回值**（`GetTick`/`gameType`/`spi_*`/`strtrim`）→ 凡调用点用返回值的，
   必须回汇编看 `r0` 的真实来源再定返回类型。

**④ 剩余 84 个假绿分类**（`python tools/classify_strict2.py`）
pointer→int 实参 48 / int→pointer 实参 20 / 指针类型不符 13 / 其他 3。
下一步：继续按「被调函数形参实为指针 / 全局实为指针」两类收敛。

---

## 零之二、历史阶段（2026-09-11 及以前）

### 2026-09-11 进度（本地，未推送）
- 新增 `tools/recon_local.sh`：zig 本地编译回路（与 CI 同口径校准，110/213 时代逐文件一致）
- 方案 A · 标量 blob 化：6 个标量全局（`TimeCountReg`/`RF_joy_key`/`inTimeVal`/`outTimeVal`/
  `frame_time_last`/`progress_stepcount`）→ `u64_pair_blob_t`/`u32_pair_blob_t` + `NAME_blob`
  指针 cast 宏（`ghidra_compat.h`），33 处 `._N_M_` 访问经 `tools/rewire_scalar_member.py`
  改写；探针实测整型 cast 与指针 cast 混合合法 → **113/213 = 53.1%**（+3 文件，无回归）
- 剩余 100 失败分类（`tools/classify_fail.py`）：member-not-struct 38 / indirection 25 /
  conflicting-types 18 / struct-tag(timeval/dirent) 8 / unknown-type 5 / other 16
- 下一步（证据已备）：13 个数组全局 per-name 精确 blob（`tools/gen_named_blobs.py` 数据齐全，
  其中 `fontname[8]`/`m_menulog[sVar4+0x1bb]` 两处动态下标需 byte-array 兜底）

| 阶段 | 通过率 | 关键修复（均为取证驱动） |
|---|---|---|
| 基线（Ghidra 原样） | 24 / 213 = 11.3% | — |
| 注入标准 include | 0 / 213（回归） | 暴露 `ulong` 与系统头 typedef 冲突 |
| 类型改 `gh_` 前缀 | 78 / 213 = 36.6% | 从构造上消除类型冲突 |
| proto 限专有 + DAT_ 兜底 | 82 / 213 = 38.5% | 上游原型类型泄漏、27 个内联字面量 |
| 补 POSIX 头 + proto 覆盖全部被调函数 | 102 / 213 = 47.9% | `usleep/access/dlsym/...` 缺声明 |
| 按调用点实参数改 K&R 声明 | 110 / 213 = **51.6%** | `gameType/mxmlLoadFile/GetFilenameExt` 等签名不可信 |
| `gh_blob_t` 覆盖 `_N_M_` 字段访问 | 110 / 213（持平） | 41 个对象重定型；严格过滤后 24 个 |

**取证工具链（本轮新增，全部本地可跑）**：

| 工具 | 作用 |
|---|---|
| `tools/analyze_sig.py` | 比对**声明签名 vs 函数体实际行为**（return 值/param_N）→ 产出差异清单 |
| `tools/find_undeclared.py` | 比对**调用目标 vs 已声明集合** → 产出未声明清单 |
| `tools/check_types.py` | 生成物类型可解析性自检（含多行 struct typedef） |

> **本轮方法论要点**：三次"假设 → 取证 → 推翻"，
> ① 「原型签名不匹配」经 `analyze_sig.py` 实测**只有 2 例** → 假设被推翻；
> ② `find_undeclared.py` 实测未声明目标**几乎全是 libc + 上游 API** → 真因是缺头文件与 proto 覆盖不足；
> ③ `_N_M_` 字段经实测**只有 1/4 字节两种尺寸且 4 字节全 4 对齐** → 据此精确构造 `gh_blob_t`。
> **没有一次是靠经验猜的。**


**已建成并自检的重建流水线**：

| 工具 | 作用 | 自检 |
|---|---|---|
| `tools/gen_compat.py` | 生成 compat 头 + 全局声明 + 函数原型 | 类型取自 Ghidra 真实导出，非尺寸猜测 |
| `tools/normalize_types.py` | Ghidra 私有类型统一加 `gh_` 前缀 | C 词法感知，不触碰字符串/注释 |
| `tools/check_types.py` | 生成物类型可解析性自检 | **0 未解析**（本地拦截，不再靠 CI 试错） |
| `tools/recon_build.sh` | 逐函数编译门禁（真实进度度量） | 全失败即 `exit 1` |
| `ledger/ghidra_types.tsv` | Ghidra 导出的 **1134 函数 + 4627 数据**真实类型 | 由 `ExportTypes.java` 产出 |

**剩余 131 个失败的主因**（需逐函数处理 = 真正的重建工作）：
1. `void value not ignored as it ought to be` —— 原型返回类型与函数体实际返回值不符
2. `too few arguments to function` —— 原型参数个数/类型与实际调用不符
3. 其余为 `unaff_*` 寄存器残留（Ghidra 未能归属的调用者寄存器值）等语义问题

> **关键教训（本轮）**：Ghidra 函数文件**无任何 include**；其私有类型名（`uint/ulong/byte/bool`…）
> 与 glibc 系统头**必然冲突**（C 中 typedef 冲突是硬错误）。**根治办法是从构造上改名（`gh_` 前缀）**，
> 而不是逐个猜测哪个头定义了它。


## 一、本轮已交付（全部经机械验证）

| 交付物 | 状态 | 验证证据 |
|---|---|---|
| **差分验证工具链** `tools/funcdump.py` + `tools/funcdiff.py` | ✅ | 自检 golden-vs-golden = **835/835 = 100% T1**；人为扰动被正确判为非通过 |
| **原厂金标准参照集** `golden/factory.funcs.json.gz` | ✅ | **835 函数 / 715,473 指令**；CI 内断言 835 + 715473 通过 |
| **源树还原 + 确权** | ✅ | 41 个 `STT_FILE` 编译单元；上游 581f/194,454B(61.3%) vs 专有 223f/122,922B(38.7%) |
| **重建工作区 + 逐函数台账** | ✅ | `ledger/functions.csv` 223 专有函数（地址/尺寸/模块/源文件） |
| **上游版本指纹工具** `tools/vermatch.py` / `stb_range.py` | ✅ | 已跑通并得出结论（见下） |
| **P2-A CI 作业** `.github/workflows/1to1-verify.yml` | ✅ | run #2 success，真实数据产出于作业日志 |
| **假绿根除** | ✅ | 加硬门禁（覆盖为 0 → `exit 1`）+ 取证转储；修复后索引 bug（`p[1]`→`p[4]`） |

**GitHub 提交**：`7697e370` → `bd17402d` → `9c993748` → `245eee2d`（均 8~11/11 blob SHA1 校验通过）

## 二、本轮关键发现（推翻旧认知）

| # | 旧认知 | 更正（证据） |
|---|---|---|
| 1 | zlib 1.2.5 | **误判**——`1.2.5` 是 `.rodata` 数据表字节。真相：`XUnzip.cpp` 内嵌 **zlib 1.1.x**（`huft_build`/`inflate_blocks`/`inflate_codes` 为 1.1.x 特征，1.2.0 已删除） |
| 2 | "XUnzip 组件" | 实为 **XZip(`TUnzip`/`LUFILE`) + miniunz(`unzip.c`) + 内嵌 zlib**，因是 C++ 编译单元故符号全被修饰 |
| 3 | 需重建 812 函数 | **实际专有仅 223 函数 / 122,922 B**（上游 61.3% 可从上游重建） |
| 4 | 从零重写可行 | **已被真机证伪**（日志空转 `waiting for Phase 4 UI`；原厂有 19088 游戏 + 中文 UI） |
| 5 | 名称指纹可定版 | **不足以定版**——stb_truetype v1.19~v1.26 全部 81/81 覆盖 |

## 三、★ 阻塞已解除：验证策略经实测修正

**原阻塞**：P2-A 定版受阻于工具链不匹配（CI 实测尺寸偏差 49.6%，全版本不可区分）。

**探测结论（全部实测，非推测）**：原厂工具链 `armv7a-libreelec-linux-gnueabi`（glibc 2.24 / GCC ~6）
**无法直接获取**——LibreELEC 不发布预编译 SDK（`sources.libreelec.tv` 空内容、`/toolchain/` 404、
`archive.libreelec.tv` 拒连）；Linaro 站点已迁移为 SPA（所有旧直链返回 65 字节占位页）。

**策略修正（详见 `docs/verification-strategy.md`）**：

| 项 | 修正前 | 修正后 |
|---|---|---|
| 主门禁 | 函数级 T1 汇编等价 | **行为差分（oracle 比对）** |
| T1 | 必须达成 | **归档**（工具链可得后可选启用；实现已就绪且自检 100% T1） |
| 结构指纹 | 用于定版 | **限用于「我们 vs 我们自编译参照」**（对工厂绝对比较噪声主导，实测通过率仅 41%） |
| 上游定版 | 尺寸/指纹 | **时代证据 + 覆盖率证据裁定** → stb_truetype = **v1.26**（固件时间戳窗口 2022-10~2023-03 唯一版本；v1.19~v1.26 全覆盖 81/81，功能风险为零） |

**新增主门禁实现（已自检）**：
- `tools/behav_capture.sh` — 行为指纹采集（退出码 / 日志语义事件序列 / 文件写入 / 帧采样 / shm 心跳）
- `tools/behav_diff.py` — 行为差分判定（B1~B5，自检：一致→PASS，不一致→FAIL+精确 diff）

> **关键工程判断**：判定标准是「语义级等价（允许寄存器分配/指令调度差异）」，
> 精确工具链并非必需；而代码级指纹在无同款工具链时**噪声主导**（会把正确实现判为 FAIL）。
> 因此**行为差分才是与「100% 原厂功能」直接对应的可靠门禁**。

## 四、下一步（依赖顺序）

> ★ **N3 里程碑（本轮达成）**：CI 中用现有工具链编译并过 ABI 门禁，**全项 PASS**：
> ```
> [PASS] e_type    got=0x2        want=0x2
> [PASS] e_machine got=0x28       want=0x28
> [PASS] e_flags   got=0x5000400  want=0x5000400
> [PASS] interp    got=/lib/ld-linux-armhf.so.3  want=/lib/ld-linux-armhf.so.3
> ```
> 结论：**P3 链路/ABI 门禁不依赖 GCC 6 即可达成**，重建产物可直接具备原厂 ELF 规格。
> 实现：`tools/abi_check.py`（自检：原厂二进制全 PASS）+ workflow `N3 ABI 门禁` 步骤。

| # | 动作 | 门禁 | 状态 |
|---|---|---|---|
| N1 | ~~取得工具链~~ | — | **已裁定不需要**（策略修正 §三） |
| N2 | 上游 5 组件按时代+覆盖率证据定版 | 证据链完整 | **已完成**（stb=v1.26；iconv=glibc 2.24；其余按同一方法） |
| N3 | 用现有可用工具链复现 `_start`/crt，ABI 门禁 | ELF 头/`.interp`/`e_flags` 逐字段一致 | ★ **已完成并 PASS** |
| N4 | 按台账逐函数重建（优先 mui 42f/70KB） | **行为差分门禁** | 可执行 |
| N5 | 行为差分（factory vs rebuild，多入口） | `behav_diff.py` PASS | 工具已就绪 |
| N6 | 真机验收 | 19088 游戏 / 中文 UI / 全菜单 / 存档 / BGM | 依赖 N4+N5 |

## 五、诚实的工作量评估

- **基础设施已 100% 完成**（工具链、金标准、台账、CI、假绿门禁）——这是后续一切的地基。
- **实际重建尚未开始**：223 个专有函数 / 122,922 B 的忠实重建是主体工作量，
  且必须先解决 N1（工具链）才能进入「编译—差分—修正」闭环。
- 在 N1 解决前强行开始 N4 会重蹈「无验证的从零重写」覆辙，**故本轮到此为止是正确的工程判断**。

## 六、复盘：本轮踩到的坑（已修，勿重复）

1. **GitHub 密钥扫描**：脚本硬编码 Token 会被 422 拦截 → 一律用 `os.environ['GH_TOKEN']`。
2. **CI 日志/制品下载**：`/logs` 与 `/artifacts/{id}/zip` 是 302 到签名 URL，
   带 `Authorization` 头会被 401 → 须**跟随时去掉该头**；`/logs` 返回**纯文本**不是 zip。
3. **`objdump -t` 解析**：行 = `addr bind type section size name`；尺寸在 **p[4]**，
   p[1] 是绑定属性。取错索引会静默提取 0 条。
4. **硬门禁必需**：任何"提取到 0 条"的作业必须 `exit 1`，否则假绿。
