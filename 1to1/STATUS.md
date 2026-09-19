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

### 2026-09-12 第七轮：★ P3 二期① XUnzip POSIX 移植（18/18 符号逐位命中）

**工厂 XUnzip.cpp 变体画像（符号表取证，非猜测）**：

| 事实 | 证据 |
|---|---|
| 编译单元名 `XUnzip.cpp`（工厂改名） | symtab `df *ABS* XUnzip.cpp` |
| 只编 unzip.cpp，**未编 zip.cpp** | 无 `CreateZip/ZipAdd/deflate*` 符号 |
| 保留 TUnzip 五方法 + FormatZipMessageU + GetZipItemW + FindZipItemW + IsZipHandleU + lu*/unz* + 内嵌 zlib 1.1.x | symtab 逐条比对 |
| 纯 C++ 包装全删（OpenZip*/CloseZip/GetZipItem/FindZipItem/UnzipItem/OpenZipU 重载/CloseZipU） | 工厂改用自研 C 包装（即我们专有集里的 5 个 zip 文件） |
| **密码支持全删**（无 Uupdate_keys/Udecrypt_byte/zdecode/EnsureDirectory；`unzOpenCurrentFile` 无 password 参） | symtab 缺失 + mangled 签名差异 |
| `Find` 的 `ic` 为 **unsigned char**（mangled `h`，非 bool `b`）；DWORD = **unsigned int**（`j`） | `_ZN6TUnzip4FindEPKchPiP8ZIPENTRY` |
| `ucrc32` 是 **C 链接**（`g F .text @0xfff4`） | 我方专有集里的 `FUN_0000fff4_ucrc32.c` 即为它 ✓ 口径不变 |
| `crc_table` = `_ZL9crc_table`@0x2e01c4（C++ internal linkage，**grep `crc_table$` 匹配不到**） | Ghidra globals + 工厂 symtab |
| `lasterrorU` = `ZRESULT lasterrorU=ZR_OK`（.bss 4B @0x3b221c） | 改为 extern，定义交工厂数据镜像 |

**移植实现**：`src/upstream/xunzip/posix/{windows.h,tchar.h}` shim（CreateFile→open、SetFilePointer→lseek、GetFileType→FILE_TYPE_DISK、DosDateTimeToFileTime→自算 FILETIME、SetFileTime→futimens、DuplicateHandle→dup、`DECLARE_HANDLE` 宏还原 `struct HZIP__` 指纹）；unzip.cpp 工厂变体补丁（ic→uchar、lasterrorU extern、`#ifdef XUNZIP_KEEP_PLAIN_WRAPPERS` 剔除工厂不存在的包装、补 ZIPENTRYW + GetZipItemW/FindZipItemW）；反编译 C 改回**工厂真名**（`XUnzip_*`→`_ZN6TUnzip*`，`operator_new/delete`→`_Znwj/_ZdlPv`）。

**结果**：`zig c++ -std=gnu++98` 编译出 XUnzip.o（168 KB），**18/18 关键 mangled 符号与工厂逐位一致**；双轨 213/213 保持 100%（零回归）。

---

### 2026-09-13 第八轮：★ P3 二期② 上游四组件编译接入（重复定义 0 / upstream 0）

| 组件 | 定版 | 编译结果 |
|---|---|---|
| stb_truetype | v1.26 | `stb_truetype.o`（impl 单元 + 版本宏证据） |
| mini-XML | v3.3.1 | 10 个 `mxml-*.o`（工厂 16 静态函数全集比对定版） |
| Helix MP3 | RealNetworks fixpnt | 12 个 `mp3_*.o`（`STAT_PREFIX=xmp3`） |
| GNU libiconv | **1.17（真源码，替换手写桩）** | `libiconv_iconv.o` + `libcharset.o` |
| libcharset | 1.17 | `locale_charset` |

**★ 关键认知：`src/upstream/libiconv/` 里那批文件是手写桩**（自称"简化版"，`iconv.c` 613 行）——1:1 不能用；已改抓 GNU libiconv 1.17 tarball，提取真 `lib/`（295 文件）+ 生成最小 `config.h`（含 `ICONV_CONST`）+ 替换 `iconv.h.in` 占位符。

**★ 上游与工厂镜像的符号冲突及解法（三类）**：

| 冲突 | 实例 | 解法 |
|---|---|---|
| 上游数据定义 vs 工厂镜像别名 | mp3 表 `xmp3_huffTable`/`xmp3_imfctWin`… 工厂为 **g O .rodata** 且已别名 | **跳过 3 个纯数据文件**（mp3tabs/trigtabs/hufftabs，零函数），表由镜像供应 |
| 上游全局状态 | `mp3DecInfo/mi/hi/di/sbi/sfi/si/fh`（工厂 g O .bss） | buffers.c 内 **extern 化**（8 个） |
| 上游版本标记 / 重名函数 | `_libiconv_version`（工厂 g O .data @0x3b1cf8）、`MP3GetNextFrameInfo`（工厂属专有区 @0x2b87f4） | iconv.c extern 化；mp3dec.c 侧 `-D` 改名 |

**★ 本轮抓到的两个隐蔽陷阱**：
1. **`.incbin` 双重 skip**：`factory_rodata.bin` 本身已跳过头部 4 字节，而 `.S` 又写了 `skip=4` → **GNU as 报错、clang 静默截断尾部 4 字节**（本地潜伏 bug，CI 才暴露）。已修：SKIP_HEAD 时输出纯 `.incbin`。
2. **别名生成器重叠**：账本 `factory_globals.tsv` 同时含 g 与 l 对象（`m_ui`/`GPIO0` 实为 **l**）→ 两个生成器重复定义同一符号（曾致 1097 假重复）。已修：`gen_local_alias.py` 自动跳过 `factory_image.S` 已覆盖的名字（现仅 5 个别名 + `crc_table`）。
   另：**`gen_data_module --missing` 必须传「全量 UNDEF」而非「分类后 MISSING」**（曾用 17 条重生成 → 934 别名退化），已固化为 `tools/regen_data.sh`。

**审计结果**：**重复定义 0 ✅ / upstream 0 ✅**；MISSING 仅剩 3 个 `.text` 区间常量（`UNK_000d2f00`/`UNK_00118000`/`UNK_002e0938`）——它们位于 `.text` 段内的只读常量表，等 **P3 三期 `.text` 精确镜像**一并解决；libc 100 / libstdc++ 4 / eabi 6 均为运行时提供。

**下一步（P3 三期）**：① `.text` 精确逐函数布局（复刻工厂函数地址，函数指针表/绝对地址依赖）；② 完整链接 → `abi_check.py` 门禁 → P5 行为差分 → P6 真机验收。

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


### 2026-09-13 第九轮：★★ P3 完整链接打通（ABI PASS + 全局布局 98.5%）

**上游四组件全部编译接入**（详见上节）+ 冲突三类解法落地 ⇒ 审计：**重复定义 0 / upstream 0 / MISSING 3**。

**完整链接**（`tools/link_full.sh`，241 对象 + 工厂镜像）：

| 指标 | 结果 |
|---|---|
| 产物 | `build/rkgame.rebuilt.elf`（17,010,068 B） |
| **ABI 门禁** | **PASS**：e_type=EXEC / e_machine=ARM / e_flags=0x5000400 / interp=`/lib/ld-linux-armhf.so.3` |
| **布局门禁** | **PASS**：全局符号 **191/194 = 98.5%**；局部 105/746（信息项） |
| 可接受偏差（3） | `_IO_stdin_used`（CRT 内部，镜像跳过 4B）；`SoundBuffer`/`diff_prev`（**工厂同名双定义**，待按 TU 拆分） |

**链接脚本重构**：工厂地址区（`.fimg_rodata`@0x2dbca4 / `.fimg_data_rel_ro_local`@0x3ae5c4 / `.fimg_data`@0x3af000 / `.fimg_bss`@0x3b2178）与运行时区（`.text`@0x9b10 / `.rodata`@0x400000 / `.data`@0x1000000 / `.bss`@0x2000000）分离 —— 使 libc 的段不挤进工厂地址区。
★ 关键：**带 SKIP_HEAD 的镜像段 VMA 必须 +skip**，否则全部 .rodata 符号系统性 Δ-4。
★ 链接期占位 `compress/uncompress/_init/UNK_* = 0` 写在链接脚本内（工厂从 libz.so.1 动态导入 / 等 .text 镜像）——**显式置 0，不造假实现**。

**CI 实测复现**（commit `f6a0451f786f`，GCC 11）：`1to1-verify` success，P3 三步真正跑通 ——
产物含 `verify_layout.txt`、`link_full_err.txt`（空）；**布局门禁 PASS：全局 191/194 = 98.5%**（与本地 zig 一致）；
P3 审计 **重复定义 0 / MISSING 3**；双轨 213/213（GCC）。
★ 两个 CI 专属坑：① `push_1to1.py` walk 范围必须含 **`linker/`**（否则 `cannot open linker script file`，被 `continue-on-error` 掩盖）；② GCC 默认 `-D_FORTIFY_SOURCE` 引入 20 个 `__*_chk` 符号 → 已归入 libc 分类。

**下一步**：① 同名双定义按 TU 拆分（`handle`/`SoundBuffer`/`diff_prev`）；② `.text` 常量镜像（3 个 `UNK_*`）；③ P4 → P5 行为差分 → P6 真机验收。

---

### 2026-09-16 第二十六轮：★★★★ 第四个真实分歧 —— 设备读被 LLVM 提升并向量化（`vdup.32` 陷阱）

**来源**：第二十四轮（`spi_id[0]` 修复）后的 CI。修复**确认生效**：重建侧发出的 flash 命令从
`addr=002000 / addr=001000`（错）变成 `addr=000100 / addr=000000`，与工厂**逐条一致**。
但重建侧**仍返回 0**（走 deinit 分支）⇒ 分歧不在命令，而在**数据传输本身**。

#### 一、线索：设备访问次数差 3 倍

| 侧 | SFC 寄存器访问次数 | 命令条数 |
|---|---|---|
| 工厂 | **180** | 4 |
| 重建 | **57** | 4 |

三轮 CI（art27/28/29）稳定复现 ⇒ 与 `spi_id` 无关的**结构性差异**。

#### 二、根因：`*dst++ = reg[DATA]` 的 load 被提升出循环并向量化

**工厂原版（权威）**：

```asm
2c3c48:  add r1, r2, #264        ; r1 = &reg[0x108]（数据寄存器）
2c3c58:  ldr r3, [r1]            ; ★ 每轮迭代都重新读
2c3c5c:  str r3, [r5], #4        ; *dst++ = r3
2c3c60:  cmp r5, r4
2c3c64:  bne 2c3c58
```

**我们的重建（LLVM 21）**：

```asm
501ee68:  ldr r2, [r0, #264]     ; 只读一次
501ee90:  vdup.32 q8, r2         ; ★ 广播成 4 个字
501eea0:  vst1.32 {d16,d17}, [r4]!   ; 一次存 16 字节
```

用 `-S -g` 让编译器自报归属：内层循环 `.LBB0_19` 的 `.loc 2 88` = 源码第 88 行
`*param_3 = puVar3[0x42];` ⇒ **该 load 被提升**（`vdup` 在外层 `.LBB0_18`）。

**后果链**：目标缓冲区被**同一个字**填满（而该寄存器是 FIFO，每次读返回下一个字）
⇒ 24 字节校验和失败 ⇒ `spi_driver_init()` 返回 0 ⇒ `main()` 走 deinit 分支
⇒ 打印 `find sound/video_driver_deinit process fail`、**进不了 `main_Menu()`**
⇒ 行为差分在「可判定前缀 **17/31**」处提前终止。

#### 三、修复：把该访存限定为 `volatile`

```c
*param_3 = *(volatile gh_uint *)(puVar3 + 0x42);
```

语义上它就是**设备 FIFO**：「一次 C 访问 = 一次设备访问」。ARM 上仍生成普通 `ldr`，
与原厂指令序列一致（不引入 `mcr`/`dsb` 之类副作用）。

**修后实测（本地产物反汇编）**：`sfc_request` 内 `vdup`/`vst1` **归零**，
`ldr r6, [r0, #264]` 落在循环内 ⇒ 形状与工厂一致。

#### 四、★ 新增门禁 B8：设备访问计数一致性（该类缺陷在 stdout 里不可见）

这个分歧**在前 17 行 stdout 里完全看不出来**（两侧逐字相等），只有后续分支不同才暴露。
⇒ 新增两项判据（`behav_capture.sh` 提取 + `behav_diff.py` 比对）：

| 判据 | 含义 |
|---|---|
| **B8a `sfc_cmds`** | 两侧发出的设备命令**条数**必须相等 |
| **B8b `sfc_faults`** | 两侧**寄存器访问次数**必须相等（不等 ⇒ 有访存被提升/合并/向量化，或循环结构不同）|

原理：两侧跑的是**同一份** shim（同一份假设备）⇒ 访问它多少次是**可观测的客观事实**，
不等即说明「设备交互的轨迹形状」与工厂不同。**若早有这条门禁，本轮可立刻定位。**

三态单元测试：`180:180` → PASS；**`180:57` → FAIL（并打印修正提示）**；`cmds=0` → SKIP。

#### 五、同轮复核的两件事（都做了实证，避免误判）

1. **尾字节路径没有丢 store**：Ghidra 原文第 116 行有 `*(char *)puVar5 = (char)(uVar4 >> (uVar10 & 0xff));`，
   生成的汇编里对应 `.loc 2 121` 的 `strb r6, [r7], #1` ⇒ 该路径**完整**（比对反汇编后排除）。
2. **工厂的写路径**是 `ldr r3,[r4],#4` / `str r3,[ip]`（缓冲区 → 寄存器），与我们的源码方向一致 ⇒ 无需改动。

#### 六、CI 实测（commit `93444d00`）：B8 通过、前缀推进到 18/32

```
[PASS] B1 exit_code 139 vs 139        [PASS] B8a sfc_cmds   4 vs 4
[FAIL] B2 events  可判定前缀 18/32    [PASS] B8b sfc_faults 180 vs 180   ← volatile 修复生效
[PASS] B3 / B4 / B5 / B7
```

★ **`volatile` 修复确认生效**：设备访问次数 180 = 180（修复前 57）。
★ 前缀 **17/31 → 18/32**：重建侧已打印 `Load /sdcard/cubegm/update/firmware.upk fail!`
  ⇒ **校验和通过、`spi_driver_init()` 已返回 1、`UpdateROM()` 已被调用**。

剩余缺口：重建侧在 `main_Menu()` 的**第一行输出之前**崩溃（工厂侧已到 `mui_setting`）。

#### 七、★ 崩溃现场（shim 的 `★ 真崩溃` 两行 —— 新探针第一次就派上用场）

| 项 | 工厂 | 重建 |
|---|---|---|
| 故障地址 | `0x00000004`（NULL+4）| `0x63647328` |
| **pc** | **`0x0002b3c8` = `mui_setting`** | `0x3fe3b1ee`（**在共享库里**）|
| lr | `0x00017ec8`（游戏代码）| `0x3fe188f7`（库里）|
| r2 | `0` | **`0x003e139c` = `root_path + 4`** |
| r6 | `0x002dd64c`（"/" 分隔串）| `0x002dd64c`（同一个 "/"）|
| r0 / r1 | `0` / `0` | **`0x6364732f` / `0x63647328`** |

⇒ 重建侧特征是「**字符串内容被当作指针**」（`0x6364732f` 恰是 `"/sdc"` 的小端解读），
且 `r2` 指着 `root_path+4`、`r6` 是 `main_Menu()` 里那两个 `myStrrstr(root_path, "/")` 用的分隔串
⇒ 高度指向 `main_Menu()` 开头 `strcpy`/`myStrrstr` 那几行的重建保真度；
两者的 `pc` 都落在库里 ⇒ 是**传给库函数的参数被算错**，而不是我们自己的循环写错。

### 2026-09-17 第三十八轮：★★★★★★ **G1 根因定案** —— `key2` 是 BSS 变量（初值恒 0），
以及**两次自我打脸**（"key2 不是签名表"错、"注入无效=假设被推翻"错）

> 完整证据链见 `GAP.md` 的 G1 段（本轮重写）。

#### 一、根因（六条独立证据，全部可复核）

| # | 证据 | 结论 |
|---|---|---|
| 1 | strace：`openat(AT_FDCWD,"/sdcard/cubegm//ui_cn.zip",O_RDWR) = 3`（两侧同值，共 3 次） | **文件系统层打开成功** ⇒ 游戏的 `open … fail` 是 `TUnzip::Open` 返回 0，**不是 fopen 失败** |
| 2 | zip 自检：EOCD@4951259 / 条目 6 / `cd_size=543` / `cd_off=4950716`，`4950716+543 = 4951259` ✓ | **`ui_cn.zip` 完全合法** ⇒ 非文件损坏、非路径错 |
| 3 | 反编译 `unzlocal_SearchCentralDir`(0x10eb0) 66–69 行比对 `key2[0..3]` **或** `key2[4..7]`；`10fa4: ldrsb r0,[r3,#4]`，`r3`←GOT 槽 `0x3B1E10`（槽内 = `0x3E190C`） | 厂商把上游 `PK\x05\x06`(EoCD) 与 **`PK\x07\x08`**(spanned) 两个字面量**搬进了全局** |
| 4 | 程序头第二个 `PT_LOAD va=0x3AE5C4 filesz=0x3BB0 memsz=0x3350F` ⇒ 文件背衬止于 `0x3B2174`，`key2@0x3E190C` 在其后 | **`key2` 在 BSS ⇒ 初值恒 0**（程序自己不赋值） |
| 5 | Ghidra 812 函数：`key2` 只读不写；`driver.so` 里既无 `0x3E190C` 也无 `PK` 字节 | 排除驱动/copy-relocation/未反编译代码 |
| 6 | 邻居：`mainkey`128B、`m_crctable`128B、`ArchivePath`/`GamePath`/`key2`/`mdtemp1` 各 28B | `key2` 属**密钥/缓冲区簇** |

⇒ 全 0 的 `key2` 让倒搜目标变成「4 个 `0x00`」⇒ 错误位置命中 ⇒ 垃圾偏移 ⇒ `TUnzip::Open`=0
⇒ `mui_setting` 拿 NULL 再 `+4` ⇒ SIGSEGV。**工厂与重建同时失败是必然而非巧合**。
**这就是"门禁全绿、窗口只有 25%"的完整机制。**

#### 二、两次自我打脸（必须记住）

1. 我在 GAP 写过的「`key2` 不是签名表」——**错**。反汇编逐字节核对证明比对源就是 `key2`。
2. 我上一轮把场景 B 的"注入后行为逐字不变"读成"假设被推翻"——**错**。
   注入值写成了 `50 4b 05 06 **50 4b 06 06**`，而正确的第二签名是 **`50 4b 07 08`**
   ⇒ **注入值本身不可能是签名** ⇒ 那是**假阴性**，不构成任何反证。
   ★ 教训：**"单变量实验无效"必须先自证"该变量真的被设成了预期值"，否则结论无效。**

#### 三、本轮行动（两档单变量）

| 场景 | 开关 | 语义 |
|---|---|---|
| B | `CGM_KEY2_SEED=1`（**字节已修正**） | constructor 时写入 `PK\x05\x06 PK\x07\x08` |
| E | `CGM_KEY2_SEED=1 CGM_KEY2_HOOK=1` | 在 `open/openat` 命中 `.zip` **的瞬间重新断言** key2（把写入时刻推到 last-moment） |

判据（CI 输出里已带）：`grep -c "ui_cn.zip fail"` 三场景对比（0 = 窗口打开）；
B 无效而 E 有效 ⇒ 写入者被夹进 constructor→zip-open 的窄窗口；两者都无效 ⇒ 写入在 open 之后。

#### 四、本轮其它修正

- **场景 D 拆除**（`CGM_SFC_PATTERN`）：首跑已给出结论 —— SFC 载荷替换会**打断启动链**
  （连 `main_Menu` 都到不了）⇒ 不参与门禁；开关保留在 shim 里备用。（也省 CI 分钟。）
- 顺手修掉一个**我的静态扫描假阴性**：我此前两次报告"工厂 .text 里 0 处构造 `0x3E190C`/`0x3B1E10`"，
  实际是**我的正则坏了** —— objdump 的注释格式是 `; (3b1e10 <sym>)`，我按 `;\s*hex` 匹配必然漏。
  ⇒ 已写入技能铁律 101：**任何"扫描 0 命中"必须先用一个"必然命中"的样本自证扫描器可用**。

#### 五、提交

- `57ba7e8b`：shim 种子字节修正 + `CGM_KEY2_HOOK` + 场景 E（替换 D）

#### 二·补充（同日第二轮 CI，`1879e05c` / `97708de8`）：**G1 正向判决 + 一个已修的假分歧**

| 项 | 结果 |
|---|---|
| **zip 的实际打开路径** | **`fopen`**（I/O 轨迹：`io #11/#12/#15 fopen rc=0 …/ui_cn.zip ◀ ZIP`）⇒ 拦 `open`/`openat` 拦错了地方（glibc `fopen` 内部绕过 PLT） |
| **★ 正向判决** | `.zip` 打开瞬间断言 key2（`CGM_KEY2_HOOK=1`）后，**工厂 `M6 = ✓(包已打开(条目缺失))`**，报错变为 `find ui.cfg in …zip fail` ⇒ **根因确证**（不只是"两侧一致地坏"） |
| **真机证据** | 原厂 SD 的 `menu.log`（444 B，设备自写）= 结构化记录（`0x11c:0a`、`0x120: 0x0a9d=2717`、多处 `ff ff ff ff`）⇒ 真机上**菜单运行过并被使用** ⇒ 真机能打开资源包 ⇒ `key2` 在真机确有来源（沙箱缺的正是 SFC security 数据那一环）；**G4 的"版本不匹配"分支基本可排除** |
| 次级缺口 | 条目查找仍失败（`find ui.cfg in … fail`），但 `ui.cfg` **确实在包里**；**工厂侧同样出现** ⇒ 包/环境问题，归入 G3 |
| **假分歧（已修）** | 在拦截的 `fopen` 里调 `note()`（走 `vsnprintf`）⇒ stdio 再入 stdio ⇒ 重建解析 `setting.xml` 崩：`pc=0x3a`、`lr=mxml_load_data+0xdbc`、`blx sl` 而 `sl=0x3a`(ASCII ':')、`[sp+0]=_IO_wfile_jumps`。工厂侧未踩到同一窗口 ⇒ 曾表现为"两侧不同"的假分歧 |
| 修复 | ① `note()` 改**零-stdio**自包含格式化器（顺带让信号处理器 async-signal-safe）；② 新增 `tools/shim_fmt_selftest.py`（实时抽取 + 无-stdio 硬断言 + 12 用例对拍），接入 `1to1-verify` 硬门禁，并**反向验证**过；③ 崩溃报告器**提前到 constructor**（原先崩在 SFC 装配前就没有现场） |

### 2026-09-17 第三十九轮：★★★★★★ **观测窗口打开了**（重建侧首次走到 M6）+ 找到 19 项同类漏参

#### 一、突破：一切都是一个**漏掉的函数参数**

| 场景 E 指标 | 修前 | 修后 |
|---|---|---|
| 重建侧 M5 `main_Menu` | ✗（崩在 `setting.xml`）| **✓** |
| 重建侧 M6 资源包 | ✗（未走到）| **✓（包已打开）** |
| 重建侧 stdout 行数 | 3 | **21** |
| 重建侧专有函数覆盖 | 4 / 223 = 1.79% | **58 / 223 = 26.01%** |

**缺陷本体**：`mxmlLoadFile(0, fp)` 漏了第 3 个参数 `cb`。
工厂机器码为证（每处）：`mov r2,#0`（cb=NULL）→ `mov r1,fp` → `mov r0,#0`（top=NULL）→ `bl mxmlLoadFile`
⇒ 真形态 `mxmlLoadFile(NULL, fp, NULL)`；我们少传一个 ⇒ ARM 上 r2 是**寄存器垃圾**
⇒ `mxml_load_data` 内 `blx r10`，r10 = **0x3a / 0x00（随场景漂移）**。
这解释了此前两个说不通的现象：同一二进制"有时崩有时不崩"、崩点 pc 两轮之间会变值。
同类第二处：`mxmlDelete()`（一个实参都没传）⇒ 改为 `mxmlDelete(tree)`。
**治理**：`proto.h` 三个 K&R 空参声明改**真原型** ⇒ 漏参在严格编译门禁阶段直接报错。

#### 二、同一物种的存量缺陷：**19 个函数存在漏参**（已建机械门禁）

`proto.h` 有 **107 个 K&R 空参声明**、**235 处零实参调用点**。新增 `tools/scan_kr_argcount.py`：
以**工厂反汇编**为权威（数每个 `bl` 之前写过几个 `r0..r3`），内置 3 个手工核对过的**自证锚点**
（`mxmlLoadFile=3 / mxmlDelete=1 / mxmlSaveFile=3`），自证不过就拒绝出结论。
首跑抓到 19 个函数（`mui_ReadJoystick` 工厂 57 处调用 / `mui_WaitNMI` 23 处 / `SaveMenuLog` 12 处 /
`mui_DisplayGameSum` 15 处 / `GetZipItemA` 工厂 4 参我们 3 参 …）。
**棘轮语义**：19 项入 `tools/kr_argcount_pending.txt`，**台账外的新增违例一律失败**；已做反向验证。
性能：一次建索引后 **2.8 秒**（原每个函数重扫 758k 行 ⇒ ~60 秒）。

#### 三、本轮还补了两条仪器纪律（都因踩坑而来）

1. **零-stdio 日志器 + 自检门禁**：在被拦截的 `fopen` 里调 `note()`（内部 `vsnprintf`）
   ⇒ 在 stdio 内部再入 stdio，把 guest 的 FILE 结构污染成 `blx sl`（sl=0x3a）的垃圾跳转，
   而且**只把两个二进制中的一个搞崩** ⇒ 一度伪造成"两侧分歧"。
   现 `note()` 为零-stdio 自包含格式化器；`tools/shim_fmt_selftest.py`（从源码实时抽取 +
   硬断言无 stdio + 12 用例对拍）已作 `1to1-verify` 硬门禁，并**反向验证**过。
2. **崩溃报告器提前到 constructor**：原先只在 SFC 装配时安装 ⇒ **最需要现场的那次崩溃**
   （发生在装配之前）只剩 qemu 一行 `uncaught target signal 11`，pc/lr/栈全丢。
   本轮正是靠补上它才拿到 `pc=0x3a / lr=mxml_load_data+0xdbc`，一击定位。

#### 四、提交（全部 CI 绿）

`1879e05c` → `97708de8` → `adb16450` → `1ac8c25e` → `1fa1469e` → `c0214eb0` → `af9bdcfd`；
最终一次三 workflow 全部 **success**（`1to1-verify` 含两道新硬门禁）。
两个 CI 专有坑：① `zig` 由 pip 安装在 site-packages **不在 PATH**（不能用 `command -v zig`）；
② Ubuntu `/usr/bin/objdump` 对 ARM32 **`-t` 能读、`-d` 报 architecture UNKNOWN**
⇒ 工具优先用 `arm-linux-gnueabihf-objdump`、否则 `objdump -d -m arm`。

### 2026-09-17 第四十轮：★★★ **更正**「19 项漏参」为错口径产物（真实存量 = 0）+ 门禁换保守口径

#### 一、更正

上一轮报的"**19 个函数存在漏参**"**是错的**。原因是机器码口径（数 `bl` 前的 `r0..r3` 个数）
被三类噪声污染，而我对**全部调用点取 max**，把噪声直接放大成 19 项：

| 噪声来源 | 实例 | 效果 |
|---|---|---|
| 临时寄存器 | `mxmlDelete` 调用点旁的 `ldr r3,[r4,#204]` | 多算（1 参 → 2/3 参）|
| 尾调用继承 | `mxmlRelease → mxmlDelete`（r0 来自本函数参数）| 少算（1 参 → 0）|
| 为未用形参预置 0 | `stbtt_GetFontVMetrics(font,&asc,0)` 把 r3 也置 0 | 多算（3 参 → 4）|

跨全部调用者复核：20 项里绝大多数是"**我们在别处传对了、只是某个调用点少传**"的误判。

#### 二、换成保守口径（新硬门禁）

`tools/scan_call_args.py`：以**工厂 per-function 反编译 C 的调用表达式**为准，逐 `(调用者, 被调者)` 比实参个数。
误差方向**只少算不多算**（Ghidra 推断原型偏小时会丢参数）⇒ **不会产生假阳性**，只会漏报（由机器码口径本地兜底）。
自证锚点：`dir_serial_list=2 / strupr=1 / stbtt_GetFontVMetrics=4`。
结果：**1279 对可比对、`✓ 无新增漏参`**。CI 硬门禁已换为该步骤；机器码工具降级为本地工作清单。

#### 三、真实修复仍然成立（实证强度见覆盖率）

`mxmlLoadFile`（6 处漏第 3 参 `cb`）+ `mxmlDelete`（1 处零实参）修好后：
场景 E 重建侧 **覆盖率 4 → 58 个函数（1.79% → 26.01%）**、`M5/M6` 首次到达、stdout 3 → 21 行。

#### 四、方法学教训（技能铁律 106）

**仪器口径要选"误差方向保守"的那一种**；每个口径上线前**必须用人工核对过的锚点自证**。
本轮四次修正全靠锚点拦下 —— 若无锚点，我会拿着噪声清单去"修"不存在的缺陷，
既烧轮次，又可能把正确代码改错。

### 2026-09-17 第四十一轮：★★★ **M6 之后第一个真分歧** + **上游库版本钉错（机械证据）**

#### 一、窗口打开后立刻抓到第一个真分歧

场景 E 两侧 `M5/M6` 都到达，但 stdout 第 21 行起分叉：工厂打印 `find ui.cfg in <zip> fail` 与
`find setting.raw fail`，我们**都缺**。重建侧崩点定位到 **`stbtt_GetFontVMetricsOS2 + 0x8`**
（就在打印 `find font.ttf in <zip> fail` 之后）。
三条消息的发出位置已逐个定位：`get_items_from_zipfile`（`mui_LoadConfig` 调用）/ `mui_InitFont` /
`mui_LoadUIResource("setting.raw")`。
**已排除**（逐行核对）：我们的 `get_items_from_zipfile`、`FindZipItemA`、`unzLocateFile`、
`unzStringFileNameCompare` 与工厂**语义一致**（函数尺寸 8.75×/2.2× 的差异只是编译产物，差点误判）。

#### 二、上游库版本钉错（新增机械门禁，抓到 14 项）

`tools/scan_symbol_delta.py`：对拍两侧**上游公有 API 符号集合**（过滤内联重命名；
自证锚点 `stbtt_FindSVGDoc` 必须报为"我们多出"）。结果 **我们多出 14 个**：
stb_truetype 5 个（**SVG 自 v1.22 才有** ⇒ 工厂更旧）、mini-XML 7 个、Helix 2 个。
**判"版本旧 vs 被 gc-sections 裁剪"**：工厂保留了同样没被使用的 `stbtt_PackFontRanges*` 等
⇒ 没做裁剪 ⇒ **确系版本更旧**。
⇒ 现有"上游定版"（stb_truetype v1.26 等）**需重新取证**；门禁已上线（14 项入台账，新增即失败）。

#### 三、本轮新增的两道机械门禁

| 门禁 | 作用 | 当前状态 |
|---|---|---|
| `调用点实参对拍`（上一轮） | 漏参（寄存器垃圾）类缺陷 | 绿（真实存量 0）|
| `上游库公有 API 集合对拍`（本轮） | 上游版本钉错 | 绿（14 项台账棘轮）|

#### 四、方法学教训（技能铁律 107）

**函数尺寸差 ≠ 语义差**：厂商版本常见的"函数变小"可能只是**尾调用/内联**；
本轮我先据 `unzStringFileNameCompare` 16B vs 140B 推断"厂商裁剪"，读了源码才发现**语义完全相同**。
⇒ 尺寸只作**线索**，结论必须回到**源码/机器码语义**。

### 2026-09-17 第三十七轮：★★★★★★ **进度量化 + 差距分析**（回答「距离直接替代还差什么」）

> 📄 完整报告见仓库根 **`GAP.md`**（含证据链、差距清单、推进顺序、验收标准）。本节只记本轮新增的仪器与结论。

#### 一、`1to1-qemu-behav` 的 `PASS` 到底意味着什么（必须写清楚）

| 事实 | 数值 |
|---|---|
| 两侧 `exit_code` | **139 vs 139**（都 SIGSEGV）|
| 崩点 | 同构：`mui_setting` 里 NULL+4（`ldrh rX,[rX,#4]`，`addr=0x4`）|
| 可复现前缀 | 38/38 行（场景 A）/ 39/39（场景 B）|
| **专有函数覆盖率** | **48/223 = 21.52%**（工厂 49/223 = 21.97%）|
| **专有字节覆盖率** | **30,804 / 122,922 = 25.06%** |

⇒ **`PASS` = 「到崩溃点为止与原厂等价（包括一样打不开 UI 资源包、一样崩在第一屏）」**，
  **≠「能跑起来」**。`mui` 模块 42 函数 / 70,396 B（重构量的 57%）在 P5 里从未执行过。

#### 二、本轮新增三件仪器

| 仪器 | 文件 | 作用 | 首跑结果 |
|---|---|---|---|
| **执行覆盖率度量** | `tools/qemu_coverage.py` + `tools/coverage_baseline.txt` | 吃 `-d exec` **原始**轨迹 → 函数/字节/专有函数三档覆盖率 + 未覆盖重量级清单 | 见上表；**顺带抓到 `ClearBuffer` 分歧** |
| **场景 B：key2 注入** | `tools/guest_shim/fake_mem.c`（`CGM_KEY2_SEED`）+ workflow 第 2 场景 | 让「UI 资源包可打开」这条路径可观测 | ⚠ **否定结论**：两侧行为与场景 A 逐字相同 ⇒ 见下 |
| **场景 C：`libkms.so.1` 空桩** | `tools/build_libkms_stub.sh` + workflow 第 3 场景 | 满足 `driver.so` 的 `DT_NEEDED` ⇒ 硬件接口层首次可观测 | 桩已验证（1240 B / ET_DYN / SONAME 正确）|

#### 三、★ 上一轮「必须比对 `key2`」的归因**被推翻**（技能铁律 97）

单变量实验：shim 把 `key2[0..15]` 写成 `PK\x05\x06/PK\x06\x06/PK\x03\x04/PK\x01\x02`（两侧同一注入），
并自证：① `-E CGM_KEY2_SEED=1` 确实出现在 wrapper 里；② shim 的 `key2 seeded` evidence 行已打印；
③ **崩溃现场回读 `key2`** 仍是注入值。

结果：两侧 stdout 与覆盖率**与场景 A 逐字相同**（仍 `open /sdcard/cubegm//ui_cn.zip fail` ×2）。
⇒ 若比对源真是 `key2`，写对值就该打开 zip ⇒ **比对源不是 `key2`**（或不止它）。
当时的"行为翻转"来自同一提交里**同时改的另 3 件事**（`uMaxBack` 阈值 / `uReadSize` 计算 / 短读即 `return 0`）
—— 这正是"一次改多件事 ⇒ 归因必错"的活标本。`MEMORY.md` 已就地标注为**待复核**。

#### 三·补、二轮实测（CI `a5743b67d3c7`）—— 两条判决性结论

| 观测 | 结果 |
|---|---|
| shim 注入 key2 后**回读** | `50 4b 05 06 50 4b 06 06` ✓ 写入成功 |
| **崩溃现场**再读 key2 | **`00 00 00 00 00 7d 1e 47`（两侧二进制完全相同）** |
| 行为是否变化 | **与场景 A 逐字相同**（仍 `open …/ui_cn.zip fail` ×2、覆盖率 48/49 不变）|
| 场景 C：`driver.so` | **两侧 `open driver.so sucess`** → `video_driver_setting 0 1 1` → `open drm!` |
| 场景 C：终止点 | 两侧均 `cannot find/open a drm device: Function not implemented` → SIGSEGV（exit 139）|
| 场景 C：差分 | 可复现前缀 **18/18**、门禁 PASS（两侧完全一致）|
| 场景 C：覆盖率 | 反而降到 6~7 个专有函数（窗口变浅 = 环境缺口，不是实现回归）|

★ 结论 1：**`key2` 有写入者**（静态取证漏判）+ **写进去的不是 ZIP 签名** ⇒ `key2` 不是签名表，
  「必须比对 key2」的归因**被实证推翻**；`GAP.md` 已就地更正（原写"无写入者"是错的）。
★ 结论 2：`libkms.so.1` 空桩**成功解锁硬件接口层**，且该层两侧行为逐字一致（1:1 保真度初步可信）；
  下一个环境缺口 = **有状态的假 DRM 设备**（否则显示层永远走不出 `open drm!`）。
★ 覆盖率棘轮已按 **场景/label** 分键登记（A: 48/49、B: 48/49、C: 6/7），不再跨场景互相误报。

---
#### 三·再补、三轮实测：**进度刻度的修正**（覆盖率会随环境非单调 ⇒ 改用里程碑）

| 里程碑 | 场景 A | 场景 B | 场景 C |
|---|---|---|---|
| M0/M1 启动+配置 | ✓✓ | ✓✓ | ✓✓ |
| M2 SPI/SFC | ✓ | ✓ | ✗（更早终止）|
| M3 `driver.so` | ✗ 加载失败 | ✗ | **✓ 成功** |
| M4 DRM | ✗ | ✗ | **✓ `open drm!`** |
| M5 `main_Menu` | ✓ | ✓ | ✗ |
| M6 UI 包打开 | ✗ | ✗ | 未走到 |
| M7 菜单存活 | ✗ | ✗ | ✗ |
| 两侧差集 | **空** | **空** | **空** |

★ 覆盖率 48→6 **不是退步**：同场景下工厂 7 / 控制组 7 / 重建 6 **三者同步下降** ⇒ 环境属性。
★ `key2` 归因**二次修正**：比对源确实是 `key2`（`10fa4: ldrsb r0,[r3,#4]`，`r3`←GOT 槽 0x3B1E10 = 0x3E190C），
  但我们的注入**在搜索前被运行期写入者覆写** ⇒ 那次实验**无效**（no-op ≠ 假设被推翻）。
  写入者两次静态定位均失败（Ghidra 0 写入者 + 75 万条指令 0 命中地址构造）⇒ 走 **GOT 间接指针**，静态盲区。
★ 新仪器：`tools/milestones.py`（进度刻度，已接入 CI 每场景产出）+ shim 的 `CGM_KEY2_PROBE` /
  `CGM_SFC_PATTERN` 两个实验开关；**场景 D**（SFC 载荷统一 0xC7 + 现场 dump key2）已接入。

---
#### 四、下一步（按收益/成本）
1. **重新定位 `SearchCentralDir` 的比对目标**（用 `key2` 之外的候选：`mdtemp1`/`ArchivePath` 邻域、
   或 `unzOpenInternal` 里真正的 EoCD 校验路径）—— 场景 B 的探针设施已就绪，可直接复用；
2. **推进场景 C**（`driver.so` 加载后驱动接口层的行为）；
3. **覆盖率棘轮**：把首跑数字回填 `tools/coverage_baseline.txt`，之后覆盖率只升不降；
4. 真机对照（工厂 vs 克隆，同 SD）以判定 G1 的两个分支。

---
### 2026-09-17 第三十六轮：★★★★★★ **行为差分门禁首次全绿**（口径修正：探针诊断 != 被测行为）

#### 一、唯一剩下的缺口 = **我自己探针的诊断输出**

`key2` 修好后的 CI（`dacf5e7f1853`）已经让**程序行为**逐字一致：
`open .../ui_cn.zip fail` ×2 与工厂相同、stdout 逐行 diff 只剩 3 行 meminfo 数值波动。
但 B2 仍卡在 **34/41**，唯一原因是 shim 崩溃报告里的 **逐帧栈回溯**：

| | 工厂 | 重建 |
|---|---|---|
| `[shim] [sp+N] = …` 行数 | **5** | **2** |
| 其余 22–34 行（shim 语义行）| **逐行相同** ✓ | ✓ |

**根因**：逐帧行的行数与内容取决于**各二进制自己的栈帧布局 + dladdr 解析结果** ——
两份不同编译的二进制**永不可能相同**。把它算进行为指纹 == 要求「两次编译的栈布局一致」
⇒ **门禁永不可通过，且掩盖真实分歧**（这条规则让 34/41 看起来像行为没对齐，其实是探针口径错）。

#### 二、修正（两边都做：一个减噪、一个加信号）

| 位置 | 改动 |
|---|---|
| `behav_capture.sh` 的 stderr 事件段 | **剔除** `[shim] [sp+N]` 逐帧行（`stderr.txt` 原样保留并上传制品，人仍可查完整回溯）|
| 同上 | **新增布局无关的崩溃形态事件**：`C|crash_fault=<原始故障地址>`、`C|crash_signal=<信号号>`（不经 `norm` 的 `ADDR` 折叠）|

★ 设计要点：**减掉的是「取决于编译布局的噪声」，补上的是「崩在哪个地址、什么信号」这一最关键语义**
（原始数值、要求两侧严格相等）⇒ 门禁既可通过，又不丢信号。

#### 三、本地用真实制品验证（`build/qemu_art41`，不花 CI 轮次）

```
factory  事件 41 -> 38（剔除 6 行逐帧），崩溃形态 fault=0x00000004 signal=11
rebuild  事件 38 -> 38（剔除 0 行逐帧），崩溃形态 fault=0x00000004 signal=11
control  事件 41 -> 38（剔除 6 行逐帧），崩溃形态 fault=0x00000004 signal=11

参考侧 38 行 / 控制侧 38 行；**可复现前缀 = 38 行**
  ✓ 参考实现两遍完全一致（整段都可判定）
  [PASS] B1 exit_code  139 vs 139        [PASS] B5 log_sha  d7c86a6f… 一致
  [PASS] B2 events     **38/38 行一致**   [PASS] B6/B7/B8a/B8b 全 PASS
  [PASS] B3/B4 new_files / changed_files 0 vs 0
  门禁结果: PASS (0 项失败)   退出码=0
```

#### 四、里程碑意义

这是 **P5 行为差分门禁的首次全绿**：在「同一环境 + 同一路径 + 同一份假硬件 shim」下，
**重建产物与工厂 rkgame 的可观测行为（stdout/stderr 事件、退出码、文件变更、menu.log 内容、
shm 心跳、SFC 设备访问计数、崩溃形态）逐项一致**。

#### 五、下一步（把「绿」扩大覆盖面）
1. **加场景**：不同 `setting.xml` / `autorunfile` 分支 ⇒ 进入不同菜单路径（当前只覆盖到 `mui_setting` 的 NULL 解引用）。
2. 继续收敛剩余上游函数（`unzLocateFile` 240/528、`unzGetGlobalComment` 148/308、`unzClose` 60/144、
   `TUnzip::{Unzip,Get,Close,Find}`、`unzOpenCurrentFile` 单参/双参）—— 它们当前被「崩在同一处」掩盖。
3. 把 `mui_setting+0x114` 那个 NULL 解引用也修掉 ⇒ 观测窗口才能越过它继续推进。

---

### 2026-09-17 第三十五轮：★★★★★ 第八个真实分歧**根因收尾** —— 中央目录搜索必须比对全局 `key2`（不是 PK 字面量）：★★★★★ 第八个真实分歧**根因收尾** —— 中央目录搜索必须比对全局 `key2`（不是 PK 字面量）

#### 一、`key2` 是**运行时全局**，工厂的签名模式来自它

| 证据 | 内容 |
|---|---|
| 工厂机器码 `0x10f9c` | `ldr r3, [r6, r2]`（`r6 = pc+0x3A10F0 = 0x3B1FC4`，`r2 = -0x1B4`）⇒ 取 `*(0x3B1E10)` = **`0x3E190C`** |
| 工厂 symtab | **`key2 @0x003E190C size=28`（type=1，OBJECT）** —— 在 `.bss`，静态态全 0 |
| 工厂 rodata | **没有** `PK\x05\x06` / `PK\x01\x02` / `PK\x03\x04` 字面量 ⇒ 模式**只能**来自该全局 |
| 比对方式 | `ldrsb` 逐字节比 **`key2[0..3]` 或 `key2[4..7]`**（两个 4 字节签名放在同一个 8 字节前缀里） |
| 我方现状 | `globals.h:4680` 已有声明、`factory_image.S:2085` 已有别名 **`.set key2, __f_bss_base + 0x2f794` = 0x3E190C（与工厂逐字节一致）** ✓ |

**⇒ 我方 `unzlocal_SearchCentralDir` 用硬编码 `0x50 0x4b 0x05 0x06` 才是错的**：
总能找到 EoCD ⇒ 打开成功；而工厂用 `key2`（本环境为 0）⇒ 找不到 ⇒ `OpenZipU` 返回 0 ⇒ `open ... fail`。
**换用同一个全局后，两侧看到的 `key2` 内容必然相同**（无论厂商 init 是否写入、写在哪），判定天然对齐。

#### 二、按工厂机器码逐条重写（`0x10eb0..0x11074`）

| 工厂指令 | 语义（已落入我方源码注释） |
|---|---|
| `10ef0 movw r3,#65534 ; bhi 1100c` | `uSizeFile > 0xfffe ? uMaxBack=0xffff : =uSizeFile`（**65534，非标准版 0xffff**）|
| `10f14 cmp r5,#4 ; bls 10ff8` | `uSizeFile < 5` ⇒ `zfree` + `return 0` |
| `10f28 add r7,r7,#1024` / `10f3c movcs r7,r8` | 循环 `uBackRead = min(uBackRead+0x400, uMaxBack)` |
| `10f44/10f4c cmp r7,fp(1028)` | `uReadSize = (uBackRead > 0x403) ? 0x404 : uBackRead` |
| `10f40 sub r5,r3,r7` | seek = `uSizeFile - uBackRead`（**不夹取**，与标准版不同）|
| `10f78 cmp r0,#1 ; bne 11064` | **`lufread` 必须恰好读满 1 个元素**，否则 `return 0` |
| `10f9c/10fa4/10fb0` | 反向扫描，比 `key2[0..3]` / `key2[4..7]` |
| `10fec add r4,r4,r5 ; beq 11054` | 命中位置 = 窗口内偏移 + `uSizeFile-uBackRead`；为 0 则下一窗口 |
| `11054 cmp r7,r8 ; bcc 10f28` | do-while：`uBackRead < uMaxBack` 继续 |
| `11064 ldr r4,[sp,#4]` | 短读时返回 `lufseek` 的返回值（0）|

**验证**：编译 rc=0、`key2` 为 UND 外部引用 ✓、最终 ELF 里 **`key2 @0x003e190c`（与工厂同址）** ✓、
门禁全 PASS（布局 193/194、ABI PASS、dyn_audit FAIL 0、上游指纹 FAIL 0）。

#### 三、本轮推送
`dacf5e7f1853`：`unzip.cpp`（blob `9b6b207fc2`）+ `XUnzip.o` + `.XUnzip.src.sha256`。
（推送器报"上传 0"是因为前一次调用已把变更送出；逐 blob 校验 `VERIFY 1167/1167 blobs match` ✓）

#### 四、下一步
1. 盯 CI：重建侧 stdout 期望出现 **`open .../ui_cn.zip fail`**（与工厂同构）⇒ 两侧停在**同一处**崩溃。
2. 剩余未对齐（`unzLocateFile` 240/528、`unzGetGlobalComment` 148/308、`unzGetLocalExtrafield` 164/320、
   `unzClose` 60/144、`TUnzip::{Unzip,Get,Close,Find}`、`unzOpenCurrentFile` 单参/双参）继续同法收敛。

---

### 2026-09-17 第三十四轮：★★★★★ 第八个真实分歧（根因）—— `luf*` I/O 底座：**stdio vs 裸 fd**

> 关键突破：**制品里本来就有 `-strace` 轨迹** —— 不需要再猜、也不需要多花一轮 CI。
> 直接 grep 目标路径，两侧的 syscall 序列把答案写死了。

#### 一、同一份制品的 syscall 对照（决定性）

| | 工厂（参考） | 重建（改前） |
|---|---|---|
| zip 打开 | `openat("/sdcard/cubegm//ui_cn.zip", **O_RDWR**) = 3` | `openat(..., **O_RDONLY**) = 3` |
| 打开结果 | **成功** | **成功** |
| 尾部搜索读 | `_llseek(3, **4947968**, SEEK_SET)` + `read(3, buf, **3313**)` | `_llseek(3, **4950253**, SEEK_SET)` + `read(3, buf, **1028**)` |
| 后续 | seek→EOF、`read(4096)=0`、**close**（未读中央目录） | seek→4950716（中央目录偏移）、逐字节读完 |
| stdout | `open .../ui_cn.zip fail` ×2 | `find font.ttf in .../ui_cn.zip fail` |
| 崩点 | `mui_setting+0x114`（`ldrh r0,[r3,#4]`，r3=0 ⇒ addr 0x4） | `stbtt_GetFontVMetrics`（r0=0 ⇒ NULL font） |

⇒ **两侧都成功打开了文件**，却对"能不能解析这个 zip"得出**相反结论**。

#### 二、根因（字节级证据，非推断）

1. 工厂 `lufopen @0x109fc` 用 **`fopen`**：模式串 = `pc(0x10a7c) + 字面量(0x002cb430)` = `0x2DBEAC`，
   该处字节实测 **`"r+b"`**（读+写）⇒ syscall `O_RDWR` ✓ 与 strace 逐字一致。
2. 工厂 `lufread @0x10c20` = `fread@plt(p,size,count,f)`（返回"元素个数"，0 时置 `herr`）；
   `lufseek`/`luftell`/`lufclose` 同理走 `fseek/ftell/fclose`（错误码 19/29）。
3. **我们** 走 `CreateFile(GENERIC_READ)` ⇒ `open(O_RDONLY)` + `fstat` + `lseek`（**裸 fd**）。
4. **差异的放大器**：stdio 的 `fseek` 会把底层 fd **对齐到 4 KiB 边界**再整块缓冲
   （4950253 → 4947968，`read` 3313）；裸 `lseek` 不会（4950253，`read` 1028）。
   于是 `unzlocal_SearchCentralDir` 里那句 **`if (lufread(...) != 1) return 0;`**
   （工厂 `0x10f78: cmp r0,#1 / bne 11064`）在两侧**得到相反结果**。

#### 三、修复：按工厂机器码忠实重写整层（不是打补丁）

`src/upstream/xunzip/unzip.cpp` 的 `LUFILE` + 6 个 `luf*` 全部重写：

| 项 | 工厂语义（照抄） |
|---|---|
| `lufopen` | `(unsigned)(flags-1) > 2` ⇒ `*err=65536`；`flags==1` ⇒ **内存缓冲**（不是 Win32 HANDLE）；否则 `fopen((char*)z,"r+b")`，失败 ⇒ `*err=512` |
| `lufread` | FILE* ⇒ `fread(ptr,size,n,f)`；内存 ⇒ `memcpy` + `total/size` |
| `lufseek` | FILE* ⇒ `fseek`（SET 加 `initial_offset`），非法 ⇒ `19`；不可 seek ⇒ `29` |
| `luftell` | FILE* ⇒ `ftell(f) - initial_offset`；内存 ⇒ `pos` |
| `lufclose` | `fclose` + `delete`；NULL ⇒ `-1` |

**符号尺寸收敛**（工厂 = 参考）：

| 符号 | 工厂 | 改前 | 改后 |
|---|---|---|---|
| `lufopen` | 212 | 284 | **200** |
| `luftell` | 68 | 84 | **68 ← 完全一致** |
| `lufseek` | 172 | 176 | **184** |
| `lufread` | 168 | 132 | **144** |
| `lufclose` | 60 | 64 | **64** |

最终 ELF 实测：`bl __ARMv7ABSLongThunk_fopen` ✓；门禁全 PASS
（宽松/严格 213/213、审计 0/0、布局 193/194、ABI PASS、dyn_audit FAIL 0、变参 4/4、`.rodata` 类型 PASS、指纹 FAIL 0）。

#### 四、顺带修掉两处**我自己**的工具缺陷

- `push_1to1.py` 的 YAML 闸门漏 `import re` ⇒ 推送时 `NameError` 直接崩（已修，函数内自足导入 + 语法自检）。
- workflow 步骤名以**反引号**开头 ⇒ YAML 解析失败（`1to1-verify` 退化成文件路径、无 jobs、18 步全丢）。
  已改回普通文本，并由新增的推送前 YAML 自检保证不再复发（实测：`pyyaml` 解析 ✓ / 2 个文件通过）。

#### 五、下一步

1. 盯 CI：重建侧 stdout 是否变成 `open .../ui_cn.zip fail`（与工厂同构）。
2. 若同构 ⇒ 两侧应停在**同一处**崩溃（`mui_setting`），可判定前缀大幅推进。
3. 剩余未对齐项按同一方法（机器码 + `-strace` 差分）继续收敛：
   `unzlocal_SearchCentralDir`(452/616)、`unzLocateFile`(240/528)、`unzGetGlobalComment`(148/308)、
   `unzGetLocalExtrafield`(164/320)、`unzClose`(60/144)、`TUnzip::Unzip`(28+.part.7 / 1600)、
   `TUnzip::Get`(152+.part.5 / 1208)、`TUnzip::Close`(68/168)、`TUnzip::Find`(180/288)、
   `unzOpenCurrentFile`（单参 / 双参——**唯一双侧签名不同者**）。

---

### 2026-09-16 第三十三轮：★★★★★ 第八个真实分歧 —— `.rodata` 字符串被 Ghidra 渲染成**整数** ⇒ 多解引用一次

#### 一、崩点（CI `d458968b771c`，承接第三十二轮"崩点移出 unz 路径"）

```
pc -> libc.so.6 + 0x6acb2   符号 = strcpy
lr -> _ZN6TUnzip4FindEPKchPiP8ZIPENTRY + 0x24
访问地址 0x746e6f66 = ASCII "font"（= "font.ttf" 的前 4 字节）
```

我们 `TUnzip::Find` 的反汇编：`mov r0, r7（栈缓冲）; bl strcpy` ⇒ `strcpy(dest, tname)`
⇒ `tname` 本身已是垃圾。追到调用点 `mui_InitFont.c:27`：

```c
zr = FindZipItemA(res_hz, (char *)DAT_002dcea4, 1, &local_11c, ze);
```

#### 二、根因（Ghidra 类型渲染陷阱）

| 事实 | 证据 |
|---|---|
| 工厂 ELF `0x002dcea4` 处**就是字符串 `"font.ttf"`** | 读该 VA 内容 = `b'font.ttf'` |
| Ghidra 把它渲染成**整数** | `globals.h:3222`：`/* @0x002dcea4 undefined4 */ extern unsigned int DAT_002dcea4;` |
| 照抄 ⇒ **多解引用一次** | 反汇编**两条连续 `ldr`**：`ldr r1,[pc,r1]`（取符号地址）→ `ldr r1,[r1]`（取**内容**）|
| 后果 | `(char *)0x746e6f66` = 垃圾指针 ⇒ `strcpy` 立刻 SIGSEGV ✓ 与崩点**逐位吻合** |

#### 三、修复

`src/compat/globals.h`：声明由整数改为**字符数组**

```c
extern char DAT_002dcea4[];   /* `.S` 已是 __f_rodata_base+0x1200 的地址别名，无需改动 */
```

**⇒ 调用点一行都不用改**；反汇编由"两条 `ldr`"变为"只有 GOT 取址" ✓（实测）。

#### 四、新增门禁 `tools/scan_rodata_int_as_ptr.py`

三条同时成立即 FAIL：① 源码出现 `(char *)DAT_xxx`；② 该符号在头文件里声明为**整数类型**；
③ **工厂 ELF** 该地址处是**可打印 ASCII 字符串**。已接入 `1to1-verify.yml` 与 `recon_local.sh`。

自检：改回 `unsigned int` ⇒ **精确报出 `DAT_002dcea4`**（退出码 1）✓；真实态 ⇒ PASS（退出码 0）✓

★ **门禁自身的假绿（本轮又踩一次）**：脚本最初用**单行**正则解析 `globals.h`，
给声明加**多行注释块**后**解析不到符号** ⇒ "通过"实为**静默漏检**；改**跨行**正则后才正确。
⇒ **凡"解析源码/头文件"的门禁，自检用例必须覆盖"注释很长/换行"的情形。**

#### 五、方法论（技能铁律 93）

**Ghidra 对"只被当地址传递的数据"缺少 `char[]` 类型信息 ⇒ 按引用宽度推断成 `undefined4`。**
· **肉眼识别**：反汇编里**两条连续 `ldr`** = 多解引用；**一条取址** = 正确。
· **修法**：声明为 `char[]`（调用点无需改）。
· **同类**：铁律 88（变参丢 `...`）、89（对象指针按元素缩放）—— 同源于
  **Ghidra 类型信息不足时给出"能编译、但语义错"的 C 代码**；
  防线 = **反汇编核对**（指令条数/立即数）+ **全量静态扫描门禁**。

#### 六、下一步

1. 盯 CI：崩点应移出 `TUnzip::Find`，观测窗口继续推进。
2. 继续对齐基线项 `TUnzip::Unzip`（516 vs 1600）、`Get`（1040 vs 1208）、`Close`（68 vs 168）
   —— 用**尺寸指纹法**（铁律 92）逐个定位"工厂删了什么"。

---

### 2026-09-16 第三十二轮：★★★★★ **根因命中** —— `file_in_zip_read_info_s` 差 24 字节（工厂删了"zip 加密"支持）

#### 一、根因（一条，统一解释此前所有观测）

| 项 | 工厂 | 我们（改前） |
|---|---|---|
| `unzOpenCurrentFile` 参数 | `(unz_s*)` **单参数** | `(unz_s*, const char *password)` |
| 该函数里 `malloc` 尺寸 | **`#108`（0x6c）** | **`#132`（0x84）** |
| `unzReadCurrentFile` | 540 B | 904 B |
| `TUnzip::Unzip` | 28 + `.part.7` 488 | 1608 B |

**差 24 字节 = `file_in_zip_read_info_s` 末尾 4 个加密字段**：

```
bool encrypted          4
unsigned long keys[3]  12
int  encheadleft        4
char crcenctest         4
─────────────────────────
                        24   ⇒ 132 − 24 = 108 ✓ = 工厂
```

**⇒ 工厂的 XUnzip 把整个「zip 加密/密码」支持删掉了**，而我们是完整版
⇒ 多出的 24 字节让 `pos_in_zipfile` / `rest_read_*` / `file` / `compression_method`
等**字段整体错位** ⇒ `unzReadCurrentFile` 用错位字段算出垃圾 seek 偏移与指针 ⇒ SIGSEGV
（与 shim 现场吻合：**访问地址 `0xffffffff`、`pc` 落在字面量池、寄存器为垃圾**）。

#### 二、字段偏移表（从工厂 Ghidra 反编译精确还原，作为重建蓝本）

```
+0x00 read_buffer            +0x3c pos_in_zipfile          +0x58 rest_read_compressed
+0x04 z_stream (56 B)        +0x40 stream_initialised      +0x5c rest_read_uncompressed
+0x24/0x28/0x2c （stream 内） +0x44 offset_local_extrafield +0x60 file
                             +0x48 size_local_extrafield   +0x64 compression_method
                             +0x4c pos_local_extrafield    +0x68 byte_before_the_zipfile
                             +0x50 crc32  +0x54 crc32_wait  = 0x6c = 108 ✓
```

（另：`unz_s` 两侧 `sizeof` 均 **128** ✓、`pfile_in_zip_read` 均在 **+0x7c** ✓ ⇒ 结构层面只差这一处。）

#### 三、修复（3 处编辑，全部在 `src/upstream/xunzip/unzip.cpp`）

1. `file_in_zip_read_info_s`：**删除** `encrypted` / `keys[3]` / `encheadleft` / `crcenctest`
2. `unzOpenCurrentFile`：**删除**密钥初始化整段（8 行：keys 赋值 + `Uupdate_keys` 循环）
3. `unzReadCurrentFile`：**删除**解密分支与加密头跳过逻辑（12 行）

#### 四、验证（本地实测）

| 项 | 改前 | 改后 | 工厂 |
|---|---|---|---|
| `malloc(sizeof(file_in_zip_read_info_s))` | `#132` | **`#108`** ✓ | `#108` |
| `unzOpenCurrentFile` size | 556 | **364** | 316（1.15×）|
| `unzReadCurrentFile` size | 904 | **656** | 540（1.21×）|
| `unzCloseCurrentFile` size | 128 | 128 | 144（1.125×）|
| 最终 ELF 复核 | — | **`mov r0, #108`** ✓ | — |
| 门禁 | — | 审计 0/0；布局 193/194；ABI PASS；dyn_audit PASS；指纹 FAIL=0 | — |

#### 五、★ 方法论（本轮新增，已写入技能铁律 92）

**`malloc(sizeof(struct))` 的立即数就是「结构体尺寸指纹」。**
在反汇编里读它，与工厂对比，能**直接发现被删/被加的字段** —— 比逐个字段猜偏移高效得多。
本轮即由此从 132 vs 108 反推出"删了 4 个加密字段"，**一举解释全部 4 项 size 差异**。
配套：Ghidra 反编译里 `__ptr[0x11] = ...` 形式的**数组索引 × 4 = 字段偏移**，
可直接还原结构体布局作为重建蓝本。

#### 六、★ CI 验证（commit `d458968b771c`）—— 行为**已推进**

| 项 | 结果 |
|---|---|
| `1to1-verify` | **success** ✓ |
| 重建侧 stdout 行数 | **34 → 36 行**（多了 2 行）|
| **崩点** | **移出 `unzOpenCurrentFile+0x170`** ⇒ 现在是 `pc -> libc.so.6 strcpy`、<br>`lr -> _ZN6TUnzip4FindEPKchPiP8ZIPENTRY + 0x24` |
| 访问地址 | `0x746e6f66` = ASCII **`"font"`** ⇒ 又一处「字符串内容被当指针」|
| 门禁 | B2 仍 FAIL（可判定前缀 19/41）；B1/B3/B4/B5/B7/B8a/B8b 全 PASS |

★ **解读**：`unz` 解压路径**已打通**（不再崩在那里）。原先被它掩盖的**下一个分歧**
（`TUnzip::Find` 内部的 `strcpy`）现在暴露出来 —— 这是**真实推进**，不是回归。

#### 七、下一个入口（第八个真实分歧）

`lr = TUnzip::Find + 0x24`，`strcpy` 的 src = `0x746e6f66`（`"font"` 内容）
⇒ `Find` 内部某处把**字符串内容当成了指针**。
工厂 `Find` 仅 **180 B**（我们 288 B）⇒ 用**尺寸指纹法**（技能铁律 92）看工厂 `Find` 少了哪一步。

#### 八、下一步

1. 用铁律 92 的尺寸指纹法对齐 `TUnzip::Find`（180 vs 288）—— 这是当前崩点所在。
2. 继续对齐基线项 `TUnzip::Unzip`（516 vs 1600）、`Get`（1040 vs 1208）、`Close`（68 vs 168）。

---

### 2026-09-16 第三十一轮：★★★ `Open` 对齐**已生效但行为未变** ⇒ 差异在 `unzOpenInternal` 内部

#### 一、已验证的事实（推送 `00ff19918fc6`）

| 项 | 结果 |
|---|---|
| `1to1-verify` | **success** ✓（新指纹门禁 + 全部旧门禁）|
| `1to1-qemu-behav` | FAIL（19/41）—— 真实分歧，**未因本轮修复而改变** |
| 改动**确实生效** | 崩溃 `pc` 从 `0x05054fa4` → **`0x05054f8c`**（代码布局变了 ⇒ 新对象被链接）|
| 本地 ELF 复核 | `TUnzip::Open` = **80 B**、`getcwd` 调用 **0** 次、`_ZL10zopenerror` @**0x3b2218**（与工厂一致，邻接 `lasterrorU`@0x3b221c、`file_info_list`@0x3b2220，**无地址冲突**）|
| 重建侧 stdout | 前 **19 行与工厂逐行一致**，第 20 行仍是分歧点（工厂 `open .../ui_cn.zip fail`，重建为 shim 日志）|
| `open driver.so fail` 那行 | **art36 里也有**（`grep -c`=1）⇒ 非新增，先前只是 `tail` 窗口不同 |

⇒ **`TUnzip::Open` 已与工厂同形，但它不是 `ui_cn.zip` 那条分歧的成因。**

#### 二、符号表精确定位：**唯一"只存在于一侧"的函数**

| 符号 | 工厂 | 重建 |
|---|---|---|
| **`unzOpenCurrentFile`** | `(unz_s*)` **316 B · 单参数** | `(unz_s*, const char*)` **556 B · 双参数** |
| `TUnzip::Unzip` | 28 B **+** `.part.7` 488 B | 1608 B |
| `TUnzip::Get` | 152 B **+** `.part.5` 888 B | 1208 B |
| `unzStringFileNameCompare` | 16 B | 140 B |
| `unzlocal_getLong` / `getShort` | 156 / 96 | 636 / 336（疑内联 `unzlocal_getByte`）|
| `unzLocateFile` / `unzClose` | 240 / 60 | 528 / 144 |
| `unzReadCurrentFile` | 540 | 904（1.67×）|
| `lufopen` / `SearchCentralDir` | 212 / 452 | 284 / 604 |
| 其余 | — | 1.3–2.0×（编译器差异范围）|

★ **除 `unzOpenCurrentFile` 外，没有任何 unz/luf 符号"只存在于一侧"** ⇒ 版本差异集中在这一个签名上。

#### 三、⚠️ 方法论限制（本轮学到，已写入技能库）

**函数 size 比值能"发现"版本不符**（57× 的 `Unzip`、签名不同的 `unzOpenCurrentFile`），
**但无法"定位行为差异"** —— `unzlocal_getLong` 156 vs 636 这类差异**同样可能只是内联造成的**。
⇒ **定位"解析行为为何不同"必须靠运行时证据（探针），不能靠 size 比值。**

#### 四、下一步（明确，按序执行）

1. **加运行时探针**（最直接、信息量最大，一轮 CI 即可定论）：
   在重建侧打印 —— `lufopen` 的 `err`、`unzlocal_SearchCentralDir` 返回值、
   `unzOpenInternal` 内的 `err` 值、`OpenZipU` 的返回值。
   ⇒ 立刻知道"我们的中央目录解析在哪一步与工厂不同"。
2. **`unzOpenCurrentFile` 改回单参数**（以 calibre 版为基，对齐签名 + 内部逻辑）。
3. 视探针结果决定是否需要**整份替换** `unzip.cpp`。

---

### 2026-09-16 第三十轮：★★★★★ 第七个真实分歧**已修复**（`TUnzip::Open` 对齐工厂）

#### 一、根因（承接第二十九轮）

工厂 `TUnzip::Open` 结尾是 **`return zopenerror;`**（`_ZL10zopenerror @0x003b2218`，已登记
`ledger/factory_globals.tsv:771`），而**我们写成了 `return ZR_OK;`** ⇒ **恒报成功**：

```
unzOpenInternal(f) 解析失败 ⇒ 内部置 zopenerror、返回 NULL
  工厂: uf=NULL 且 return zopenerror(非0) ⇒ OpenZipU 返回 0 ⇒ 打印 `open %s fail` ⇒ 优雅继续
  我们: uf=NULL 却 return ZR_OK(0)         ⇒ OpenZipU 走"成功路径" ⇒ 带着非法 uf 继续
                                            ⇒ FindZipItemA/UnzipItem ⇒ 崩在 unzOpenCurrentFile
```

**⇒ 这一行就是 `open /sdcard/cubegm//ui_cn.zip fail` 有无、以及后续崩溃与否的分水岭。**

#### 二、改动（4 处）

| 位置 | 改动 |
|---|---|
| `src/upstream/xunzip/unzip.cpp`（文件头）| 新增 `extern ZRESULT zopenerror asm("_ZL10zopenerror");` —— 用 asm 标签绑定镜像里的同名 local 符号（`factory_image.S:1904` 已有 `.globl _ZL10zopenerror / .set __f_bss_base+0xa0`）⇒ **地址天然一致且不产生重复定义** |
| `unzOpenInternal` | 入口 `zopenerror=ZR_OK`；`fin==NULL ⇒ ZR_ARGS`；`copyright 不符 ⇒ ZR_CORRUPT`；`err!=UNZ_OK ⇒ zopenerror=err`（与 calibre 版 2842/2844/2849/2883 逐处对应）|
| `TUnzip::Open` | 删除 `NOTINITED` 前置检查 / `GetCurrentDirectory`+`_tcscat` / ZIP_HANDLE 的 `GetFileType` 检查；结尾改 `return zopenerror;` |
| `tools/link_audit.sh` | ★ `XUnzip.o` 原为「**仅在 .o 缺失时**编译」⇒ 改了 `unzip.cpp` 也不重编（本轮踩到：本地改了但链接产物没变）；改为「.o 不存在 **或** 源码更新」即重编 |

#### 三、验证证据

| 项 | 结果 |
|---|---|
| `TUnzip::Open` 符号 size | **204 B → 80 B**（工厂 84 B，比值 1.05 ⇒ **已自动移出指纹门禁列表**）|
| 机器码与工厂同形 | `mov r0-r3 ⇒ bl lufopen ⇒ cmp/beq ⇒ bl unzOpenInternal ⇒ str r0,[r4] ⇒ GOT ⇒ r0=*(0x3b2218)` ✓ |
| `getcwd` 调用 | **无** ✓（工厂也没有）|
| `_ZL10zopenerror` | 在 `XUnzip.o` 里是 **UND 引用**，由 `factory_image.S` 提供地址 ✓ |
| 链接 | rc=0（17,348,944 B），审计**重复定义 0 / MISSING 0** ✓ |
| 门禁 | 指纹 FAIL=0 / KNOWN=3；布局 193/194；ABI PASS；dyn_audit PASS；变参 4/4 ✓ |

#### 四、基线纪律执行

已按纪律**删除** `_ZN6TUnzip4OpenEPvjj` 基线行；并把 `mxmlSaveFile/mxmlSaveString` 的注释更正为
「**已核实非版本问题**：mini-XML 大函数 `mxml_load_data` 5452 vs 4812（1.13×）高度吻合，差异源于
工厂走共用的 `mxml_write_string`(172 B) 而我们把逻辑内联」⇒ 保持基线但**不得据此改上游**。

#### 五、下一步

1. 盯 CI：`1to1-qemu-behav` 应出现 **`open /sdcard/cubegm//ui_cn.zip fail`（两次）**，观测窗口从 19 行继续推进。
2. 继续对齐剩余三家：`TUnzip::Unzip`（516 vs 1608）、`Get`（1040 vs 1208）、`Close`（68 vs 168）。

---

### 2026-09-16 第二十九轮：★★★★★ 第七个真实分歧定位（**上游 XUnzip 版本不符** —— 一整类新问题）

#### 一、已推送并验证（commit `ed3126454d09`）

| 项 | 结果 |
|---|---|
| `1to1-verify` | **success** ✓（上一轮「门禁放在链接之前」的顺序问题已修）|
| `1to1-qemu-behav` | FAIL —— 属**真实分歧**，非假绿 |
| 可复现前缀 | **41 行（完整）** ✓（归一化修复生效）|
| 重建侧 stdout | 已打印 `root_path:/sdcard` ⇒ **进入 `main_Menu()` 正文** |
| 两侧 exit_code | 139 vs 139（**工厂最终也崩**，崩在 `0x2b3c8` = `mui_setting`）|
| 两侧 `pre_all` | 差异**仅 rkgame 二进制本身**（3.9 MB vs 17 MB）⇒ 环境一致 ✓ |

#### 二、★ 第七个真实分歧：`TUnzip` **上游实现版本不符**

**崩点**（CI shim 现场）：`pc -> _Z18unzOpenCurrentFileP5unz_sPKc + 0x170`；
而工厂在同样位置是**优雅失败**：打印 `open /sdcard/cubegm//ui_cn.zip fail`（两次）后继续。

**逐符号指纹对比（决定性证据）**：

| 符号 | 工厂 | 重建 | 判定 |
|---|---|---|---|
| `TUnzip::Open` | **84 B** | 204 B | ✗ |
| `TUnzip::Unzip` | **28 B**（+`.part.7` 488 B）| 1608 B | ✗ |
| `TUnzip::Get` | 152 B（+`.part.5` 888 B）| 1208 B | ✗ |
| `TUnzip::Close` | 68 B | 168 B | ✗ |
| `unzOpenCurrentFile` | `(unz_s*)` **单参数** | `(unz_s*, const char*)` **双参数** | ✗ |
| `lufopen` | 212 B | 284 B | ✗ |
| `unzClose` | 60 B | 144 B | ✗ |
| `unzOpenInternal` | 476 B | 548 B | ✗ |
| **`sizeof(TUnzip)`** | **576**（`_Znwj(0x240)`）| **576** | ✓（唯一一致）|

**工厂 `lufopen` 反汇编**（0x109fc）：就是 Wischik 的 `ZIP_STD` 实现 ——
`fopen(path,"rb")` + `fseek`，`sizeof(LUFILE)=28`，**没有 `getcwd`**。

**重建 `TUnzip::Open` 反汇编**（0x05055800）：
`getcwd(this+0x13c, 260)` → `strlen` → 加 `'\'`，对应源码

```cpp
GetCurrentDirectory(MAX_PATH, rootdir);   // 我们多出来的
_tcscat(rootdir, _T("\"));
```

工厂 `TUnzip::Open`（84 B）**没有** `NOTINITED` 检查、**没有** `GetCurrentDirectory`，直接
`lufopen` → `unzOpenInternal` → 写 `this->uf`。

**工厂缺的符号**：`unzGetCurrentFileInfo` / `unzStringFileNameCompare` /
`unzGetLocalExtrafield` / `unzGetOffset` / `unzGetFilePos` / `unzGoToFilePos`
**工厂有的符号集**：`lufopen luftell lufseek lufread unzOpenInternal unzGoToNextFile
unzLocateFile unzReadCurrentFile unzCloseCurrentFile unzClose unzOpenCurrentFile unzGetGlobalComment`

#### 三、上游定版（联网核实，非臆测）

官方源 `wischik.com/lu/programmer/zip_utils_src.zip` 已下载（222,717 B，
内部文件日期 2005-09-18）⇒ **官方当前版是双参数 `unzOpenCurrentFile(file,password)`**，
**与我们一致、与工厂不同** ⇒ 工厂用的是**更早的版本**。

GitHub code-search 逐候选核对后**最接近的候选**：

| 候选 | 大小 | `unzOpenCurrentFile` | `rootdir` 成员 |
|---|---|---|---|
| Squirrel.Windows | 145 KB | 双参数 | 有 |
| OpenSceneGraph | 153 KB | 双参数 | 有 |
| DuiLib_Ultimate | 150 KB | 双参数 | 有 |
| **calibre `bypy/windows/XUnzip.cpp`** | **160 KB** | **单参数 ✓** | **有 ✓**（尺寸 576 ✓）|
| NIM_Duilib | 145 KB | 双参数 | 有 |

calibre 版 = **「XUnzip.cpp Version 1.3」（Modified by Hans Dietrich）**。
但它的 `TUnzip::Open` 仍含 `NOTINITED` + `GetCurrentDirectory` ⇒ **仍与工厂不同**。

⇒ **结论：工厂 = Hans Dietrich 1.x 系 + 厂商（Rockchip/方案商）定制**，
定制点 = **删掉 `Open` 里的目录初始化 + `EnsureDirectory` 那条解压分支**。

#### 四、因果链（闭合）

```
工厂: TUnzip::Open(简化) -> lufopen -> [失败路径] 返回非 0
      -> get_items_from_zipfile: res_hz==0 -> RARCH_LOG("open %s fail") -> 优雅继续
      -> 后续崩在 mui_setting(0x2b3c8)
重建: TUnzip::Open(含 getcwd/rootdir) -> 行为不同 -> 返回 0（成功）
      -> FindZipItemA/UnzipItem -> unzOpenCurrentFile -> SIGSEGV
```

#### 五、续接清单

1. **新增门禁 `tools/scan_upstream_fingerprint.py`**（建议）：对关键上游符号
   （`unz*` / `luf*` / `TUnzip::*`）比对**工厂 vs 重建的 size**，不一致即报警。
   ★ 这是「上游选型」的**自动回归门禁** —— 本轮若早有它，第一轮就会发现版本不符。
2. **对齐 `TUnzip`**：以 calibre 版为基，逐函数按工厂反汇编改 `Open` / `Unzip` / `Get` / `Find` / `Close`。
3. 编译后**逐符号 size 复查**，再推送（预计会牵动 `src/upstream/xunzip/unzip.cpp` 全文件）。
4. 参考物已存 `build/upstream_ref/`（**在 build/ 下，不进 push**）：
   `zip_utils_src.zip`（官方）、`calibre_unzip.cpp`、`XUnzip.h`、各候选。
5. **新增门禁 `tools/scan_upstream_fingerprint.py` 已接入 CI + `recon_local.sh`**（2026-09-16）：
   判据 = 上游符号（`unz*`/`luf*`/`TUnzip::*`/`mxml*`/`stbtt_*`/`iconv*`/`inflate*`/`xmp3_*`）
   工厂 vs 重建的 **size 比值**；`≥8×` = FAIL，`4×~8×` = WARN。
   已知未对齐项登记在 `tools/upstream_fingerprint_baseline.txt`（**修好一项必须删一行**，
   基线内容会原样打印以保持透明）。首跑结果：**FAIL=0（基线豁免 4 项）、WARN=10**；
   ★ **新信号**：`mxmlSaveFile` 34.3×、`mxmlSaveString` 22.1× —— 同样是「工厂=薄封装 vs
   重建=完整实现」模式 ⇒ **minixml 也可能版本不符，下一轮一并查**。
6. **`tools/scan_scaled_ptr_arith.py`**（本轮新增）目前是**报告型工具，未接入门禁**：
   首跑 218 条 HIGH 中大量是 `puVar = puVar + 1`（同类型指针递增，**本来就正确**）
   ⇒ 判据需收窄为「cast 目标类型 ≠ 左操作数声明类型」，收窄后再决定是否接入。

---

### 2026-09-16 第二十八轮：★★★ 第六个真实分歧定位并修复（**本轮暂停于此，待推送验证**）

> ⏸ **状态：本地已改、已编译验证，但尚未推送**（用户暂停任务）。续接入口见本节末尾「续接清单」。

#### 一、进展（CI `159b04cf8d43` 实测）

| 项 | 结果 |
|---|---|
| 重建侧 stdout | **已打印 `root_path:/sdcard`** ⇒ **成功进入 `main_Menu()` 正文** ✓（`RARCH_LOG` 变参修复奏效）|
| 可判定前缀 | 18 → **19/41**（重建侧 37 个事件）|
| 门禁 | B1/B3/B4/B5/B7/**B8a/B8b(180=180)** 全 PASS；B2 FAIL（真实分歧，符合预期）|
| `1to1-verify` | **failure** —— 但原因是**我把新门禁放在了链接之前**（那时 `build/rkgame.rebuilt.elf` 还不存在 ⇒ 脚本返回 3）|

#### 二、★ 第六个真实分歧：对象指针算术被**按元素大小缩放**

**崩点**（shim 现场）：`pc = OpenZipU + 0x2c`、调用者 `get_items_from_zipfile + 0x28`、
故障指令 `0xE7891000 = str r1, [r9, r0]`、**`r0 = 0x2be00`**（作为索引）、
访问地址 `0x050b4cd8 = r9 + 0x2be00`（`r9` = `_Znwj(0x240)` 刚申请的对象，**只有 576 字节**）。

**根因**：`TUnzip` 是 **576 字节**的类（= 申请尺寸 `0x240`）。源码写成

```c
*(gh_u4 *)(this + 0x138) = 0xffffffff;   /* this 是 TUnzip* ⇒ 0x138 × 576 = 0x2BE00 ✗ */
*(gh_u4 *)(this + 4)     = 0xffffffff;   /* 4 × 576 = 0x900 ✗ */
```

而工厂机器码是**字节偏移**：`12cfc: str ip, [r0, #312]`（= 0x138）、`12d04: stm r0, {r5, ip}`（= 0 与 4）。

**修复**：改成显式字节算术 `*(gh_u4 *)((char *)this + 0x138)` / `((char *)this + 4)`。
**修后机器码实测**：`str r9, [r0, #312]` ✓ 与工厂一致。

**影响**：`ui_cn.zip` 读取路径越界 180 KB 直接 SIGSEGV；而工厂在同一位置是**优雅失败**
（`OpenZipU` 返回 0 → 打印 `open …／ui_cn.zip fail!` 并继续）⇒ 修完后重建侧应能打印那两行、
并像工厂一样在 `mui_setting` 处 NULL 解引用（**届时行为差分有望首次全等 PASS**）。

**同类普查**：`TUnzip/XUnzip` 5 个文件里已无其它 `对象指针 + 常量` 写法 ✓。

#### 三、本轮已推送的（`159b04cf8d43`）

1. **`RARCH_LOG` 变参修复**（第五个真实分歧，详见第二十七轮）+ `proto.h` 真原型
   + 幂等补丁 `tools/patch_proto_varargs.py`（接入 `gen_compat_all.sh`）
2. **新门禁 `tools/scan_varargs_fns.py`**（工厂 `push {r0,r1,r2,r3}` ⇒ 4 个变参函数；
   本地首跑精确命中 `RARCH_LOG`，修后 4/4 PASS）
3. **修掉我自己的门禁假绿**：`norm()` 未折叠空白 ⇒ 前缀塌到 6 行 ⇒ trivial PASS；
   已加空白折叠 + shim 全部 hex 加 `0x` + `behav_diff.py` **前缀长度护栏**
4. 3 处 `RARCH_LOG(&DAT_xxx)` ⇒ 去掉 `&`（真原型暴露出的类型不符）

#### 四、⏸ 续接清单（下次开始按序执行）

1. **本地复跑**：`CC="$ZIG cc" sh tools/recon_local.sh report/local_recon_build.txt`
   → 期望 宽松/严格 **213/213**、假绿 0、INFRA 0、数组转型 PASS、**变参门禁 4/4 PASS**；
   再跑 `link_audit.sh` + `build_upstream.sh` + `link_full.sh` + 四个门禁
   （布局 / ABI / dyn_audit / scan_varargs_fns）。
2. **推送**（增量，预计 2 个 blob）：`src/proprietary/misc/FUN_00012cd0_OpenZipU.c`
   + `.github/workflows/1to1-verify.yml`（已把变参门禁移到 P3 完整链接**之后**）。
3. **盯 CI**：`1to1-verify` 应转 success（顺序已修）；`1to1-qemu-behav` 看前缀能否再推进
   （预期 19 → 22，甚至 **41/41 全等 PASS**）。
4. **若仍有分歧**：直接读制品里 `rundir_rebuild/stderr.txt` 的 `★ 真崩溃` 段
   （已带 `pc`/`lr` 归属 + **栈回溯**，`dladdr` 弱引用解析；不需要 gdb）。

---

### 2026-09-16 第二十七轮：★★★★★ 第五个真实分歧 —— Ghidra 把**变参函数**渲染成单参数（一整类陷阱）

#### 一、定位链（全部有运行时证据）

| 步骤 | 证据 | 结论 |
|---|---|---|
| ① 门禁假绿被自己抓到 | `可复现前缀 = 6 行`（应 41）| 见下一节；修完后该轮 CI 正确报 `FAIL（18/41）`|
| ② `dladdr` 探针点名 | `pc -> libc.so.6+0x6b1ee 符号=strlen`；**`lr` 也在 libc 内**（`+0x488f7`）| 不是游戏代码直调，是 **libc 内部**调用 |
| ③ 栈回溯 | `[sp+4] = libc + 0x11ed50  _IO_2_1_stdout_` | 现场与 **stdout** 相关 ⇒ printf 族 |
| ④ 寄存器 | `r0=0x6364732f`（`"/sdc"` 的内容）、`r1=r0 & ~7`、`r4=7`（对齐掩码）| `strlen(<字符串内容>)` |
| ⑤ 反查调用者 | 读 `RARCH_LOG` 的重建产物：`push {fp,lr}` / `pop {fp,lr}` / **`b RARCH_LOG_V`** | 纯尾调用，**只传了 r0** |
| ⑥ 对照工厂 | `9ed8: push {r0,r1,r2,r3}` / `add r1,sp,#20` / `ldr r0,[sp,#16]` / `bl RARCH_LOG_V` | 工厂是**真变参**，传 `(fmt, va_list)` **两个**参数 |

**因果链闭合**：`RARCH_LOG` 丢 `...` ⇒ `RARCH_LOG_V(char*, va_list)` 的第二个参数（`va_list`）
**成了调用者的 r1 残留值**；而 `main_Menu()` 里 `RARCH_LOG("root_path:%s
", root_path)` 调用时
`r1 = root_path(0x3e1398)` ⇒ `vfprintf(stdout, fmt, ap=0x3e1398)` 把**字符串自己的内存**当参数列表
⇒ `%s` 取到的"指针" = `0x6364732f` = `"/sdc"` 的内容 ⇒ 崩在 libc `strlen`。
**与实测寄存器逐位吻合。**

#### 二、修复

`src/proprietary/misc/FUN_00009ed8_RARCH_LOG.c` 按原厂指令证据还原为真变参：

```c
void RARCH_LOG(char *param_1, ...)
{
  __gnuc_va_list ap;
  __builtin_va_start(ap, param_1);
  RARCH_LOG_V(param_1, ap);
  __builtin_va_end(ap);
  return;
}
```

**修后产物**：`stm ip, {r1,r2,r3}`（变参保存区）+ `add r1, fp, #8`（va_list）+ `bl RARCH_LOG_V` ✓ 与工厂同语义。

★ 附带一处 C 语言硬约束：`proto.h` 里 Ghidra 生成的 K&R 空声明
`extern void RARCH_LOG();` **与可变参原型不兼容**（C11 6.7.6.3p15 禁止空声明配 `...`），
clang 直接报 `error: conflicting types`。⇒ 新增幂等补丁 `tools/patch_proto_varargs.py`
（已接入 `gen_compat_all.sh`，成为第 5/6 步）。

#### 三、★ 新增门禁 `tools/scan_varargs_fns.py`（把这一整类陷阱变成静态可拦）

- **工厂侧判据**：变参函数的 AAPCS32 序言是 `push {r0, r1, r2, r3}`（`0xE92D000F`）——
  全 `.text` 扫该 opcode，命中 **4 处**：`RARCH_LOG` / `spi_printf` / `mxml_error` / `_mxml_strdupf`。
- **重建侧判据**：**不能**要求同一 opcode（LLVM 用 `sub sp,#12` + `stm rX,{r1,r2,r3}`）⇒
  改为要求「函数序言区（前 64 B）里存在把 `{r1,r2,r3}` 一起存出去的 `stm`/`push`」。
- **首跑结果**：精确命中 **只有 `RARCH_LOG` 违规**（其余 3 个已是正确变参，零误报）✓
- **修后**：4/4 保真 ⇒ 门禁 PASS。

★ 顺带证实：`spi_printf` 此前已按原形还原（其源码里就有同一条证据注释），**`RARCH_LOG` 被漏掉**——
  说明"逐个靠人记"不可靠，必须机器扫。

#### 四、门禁全景（本地全绿）
#### 八、★★★★★ 抓到并修掉一次**我自己的门禁假绿**（归一化未折叠空白 ⇒ 前缀塌陷 ⇒ trivial PASS）

**现象**：`22d4cdc1` 那一轮 `1to1-qemu-behav` 报了 **success / 门禁 PASS**，但差分报告里写着：

```
参考侧 41 行 / 控制侧 41 行；**可复现前缀 = 6 行**
  ⚠ 参考侧 #7 : O|MemFree:         N kB
     控制侧 #7 : O|MemFree:        N kB      ← ★ 空格数不同
```

⇒ **可判定前缀只有 6 行**，而两侧真正的分歧在第 18 行 ⇒ 门禁只判了前 6 行 ⇒ **假绿**（最危险的一类）。

**根因（两处，都在我自己这边）**：

1. **采集端归一化没有折叠空白**：`norm()` 只把 `[0-9]{3,}` 换成 `N`，
   而 `/proc/meminfo` 的 `MemFree:` 是**右对齐**的 —— 数值位数一变（如 `999888` → `11252736`），
   冒号后的**空格数**就变 ⇒ 参考实现"自身两遍不一致" ⇒ 确定性前缀从 41 行塌到 6 行。
2. **我新加的 shim 现场打印用了裸十六进制**（`%08lx`，无 `0x`）⇒ 归一化的 `0x[0-9a-f]{2,}` 规则
   匹配不到 ⇒ 地址不被归一 ⇒ 又一处"参考实现自身不确定"的来源。

**修法**：

| 位置 | 修改 |
|---|---|
| `behav_capture.sh` 的 `norm()` | 增加 `s/[[:space:]]\{1,\}/ /g` + 去行首尾空白（**必须折叠空白**）|
| `fake_mem.c` | 所有 hex 打印统一加 `0x` 前缀（12 处；`%p` 本就带 `0x`，故不加 `0x%p`）|
| `behav_diff.py` | 新增**前缀长度护栏**：`可复现前缀 < 参考侧事件数 × 60%` ⇒ **INCONCLUSIVE(3)**，并打印成因提示 |

**单元测试**：
- 归一化：三行不同位数的 `MemFree:` ⇒ 去重后 **1 行** ✓；新格式的崩溃现场行 ⇒ 全部地址变 `ADDR` ✓。
- 护栏：前缀 6/41 ⇒ **INCONCLUSIVE**；前缀 180/180 ⇒ PASS ✓。

★ 教训：**"归一化"本身就是门禁的一部分** —— 它少折叠一类可变性（空白/对齐/裸地址），
  就会把"参考实现自身的不确定"变成"前缀塌陷"，从而**反向**把门禁变成永远通过。
  这类假绿比普通假绿更隐蔽：报告里数字都"正常"（41 行都对上了），只有**前缀长度**这一个数字暴露了它。

#### 九、★ `dladdr` 探针实测点名（commit `93fd9e6a`）

```
[shim] ★ 真崩溃 @63647328 不在设备页 (base=(nil)) pc=3fe3b1ee lr=3fe188f7 sp=40ffec70
        r0=6364732f r1=63647328 r2=003e139c r3=00000001 r4=00000007 ...
[shim]   pc 归属: /arm-root/lib/arm-linux-gnueabihf/libc.so.6 + 0x6b1ee   符号=strlen
[shim]   故障指令 @pc = 2300e9d1
```

| 侧 | pc 归属 | 故障指令 | 判读 |
|---|---|---|---|
| **重建** | **`libc.so.6 + 0x6b1ee` 符号 = `strlen`** | `0xE9D12300`（ldrd，`r1 = r0 & ~7`，`r4 = 7` 为对齐掩码）| **`strlen(0x6364732f)`** —— 即 `strlen("/sdc" 的**内容**)` |
| 工厂 | `rkgame + 0x233c8`（= `0x2b3c8 - 0x8000`，与首个 LOAD 从 `0x8000` 起吻合）= **`mui_setting`** | `0xE1D300B4`（`ldrh r0,[r3]`，r3=0）= **NULL 解引用** | 与 exec 轨迹末行 `mui_setting` 一致 |

★ 两处副产品（都已核实）：
1. 重建侧游戏代码里**所有** `strlen` 调用都指向 **`compiler_rt.strlen`**（zig 内建，在**我们自己的二进制**内，
   地址 `0x50570a0`）；工厂则是 `strlen@plt`。⇒ 崩溃的 libc `strlen` **不是**游戏代码直接调的，
   而是**由某个库函数内部调用**（`lr` 落在库地址也印证这一点）。
2. 两侧 exec 轨迹的**最后 16 条完全相同**（仅库基址差 `0x200000`），**唯一分歧**在最后一步：
   同一条 PLT 解析器之后，工厂跳到 `mui_setting`（游戏代码），重建跳到 `libc strlen`。

⇒ 下一步（已就位，待下一轮 CI）：把 shim 的现场升级为 **`lr` 归属 + 栈回溯**（弱 `dladdr` 逐帧解析，
不需要 gdb、真崩溃时依旧拿得到），直接点名"是哪个库函数以 `strlen` 处理了 `root_path` 的内容"。

#### 九、门禁全景（本地全绿）

1. **`bt_probe` 停在「有意的设备缺页」上**：假硬件让 guest 频繁缺页（设备寄存器访问就是靠缺页拦下来的），
   gdb 不忽略就会停在**正常被处理**的那一次，产出误导现场 ——
   实测它报「崩在 `sfc_init` 的 `ldrh r1,[r0,#44]`」，而那只是一次普通设备读。
   ⇒ 加 `handle SIGSEGV/SIGBUS nostop noprint pass`（与帧探针一致）。
   ★ 但真崩溃时 shim 已把 SIGSEGV 恢复成 `SIG_DFL`，信号穿透到进程 ⇒ gdb 拿不到调用栈，
     因此**真崩溃现场改由 shim 自己打印**（下一条）。
2. **shim 在「非设备缺页」时打印完整现场**：新增
   `★ 真崩溃 @<addr> 不在设备页 (base=…) pc=… lr=… sp=…` + `r0..r7`。
   理由：真崩溃时 pc 常落在 ld.so/PLT 解析器里（调用点信息已丢），只有 `lr`（=调用者）与基址寄存器
   才能直接指出「哪条指令、用哪个基址寄存器、被谁调用」。比叫 gdb 更可靠、且零额外成本。

#### 七、门禁全景（本地全绿）

```
宽松 213/213   严格 213/213   假绿 0   INFRA 0        ← 含本轮新增的三态判定
审计 重复定义 0 / MISSING 0 / upstream 0
布局 PASS 193/194 = 99.5%     ABI PASS     dyn_audit PASS (FAIL 0)
数组转型门禁 PASS（761 声明 / 213 文件）
```

---
### 2026-09-16 第二十五轮：★ 编译门禁改三态判定（消除「把环境故障误判成类型错误」）

**触发**：上一轮报告出现「严格 212/213、**假绿 1**」（前 5 轮都是 213/213、假绿 0），点名
`src/proprietary/core/FUN_000226a8_filelist_run_game.c`，且该行 `serr` **为空**。

#### 一、复跑定性：不是源码错误

以**完全相同的严格命令行**连续编译该文件 3 次 ⇒ `rc=0` **三次全过**；stderr 里 `error:` 出现 **0** 次
（只有 7 条 warning + 2 条 note：`NAN` 宏重定义、`main` 返回类型、`-Wpointer-sign`）；该文件最后修改日期 Sep 12。

★ 顺带观察到一个有用现象：**首次运行 stderr 非空（3547 B，缓存预热/编译 `compiler_rt` 的 warning）、之后两次为空** ——
这解释了该文件在报告的严格阶段 `serr` 为空的形态（只是时机不同）。

⇒ **定性**：那次 `rc≠0` 是**工具链/环境瞬时故障**（zig 在内存压力下可非 0 退出且 stderr 为空），
却被记成「类型错被 warning 掩盖」的假绿，**污染了门禁结论**。

#### 二、修法：双轨判定由二态改为三态（`recon_local.sh` + `recon_build.sh` 同步）

| 条件 | 归类 | 处理 |
|---|---|---|
| `rc=0` | 通过 | 计入 ok |
| `rc≠0` 且 stderr **含** `error:` | **真源码错误** | 宽松失败 / 严格假绿 |
| `rc≠0` 且 stderr **不含** `error:` | **INFRA 未判定** | `sleep 2` **重试一次**；仍如此则单独计数，**既不算通过也不算类型错**，末尾 **exit 3** 显式失败 |

★ 判据刻意用「**有没有 `error:`**」而不是「stderr 是否为空」：编译器可能只吐 warning 然后因环境原因失败，
那时 stderr 非空但依然不是源码错误。

#### 三、五用例单元测试（假编译器注入故障，秒级）

| 用例 | 注入 | 断言 | 实测 |
|---|---|---|---|
| A 全成功 | 全 `rc=0` | 213/213、假绿 0、INFRA 0、exit 0 | ✓ |
| B 宽松侧空 stderr | 单文件 `rc=1` 无输出 | **失败数 0**（不再误计）、INFRA 1、exit 3 | ✓ |
| C 严格侧空 stderr | 仅严格口径 `rc=1` 无输出 | **假绿 0**、INFRA 1、exit 3 | ✓ ← **正是真实那一例** |
| D 空 stderr 后自愈 | 首败、重试成功 | 213/213、exit 0 | ✓ |
| E 含 `error:` | 单文件 `rc=1` 且打印 error | 宽松失败 1、**不误判为 INFRA** | ✓ |

**顺带修的隐患**：`recon_local.sh` 在 `set -u` 下使用了未定义的 `$PY`（尾部静态门禁要调它），
此前依赖外部 `export PY` 才跑得通 ⇒ 已补 `PY="${PY:-python}"`（**脚本要能独立跑，不靠调用方环境**）。

#### 四、真实本地复跑（全绿）

```
宽松口径 213/213  严格口径 213/213  假绿 0  INFRA 0  exit 0
审计 重复定义 0 / MISSING 0 / upstream 0      链接 rc=0
布局 PASS 全局 193/194 = 99.5%   ABI PASS   dyn_audit PASS (FAIL 0 / WARN 1)
数组转型门禁 PASS（761 个数组声明 / 213 个受检文件）
```

---

### 2026-09-16 第二十四轮：★ 修掉 `spi_id[0]` 误渲染（Ghidra 的「指针→窄整数」陷阱）

**来源**：第二十三轮 CI 的 shim 日志显示**两侧发出的 flash 命令不同** —— 这正是深窗口暴露的**第二个真实语义分歧**。

| 侧 | 命令序列 |
|---|---|
| 工厂 | `op=009f addr=0 len=3` → `op=485a addr=0x194 len=16` → `op=4848 addr=0x100` → `op=4848 addr=0x000` |
| 重建（修复前）| 缺少让原厂选择 0x0b 分支的那次判断结果不同 ⇒ 后续流程与窗口深度不一致 |

**根因**：原厂是 `if (spi_id[0] == 0xb)`（反汇编 `ldrb r3,[r6]`，`r6 = &spi_id`），
而 Ghidra 把它渲染成 **`(gh_byte)spi_id`** —— 在「`spi_id` 是数组」的声明下，这变成**指针→字节的转换**
（取地址最低字节 `0xc8`），于是两处判断全部走错分支。这是 P5 深窗口抓到的**第二个真实语义分歧**。

**修复（2 文件 5 处）**：

| 文件 | 处数 | 变更 |
|---|---|---|
| `src/proprietary/flash/FUN_002c4044_spi_driver_init.c` | 2 | `(gh_byte)spi_id` → `spi_id[0]`（并补上「为什么」的注释）|
| `src/proprietary/flash/FUN_0000ac44_UpdateROM.c` | 3 | `(char)spi_id` → `spi_id[0]` |

#### 新增静态门禁 `tools/scan_array_casts.py`

扫描 `src/**/*.c` 里「**数组名被转型成窄整数**」的形状（`(gh_byte)ARR` / `(char)ARR` / `(gh_u2)ARR` …），
与 `globals.h` 的数组声明表交叉比对。该类错误**编译/链接/ABI/布局门禁全绿**，只有行为差分或静态扫描能发现。
已接入 `1to1-verify`（`1to1/` 下调用）与 `recon_local.sh`。

★ 门禁第一版就出**假阳性**：报「命中 1 处」—— 结果是我自己写在源码里的**解释性注释**正好引用了
`(gh_byte)spi_id` 这个错误写法。已加 `strip_comments()`（保留字符串字面量），并做**双向测试**：
注入错误写法 ⇒ **exit 2 且命中代码行**；恢复 ⇒ **exit 0**。

---
### 2026-09-15 第二十三轮：★★★★ SFC 做成「有状态设备」→ 观测窗口 20 → 22 行，**首次进入 main_Menu()**

**里程碑**：`spi_driver_init()` 的 24 字节 flash 校验和**通过**（返回 1）⇒ `main()` 走 else 分支 ⇒
`UpdateROM()` → `sfc_uninit()` → `ShareMemCreat()` → `main_Menu()`（菜单 = 重建量最大的一块）。

| 行 | 内容 | 含义 |
|---|---|---|
| 18 | `ROM Size:01000000 CRC32:0000 Update time:1980-0-0 0:0:0` | 假 flash 的芯片 ID 让原厂走 0x0b 分支（FlashSize=16 MB）|
| 19 | `Load /sdcard/cubegm/update/firmware.upk fail!` | **UpdateROM 被调用**（= 校验和通过）|
| 20 | `root_path:/sdcard` | **main_Menu() 已进入** |
| 21-22 | `open /sdcard/cubegm//ui_cn.zip fail` ×2 | 下一处缺口 = UI 资源包（本轮已补齐，下轮见分晓）|

#### 为什么只能做「设备仿真」

读循环是 `*dst++ = g_sfc_reg[0x42]` —— **同一个寄存器地址反复读**。静态内存页每次都返回同一个字 ⇒
缓冲区内容必然 4 字节周期；而密钥表 KY（工厂 `.rodata` @0x002dee30 = `aXDT8kluSPu6PvHIV2JhA1V4`）
**不是** 4 字节周期（KY[8]=0x53 vs KY[12]=0x50）⇒ **数学上不可能通过**（此前已用「766 KiB 栈投毒」
反证那两个值不是随机栈垃圾，而是被写过的确定性内存）。

#### 做法（`tools/guest_shim/fake_mem.c` ③ 段，约 300 行）

`mprotect(PROT_NONE)` 保护寄存器页 + `SA_SIGINFO` 处理器：解码缺页的那条访存指令 → 按**设备语义**应答 →
`pc += 4`。设备语义：忙标志恒 0；状态寄存器（含 `ldrh/ldrb [r0,#0x22]` 这种**上半字/单字节**读）= 可读字数<<16；
数据寄存器 = FIFO 下一字（逐字变化）；写 `0x100`（低 16 位 opcode、位 16..29 字节数）复位 FIFO、写 `0x104` = 地址。
「flash 里有什么」按 (opcode, addr) 决定，其中 `0x4848`@0x000 的 256 字节是**按校验和方程反解**出来的
（`buf[0xc0..0xd7]=0`、`k<8` 取 0、`k=8..23` 取 `KY[k]^buf[k-8]`），全部由 KY 现算。

★ 处理器发现缺址**不在设备页**时恢复 `SIG_DFL` 再 return ⇒ 非设备错误照旧崩，语义不变。
★ 回退开关 `CGM_SFC_MODE=seed` 可退回旧的静态种子页行为。

#### 推 CI 之前的零成本验证（本地全做完）

1. **解码器交叉验证**：`objdump -d` 反汇编文本 + 一份 Python 逻辑镜像，逐条比对「读/写、Rd、size」——
   `sfc_request` 上 **37 条（重建）+ 51 条（原厂）访存指令、0 异常**。靠它把半字尺寸判据从 bit6 改成 bit5。
2. **设备 + 校验和数值模拟**：Python 复现整条读取序列与校验和循环 ⇒ 失配 0 字节 ⇒ 返回 1。
3. `zig cc -c` 编译自检通过。

#### CI 实测证据（shim 自己打在 stderr 上）

```
[shim] SFC 设备仿真已装配 base=0x3fb64000 len=0x1000
[shim] sfc cmd op=009f addr=000000 len=3   -> payload=flash(4 B)
[shim] sfc cmd op=485a addr=000194 len=16  -> payload=flash(16 B)
[shim] sfc cmd op=4848 addr=000100 len=256 -> payload=zeros(0 B)
[shim] sfc cmd op=4848 addr=000000 len=256 -> payload=flash(256 B)   <- 反解数据
[shim] SFC 设备撤防（munmap）：faults=180 cmds=4 unhandled=0
```

#### 同轮修掉的两个「外围」问题（都是深窗口带来的新风险）

1. **`-d exec` 轨迹日志无上限**：观测窗口一深，guest 可能长时间运行 ⇒ 日志涨到 GB 级**写满 runner 磁盘**
   （本轮为此外**提前取消**了一整轮 CI，避免污染仓库预算）。⇒ 加**大小看门狗**（超过 128 MiB 杀 guest）
   + `EXEC_TIMEOUT` 300→90 s；给采集落盘的 stdout/stderr 加 20000 行上限（`events` 本来就有 400/200 上限）。
2. **gdb 默认在 SIGSEGV 上停止**：假硬件让 guest 频繁缺页，帧探针的「第一次停下」于是变成设备缺页而不是
   函数入口 ⇒ 量到无意义的 `fp-sp=0x18` ⇒ 帧门禁**假红**，整轮连 `behav_diff.txt` 都没生成。
   ⇒ ① gdb 命令加 `handle SIGSEGV nostop noprint pass`（+SIGBUS）；② **把帧门禁挪到差分之后** ——
   差分是主门禁，绝不能因为次级探针出问题而拿不到差分结论。

#### 环境补齐（`golden/sdcard_min/`，全部取自原厂 SD 只读拷贝）

`font.ttf`(1.84 MB)、`cores/filelist.xml`(8.7 KB)、`ui_cn.zip`(5.0 MB)、`chord.wav`/`Button1.wav`(各 7.7 KB)、
`Back_In_The_City.mp3`(1.66 MB) —— 两侧加载同一份 ⇒ 差分仍公平。

---
### 2026-09-15 第二十二轮：★★★★★ 行为差分**全等**（22/22 事件）+ 定位并修掉「callee 写坏调用者 fp」

**里程碑**：`1to1-qemu-behav` 首次 **success**，且**不是前缀一致，而是整段全等**：

```
参考端 factory: exit=139  stdout=20 行  stderr=3 行
重建端 rebuild: exit=139  stdout=20 行  stderr=3 行
[PASS] B1 exit_code 139 vs 139        [PASS] B2 events 可判定前缀 22/22（重建侧共 22 行）
[PASS] B3/B4 新增与变更文件 0 vs 0     [PASS] B5 menu.log sha 一致
确定性控制：参考侧 22 行 / 控制侧 22 行 ⇒ 可复现前缀 = 全段
门禁结果: PASS（0 项失败）   三个 workflow 全部 success
```

两侧 stdout **逐行相同**（仅 MemFree/MemAvailable/Buffers 随运行波动，已被归一化），
含此前一直缺失的两行 `find sound_driver_deinit process fail` / `find video_driver_deinit process fail`，
终止状态也一致：双方都在 `DeinitDisplay` 的 **`dlclose(NULL)`** 里 SIGSEGV（工厂侧 si_addr=0x19b）✓。

#### 一、定位过程（都是可复现的运行时证据，不是猜）

| 步骤 | 手段 | 得到的结论 |
|---|---|---|
| ① | `-d exec`（记录**每个被执行**的翻译块，含已缓存块） | 最后一个被执行块 = `spi_driver_init` 的 `sub sp,fp,#28`+`pop {…,pc}`，之后**再无任何块** ⇒ 是 `pop` 取到坏地址跳飞（不是坏访存）|
| ② | qemu gdbstub + `gdb-multiarch` 取崩溃现场 | `pc=0xf2280500`（不可映射）、**`sp=0x40fff212` 未 4 字节对齐**、`handle=0` ⇒ 排除「dlsym 句柄为垃圾」|
| ③ | shim 里加 `munmap` 探针（顺带读 guest 的 `handle`） | 重建侧**完全没有** `munmap(…,0x400)` 行 ⇒ 崩溃发生在 `sfc_uninit` **之前**（进程从未回到 main）|
| ④ | gdb 断点：入口 / prologue 后 / 两次调用返回点 / epilogue | 入口 `fp=0x40fff210` → prologue 后 **`fp=0x40fff208` ✓** → 首次 `sflash_read_security_data` 返回后 **`fp=0x40fff20a` ✗（+2）**；保存的 lr 槽**完好** |
| ⑤ | 指令级扫描两个 callee 里所有写 r11 的指令 | 只有标准 prologue/epilogue ⇒ 破坏来自**数据写**而非寄存器写 |

#### 二、根因（逐位吻合）

`sfc_request(param_1, …)` 里有一句：

```c
uVar2 = param_1[1] | 2;   param_1[1] = uVar2;    /* 设置「命令行第 2 个字」的 bit1 */
```

而 `sflash_read_security_data` 原是**两个独立标量** `local_10` / `local_c`，并传 `&local_10`。
工厂原版是帧内**连续 8 字节的 2 字命令行**（`str lr,[sp]` + `str lr,[sp,#4]` ⇒ `cmd[0]=0x4848, cmd[1]=0`，`&cmd = sp`）。
我们把两个标量交给编译器排布 ⇒ LLVM 排成「`local_10` 在高、`local_c` 在低」⇒ `&local_10 + 4` **越出这两个标量**，
正好命中 `sflash` 帧里紧邻的**保存的 fp 槽**（内容 = 调用者的 `fp` = `0x40fff208`）⇒ `| 2` ⇒ **`0x40fff20a`** ✓（与实测完全一致）。
该值随 `pop {fp,pc}` 回传给 `spi_driver_init` 的 r11 ⇒ 它的 epilogue `sub sp,fp,#28` 帧基址偏 2 字节 ⇒
`pop {…,pc}` 按错位读栈，把「保存 lr 的高半字 + 下一字」拼成 `0xf2280500` ⇒ 跳飞 ✓✓。

#### 三、修复（同一模式 8 处，全部改成 2 字数组）

`gh_u4 cmd[2]`，`cmd[0]=<命令>`、`cmd[1]=<参数>`，传 `cmd`：
`sflash_read_security_data` / `snor_write_en` / `spi_read` / `spi_write` /
`sflash_write_security_data` / `sflash_erase_security_data` / `erase_sector` / `spi_driver_init`。
修后 `sflash` 的代码生成与工厂**结构一致**（`cmd[0]`@sp+0、`cmd[1]`@sp+4、`&cmd=sp`、帧 8B）✓。

#### 四、把这次踩的坑变成**永久门禁**（静态门禁全都拦不住它）

- **帧不变式门禁**（`ci_qemu_behav.sh` 的帧探针，现已接成**硬失败**）：用 qemu gdbstub 在目标函数的
  入口与 epilogue 各停一次，要求 **`fp - 帧基址 == 0x128`**（与 `sub sp,fp,#28` + 9 寄存器 push 自洽）。
  实测越界 bug 会把该值变成 `0x12a` ⇒ 立刻红灯。
- **断点地址动态化**：新增 `tools/find_func_marks.py`（从当前 ELF 现算入口与 epilogue），
  避免硬编码地址随重链接漂移、把探针变成无意义输出。
- 该门禁**不需要**任何静态符号信息即可捕获「callee 破坏调用者 fp」这一整类缺陷。

#### 五、当前整体状态

| 门禁 | 结果 |
|---|---|
| 宽松/严格编译 | 213/213 = 100%（假绿 0）|
| 符号审计 | 重复定义 0 / MISSING 0 / upstream 0 |
| ABI | PASS（e_flags=0x5000400、interp=/lib/ld-linux-armhf.so.3、GLIBC 上限 2.7 = 工厂）|
| 布局 | PASS（全局符号 193/194 = 99.5%）|
| 动态段/初始化链 | PASS（DT_INIT 真实、ABS0 = 0）|
| **行为差分** | **PASS（22/22 全等，含终止状态）** |

**下一步**：① 继续把观测窗口推深（当前窗口止于 `dlclose(NULL)`；若要覆盖 `main_Menu()` 需要 fake `driver.so`
导出 `video/sound_driver_init` 等符号，或让 `dlopen` 成功）；② P5 做「多场景差分」（不同 `setting.xml`/`autorunfile`
分支）；③ P6 真机验收（SD 部署 + 设备自写 `menu.log`）。

---
### 2026-09-15 第二十一轮：★★★ 假硬件 shim 把观测窗口推深（13 → 20 行）+ 确定性控制组 + 门禁假 PASS 修补

**目标**：让 qemu 下的可观测窗口不再停在最浅处（此前两侧都停在 `Failed to initialize GPIO` 之间的
NULL 寄存器写，只有 13 行输出，"等价"没有说服力）。

#### 一、假硬件 shim（`tools/guest_shim/fake_mem.c`，两侧同一份 ⇒ 差分仍公平）

| 措施 | 内容 | 效果 |
|---|---|---|
| ① 设备节点重定向 | `open/open64/openat` 把 `/dev/mem`、`/dev/fb`、`/dev/dri`、`/dev/input`、`/dev/sunxi`… 重定向到 `/dev/zero` | `open("/dev/mem")` 成功 ⇒ `sunxi_gpio_init()` 走完 5 次 mmap |
| ② 物理寄存器映射 | `mmap(MAP_SHARED+可写+偏移≥4MiB)` → 匿名零页 | 寄存器读回 0、写入被丢弃；两侧一致 |
| ③ 栈投毒 | constructor 用**递归帧**（24 × 4 KiB）把栈填 `0xA5` | 让"未初始化读"可复现（见第四节：实现方式踩过坑） |

★ 只拦 `mmap` 是不够的 —— `open("/dev/mem")` 先失败，`mmap` 根本走不到（实测踩到）。
★ shim 必须用 qemu 的 `-E LD_PRELOAD=…` 注入 **guest**；**不能** export 到宿主环境
（qemu-arm-static 是 x86_64 宿主程序，宿主 ld.so 见到 armhf 的 .so 会直接崩：实测两侧 exit=129、零输出）。

**效果（CI 实测，commit `aea8b7b4` / `89dc7b6d`）**：

| 指标 | 之前 | 之后 |
|---|---|---|
| 参考侧 stdout | 13 行 | **20 行** |
| 等价区间 | 到 `Failed to initialize GPIO` | 到 **`RF_IC Test Fail !`**（穿过 GPIO→SPI→SFC 闪存探测） |
| 新增可见事件 | — | `CRU_CLKGATE8_CON:0` / `CRU_CLKGATE8_CON:e000000` / `GRF_GPIO0A_IOMUX:0` / `GRF_GPIO2A_IOMUX:C00000` |

另修复**环境缺陷**：`golden/sdcard_min/` 补入真机 `driver.so`（39,844 B，两侧同一份）——
此前它缺失导致 `dlopen` 失败并跳过图形初始化（`open driver.so fail, libkms.so.1: …`）。
★ 该文件不在 `push_1to1.py` 的 walk 目录内（`golden/` 走显式清单），漏加会**静默不推送**；
而 MANIFEST 已引用它 ⇒ CI 铺设会失败。已补清单项。

#### 二、★ 新增「确定性控制组」（`behav_diff.py` 的 B0c）

用**同一份参考二进制再跑一遍**（`CGM_CONTROL=1`，默认开），取
`k = events(factory) 与 events(control) 的最长公共前缀`：

- 前 k 行 = 参考实现**自身可复现**的部分 ⇒ 门禁只判这一段：
  `rebuild[:k] == factory[:k]` **且** `len(rebuild) >= k`；
- 第 k+1 行起 = 参考实现自己都不稳定的部分 ⇒ **不计为失败**，但会在报告里单列并标注"环境受限"；
- 对照组必须与参考侧是**同一份二进制**（sha 相同），否则 P0d FAIL。

**决定性证据**：本次 CI 中参考侧两遍**完全一致（20/20 行）** ⇒ `k = 20` ⇒
**该分歧不是不确定，而是真实、可复现的实现差异**（重建侧 18 行，在可判定区间内提前终止）。

#### 三、★★ 修补我自己的门禁「假 PASS」（由栈投毒的副作用暴露）

第一版栈投毒写成「取 SP 减大偏移再写」（**错**）：qemu-user 下该地址未映射 ⇒ guest 启动即 SIGSEGV。
后果：两侧 stdout 均为 **0 行**，events 只剩 qemu 自己的 `uncaught target signal 11` 一行，
而 B0c 的"确定性前缀=1"把它判成 **PASS** ⇒ 假通过。

两处收紧（均已双向单元测试）：

1. **B0 改用「真正的行为观测」**：`stdout_lines > 0` 或 有新增/变更文件；
   不再用 `observed`（它把 **stderr** 也算进去，而 qemu 自身报错就是一行 stderr）。
2. **可复现前缀必须包含 stdout 事件**：否则判 **INCONCLUSIVE(3)**，理由是"前缀已退化为启动即崩的噪声行"。
3. 栈投毒改为**递归帧**实现（每层 4 KiB × 24 层，走正常栈增长），不再做危险指针算术。

#### 四、当前进度与下一步

**仍剩 1 项 FAIL（真实、可复现）**，位于 `spi_driver_init()` 打印 ROM 信息处：

```
factory: ROM Size:00000000 CRC32:0000 Update time:2011-13-29 15:20:0  + 2 行 find *_driver_deinit process fail
rebuild: ROM Size:00000000 CRC32:0000→0003 Update time:1980-0-0 0:0:24   （且少这 2 行 ⇒ 提前崩）
```

已定位的证据链：

- 打印点：`spi_driver_init`（0x2c4044）`printf("ROM Size:%08X CRC32:%04X ", FlashSize, [sp+8])`
  + `printf("Update time:"); DateToTmuDate([sp+12])`；
- 两个值来自 **`sp+8` / `sp+12`**，本应由 `sfc_request()` 填入安全数据；
- **栈投毒未改变这两个值**（与投毒前完全一致）⇒ 它们**不是**栈垃圾，而是**被代码写入**的
  ⇒ 指向 `sfc_request`（0x2c39f0，904 B）或安全数据读路径的重建保真度；
- 我们重建的 `sflash_read_security_data` 与工厂**逐指令一致**（`0x4848` + 零 = 4 字节栈槽，
  参数 `(&local, param_2, param_1, 0x100)` 对应 r0/r1/r2/r3 完全吻合）⇒ 嫌疑集中在 `sfc_request`。

**下一步**：① 逐指令对照 `sfc_request` 的"寄存器→缓冲区"写入路径（重点看 `param_4 & 3` 的
字节循环与 `uVar1 = param_4 >> 2` 的边界）；② 顺带解释"提前 2 行崩"是否同源。

---
### 2026-09-14 第二十轮：★★★ 设备兼容性硬伤修复（GLIBC 2.34 → **2.7**）+ libz 地雷

本轮是「行为差分只跑到 13 行就全绿」这个盲区暴露出来的两类**真机阻断级**问题。

**① GLIBC 下限（真机起不来）**

| | 工厂 rkgame | 修复前（CI GCC 链接） | 修复后 |
|---|---|---|---|
| 需要的最高 GLIBC 标签 | **GLIBC_2.7** | **GLIBC_2.34**（还有 2.29/2.33） | **GLIBC_2.7** ✅ |

设备侧证据（三条独立）：
· `golden/factory.rkgame.bin` 的 `.dynstr` = `{GLIBC_2.4, GLIBC_2.7}`；
· 设备 SD 上原厂 **ARM** 运行库（SDL / libz / libpng12 / freetype / libcrypto）最高只用 **GLIBC_2.16**
  （同目录另有 MIPS 库，属另一机型，不可当 sysroot —— 与既有结论一致）；
· rkgame 的 `.comment` = **GCC 6.2.0**，SD 上 `libstdc++.so.6.0.22`（GCC 5/6 时代）⇒ 设备 glibc 处于 **2.16~2.24** 区间。

⇒ 要求 2.34 的产物在设备上必然 `version GLIBC_2.34 not found` 起不来。
**修法**：链接改用 **zig + `-target arm-linux-gnueabihf.2.7`**（zig 0.16 支持在目标三元组里指定 glibc 版本。
实测 `-target …2.7` 的产物 GLIBC 标签 = `{2.4, 2.6, 2.7}`）。附带收益：**自动带回 `libpthread.so.0` / `libdl.so.2`**
（glibc 2.7 时代这两个是独立库）⇒ NEEDED 结构更贴近工厂。

**② `compress`/`uncompress` 被绑成 ABS 0（存档/读档必崩）**

它们被 `retro_save_state` / `retro_load_state`（及 `TestLibz0`）调用，而链接脚本里 `PROVIDE_HIDDEN(compress = 0)`
把它们绑成 **ABS 0** ⇒ 调用即跳地址 0。工厂的取值方式 = 从 **libz.so.1 动态导入**（NEEDED libz.so.1）。

**修法**：新建 `src/compat/zstub.c` —— **链接期桩 DSO**（SONAME=`libz.so.1`）。
★ 为什么不直接链一个真实 `libz.so.1`：实测链接真实 DSO 会写下 `ZLIB_1.2.x` **符号版本需求**，
而设备 SD 上原厂 ARM libz 导出的版本集是**非标准的**（`ZLIB_1.2.0 … ZLIB_1.2.12`）⇒ 可能 `version ZLIB_x not found`。
桩**不含任何版本标签**，对任何 zlib 都安全。桩不打包、不在设备执行 —— 运行期由设备自己的 libz 解析。
链接脚本里的 `PROVIDE_HIDDEN(compress/uncompress = 0)` 已**删除**。

**③ 新增门禁（`tools/dyn_audit.py` A6/A7）**

| 门禁 | 判定 | 现状 |
|---|---|---|
| **A6 ABS 0 的 FUNC/OBJECT 符号** | ⇒ **FAIL**（排除 `STT_FILE` 与 `_init`/`_fini`） | **0 个** ✅ |
| **A7 GLIBC 版本上限 > 工厂** | ⇒ **FAIL**（设备上 version not found） | **2.7 ≤ 2.7** ✅ |
| A7 NEEDED 结构差异 | ⇒ WARN（已知可接受差异单列） | 缺 `libstdc++.so.6`（operator new/delete 用自备 C shim，malloc 语义等价）、`libgcc_s.so.1`（纯 C 无展开需求） |

**结果（本地 zig 全链路）**：NEEDED = `libz.so.1, libdl.so.2, libm.so.6, libpthread.so.0, libc.so.6`；
**布局 PASS**（全局 193/194 = 99.5%）；**ABI PASS**；**dyn_audit PASS**（FAIL 0 / WARN 3）。

**④ CI 与本地统一工具链**：两个 workflow 都改为 `pip install ziglang==0.16.0` →
`CC=$ZIG cc` + 独立 `ZIG_GLOBAL_CACHE_DIR`（并发共享 cache 会 CacheCheckFailed）。
⇒ 消除「GCC 链接 vs lld 链接」的段划分差异（那曾产出一次"假红"），也让 CI 产物的 GLIBC 下限与本地一致。
（GCC/binutils 仍保留安装：`arm-linux-gnueabihf-gcc` 的 N3 ABI 对照步骤与 `objdump` 指纹步骤仍用它。）

---

### 2026-09-14 第十九轮：★★★ P5 行为差分首次 PASS；门禁「假红」修正

**CI（commit `f28630c5`）结果分裂，但两边都有信息量：**

| workflow | 结果 | 说明 |
|---|---|---|
| `1to1-qemu-behav` | **success** | **行为差分 B1–B7 全 PASS** |
| `1to1-verify` | **failure** | 硬门禁「镜像尾部 slack」在 CI 报 1 项违规 |
| `rkgame-rebuild` | success | — |

**行为差分首次通过（观测窗口 13 行完全一致）：**

```
factory  binary=/sdcard/cubegm/rkgame  sha=8ff3b4b70c253ff7  exit=139  stdout=13 行  menu.log/2 行
rebuild  binary=/sdcard/cubegm/rkgame  sha=e7c45aee70ed9a31  exit=139  stdout=13 行  menu.log/2 行
[PASS] B1 exit_code 139 vs 139      [PASS] B2 events 13 vs 13
[PASS] B3 new_files 0 vs 0          [PASS] B4 changed_files 0 vs 0
[PASS] B5 log_sha d7c86a6f…(menu.log) vs 同
⇒ 门禁结果: PASS (0 项失败)
```

两侧 stdout 逐行相同：`rkgame v1.42` / `directory:/sdcard/cubegm/` / `appname:rkgame` / `displayfps:0` /
meminfo 8 行 / `open driver.so fail, /sdcard/cubegm//driver.so: …` / `Failed to initialize GPIO`
⇒ 段保真修复**完全生效**（第十七/十八轮的两处修复都得到验证）。

**门禁 FAIL 是「假红」而非产物缺陷**：CI(GNU ld) 把镜像区切成两条 LOAD ——
`0x3ae5c4..0x3e1ad3`(.fimg_bss) 与 `0x3e2000..0x3f2000`(.fimg_bss_pad)。原门禁要求**单条** LOAD
同时覆盖 `.fimg_bss` 末与 +0x1000 ⇒ 必然失败；而内核对 PT_LOAD 只按**页**授权，前一条尾部会被
向上取整到 0x3e2000，与 pad **无缝相接** —— 这正是行为差分能 PASS 的原因。

**修正**：`verify_layout.py` 新增「**运行期可访问区间 = 页对齐后的 LOAD 并集**」（`_paged_union` +
`covered()`），slack 门禁改按并集判定，并在报告里打印该并集便于人工核对。
**双向单元测试**（用 CI 的真实 LOAD 表）：修复后 `covered(.fimg_bss末, +4K)=True`；
去掉 pad 段后 `=False` ⇒ 新口径**放行正确产物、仍拦住真实地雷**。
本地复测：布局 **PASS**、ABI **PASS**、dyn_audit **PASS**（FAIL 0 / WARN 3）。

**★ 下一轮已定位的风险（本轮新发现）**：`NEEDED` 列表不一致 ——
工厂 = `libz.so.1, libdl.so.2, libm.so.6, libstdc++.so.6, libpthread.so.0, libgcc_s.so.1, libc.so.6`；
我们的重建产物只有 `libm.so.6, libc.so.6`（`compress/uncompress` 仍是链接脚本内 `= 0` 占位）。
当前不暴露只因为两侧都在 `Failed to initialize GPIO` 处就崩了；**一旦把执行驱动得更深（解压 UI 资源、
读 joystick.zip）就会踩到**。⇒ 与「假硬件 shim 让两侧走得更深」一起处理。

---

### 2026-09-14 第十八轮：★★★ 段保真度 —— 工厂「地址 0x8000 以下为空洞」被我们填上了

第十七轮的 `.fimg_bss_pad` 修复**完全生效**（commit `5d7e74f7`，CI 实测）：

| 事件行 | 修复前 | 修复后 |
|---|---|---|
| `directory:` / `appname:` | **空** | `/sdcard/cubegm/` / `rkgame` ✓ |
| 第 4 行 | `open config.xml fail!` | `displayfps:0` ✓ |
| driver.so 路径 | `/driver.so` | `/sdcard/cubegm//driver.so` ✓ |
| **B1 退出码** | 139 vs 134 | **139 vs 139 PASS** ✓ |

`*** stack smashing detected ***` 自己消失了 —— 它本就是空 work_path 的连锁后果。
于是只剩 **一行** 差异：重建侧多打印 `RF_IC Test Fail !`。

#### 一、这一行差异的根因：段权限/地址空洞不一致

定位到具体函数：工厂在 `InitRFJoystick()` 的**第一次 GPIO 写**就崩了，而我们的版本走完了
6 次 GPIO 操作 + 3 次 SPI_Write + `SPI_Read`，直到读回值不等于 0xa5 才打印。

```
sunxi_gpio_set_cfgpin(0,1) →  *(gh_uint *)(GPIO2 + 4) = ... | 8;
   GPIO2 因 /dev/mem 打不开而保持 NULL ⇒ 写**地址 4**
```

程序头对比（决定性）：

| | 首个 PT_LOAD | p_align | 地址 0..0x7fff | RWX 段 |
|---|---|---|---|---|
| **工厂** | `va=0x8000..0x3ad1ec` `fl=0x5(RX)` | **0x1000** | **空洞**（未映射） | 无 |
| 我们（修复前·CI/GNU ld） | `va=0x0..0x4de8cc` `fl=0x7(**RWX**)` | **0x10000** | 已映射**且可写** | 有 |

⇒ 工厂：写地址 4 → 立刻 SIGSEGV；我们：写地址 4 **静默成功**（还污染了镜像首字节）→ 继续跑。
根因是 `p_align=0x10000` 让链接器把首段起点一路向下取整到 0。

#### 二、修复与门禁

1. **`-Wl,-z,max-page-size=0x1000`**（与工厂一致；工厂各 LOAD 都是 `al=0x1000`）。
   本地实测：首段变成 `va=0x9000`（`off=0`，ELF 头随之映射在 0x9000 ⇒ `AT_PHDR` 仍有效），
   **地址 0/4/0x7ffc/0x8000 全部变为未映射**，且**不再有 RWX 段**。
2. **`tools/extract_factory_phdrs.py` + `ledger/factory_phdrs.tsv`**：把工厂的程序头
   （地址/权限/对齐）固化成**基准台账**（结论：工厂最低 LOAD = 0x8000）。
3. **`verify_layout.py` 新增「段保真度门禁」**（基准 = 上面的台账）：
   ① 任何 LOAD 不得覆盖 `[0, 工厂最低 LOAD)`（地址空洞必须保留）；
   ② 不得出现 `W ∧ X` 的 LOAD（工厂没有）；
   ③ 每个 LOAD 的 `p_align` 必须等于工厂的 `0x1000`。

**本地复测**：布局 **PASS**（全局 193/194、节覆盖 0、镜像 slack 0、**段保真 0**）、ABI **PASS**、`dyn_audit` **PASS**。

#### 三、附带完成：构建标志与工厂对齐

工厂的完整编译命令行就印在二进制里（`.comment`）：

```
GNU C11 6.2.0 -mabi=aapcs-linux -march=armv7-a -mfloat-abi=hard -mfpu=neon -mtune=cortex-a8
-mtls-dialect=gnu -g -O2 -std=gnu11 -fgnu89-inline -fmerge-all-constants
-fno-stack-protector -frounding-math -fomit-frame-pointer
```

工厂里 `stack_chk` / `FORTIFY` / `__memcpy_chk` 出现次数**全是 0**。已给全部编译入口
（`recon_build.sh` / `recon_local.sh` / `link_audit.sh` / `build_upstream.sh` / `link_full.sh`）
统一加上 `-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0`（commit `f13063e1`），
消除"工具链默认值差异"这一类假分歧。（`-O1` vs 工厂 `-O2` 仍是有意保留的差异：
反编译产物在 `-O1` 下通过双轨门禁；T1 汇编等价需同款 GCC 6，已归档。）

**下一步**：读 CI 的段保真门禁与行为差分 —— 预期 `RF_IC Test Fail !` 消失、B1/B2 全绿或
再暴露**新的**真实分歧。

---

### 2026-09-14 第十七轮：★★★ P5 首次真实差分 → 根因定位（镜像 `.bss` 之后无映射余量）

观测链修好后，**同一轮 CI 立刻给出四条可行动分歧**（commit `3715d428`，`1to1-qemu-behav` failure，
但这是**有内容的** failure）：

```
参考端 factory: exit=139(SIGSEGV) stdout=13 行  binary sha=8ff3b4b70c253ff7
重建端 rebuild: exit=134(SIGABRT) stdout=14 行  binary sha=af7e22fe72276163
  [FAIL] B1 exit_code  139 vs 134
  [FAIL] B2 events     13 vs 15 行
  [PASS] B3/B4/B5/B6/B7   （新增/变更文件、menu.log sha 全部一致）
```

| # | 分歧 | 说明 |
|---|---|---|
| 1 | `directory:` / `appname:` **为空**（工厂是 `/sdcard/cubegm/` 和 `rkgame`） | **根因**，见下 |
| 2 | 重建侧多出 `open config.xml fail!`，工厂侧是 `displayfps:0` | 同源：work_path 空 ⇒ `/setting.xml` 打不开，`GetConfig()` 走失败分支 |
| 3 | `open driver.so fail, /driver.so`（工厂是 `/sdcard/cubegm//driver.so`） | 同源：`sprintf("%s/driver.so", work_path)` |
| 4 | 重建侧多出 `RF_IC Test Fail !` + `*** stack smashing detected ***` | 待 #1 修好后复测 |

#### 一、根因（strace 铁证）

```
工厂   : readlink("/proc/self/exe", 0x003e1498, 4096) = 21
重建产物: readlink("/proc/self/exe", 0x003e1498, 4096) = -1 errno=14 (Bad address)
```

两侧 `work_path` 是**同一地址**（0x3e1498，镜像保证），但重建产物 **EFAULT**。

排除「bss 没被映射」：重建产物在 `readlink` 之前已成功写 `autorunfile[0]='\0'`（该符号也在 `.fimg_bss` 内）
并继续跑到打印 meminfo ⇒ **bss 映射正常**。

真因 = **`work_path + 4096` 的尾部落进了未映射空洞**：

| | `.bss` 结束 | 下一处已映射内存 | `work_path+4096`=0x3e2498 |
|---|---|---|---|
| 工厂 | 0x3e1ad3 | **堆，brk=0x3e2000（紧贴 .bss）** | 落在堆页内 ✓ |
| 重建 | 0x3e1ad3 | 运行时区在 0x400000 / brk=0x0503e000 | 未映射 ✗ |

即：**工厂进程天然具备「`.bss` 之后就是堆」的性质**（内核把 brk 放在最后一个 PT_LOAD 之后，
而工厂的 `.bss` 就是最后一个）；我们的重建产物把运行时区排在镜像之后，brk 被推到了 0x503e000。
内核的 `readlinkat` 只校验真正写入的字节（21），**qemu 校验整段 `bufsiz`（4096）** ⇒ 只有 qemu 下暴露。

#### 二、修复 + 门禁补强

1. **`.fimg_bss_pad`（64 KiB，页对齐，progbits 零填充）**：在镜像 `.bss` 之后补一段已映射的零页，
   恢复「数据段之后仍有已映射内存」的进程镜像性质。副作用是好的：段 `filesz == memsz`，
   连"加载器是否正确零填 bss"都不再依赖。（`gen_data_module.py` 生成 + 链接脚本自动排 VMA。）
2. **`verify_layout.py` 新增三条**（此前 3 条门禁全 PASS 却漏掉了这个 bug）：
   - **程序头全量表**（本地 lld 11 条 LOAD / CI binutils 5 条 —— 段划分完全不同，必须能看到原件）
   - **节覆盖门禁**：SHF_ALLOC 节必须被某个 PT_LOAD 完整覆盖
   - **镜像尾部 slack 门禁**：镜像区**最后一段**之后必须仍有 ≥4 KiB 已映射内存
     （★ 口径只查最后一段：镜像内部段间空隙是工厂原版自己的布局，逐段要求会误报）
3. 顺带核实：`GetConfig()` 的失败分支字符串**确实是** `open config.xml fail!`（0xa344 的 PC 相对链
   解出 0x2dbcc8），我们的重建**没有**用错字符串（`open setting.xml fail!` 属于另外两个函数）。

**本地复测**：布局门禁 **PASS**（全局 193/194 = 99.5%、节覆盖 0 未覆盖、镜像 slack 0 不足）、ABI **PASS**、
`dyn_audit` **PASS**，`work_path+4096` 已落在 `0x003ae5c4..0x003f2000`。

---

### 2026-09-14 第十五轮：工厂侧「静默 exit=1」真因 = 文件权限

宿主 `strace` 显示 qemu 只做了 4 个系统调用就退出、零报错；**加可执行位后立刻变成 guest 真的跑起来**。
真因：`golden/factory.rkgame.bin` 由 git 检出 ⇒ 权限 **0644**（树条目 100644），而重建产物由编译产生 ⇒ 0755。
qemu-user 对**不可执行**目标会走 `execve` 回退 → `EACCES` → **静默 exit 1**。
⇒ 两侧运行前必须 `chmod +x`；并在 `push_1to1.py` 对该文件树条目标 **100755**（已实测 `mode=100755` 入库）。
附带发现：`ioctl(1,TCGETS)=ENOTTY` ⇒ stdout 是管道 ⇒ glibc 全缓冲 ⇒ 崩溃现场输出丢失（→ 第十六轮修）。

---

### 2026-09-14 第十六轮：★★ P5 观测口径修正 —— 「没有输出」是假象（4 个真问题）

上一轮拿到的是「工厂侧 rc=1、零输出、连 syscall 轨迹都没有」。本轮把它彻底查清，
并修掉**四个会让差分假空洞 / 假失败 / 丢维度**的真问题。

#### 一、四个真问题

| # | 问题 | 症状 | 修复 |
|---|---|---|---|
| 1 | **日志文件名错了** | 真机日志是 `%s/menu.log`（`LoadMenuLog`/`SaveMenuLog` 里 `sprintf(acStack,"%s/menu.log",work_path)`）；仓库里**从来没有** `rkgame.log` ⇒ 采集永远 0 行 | `behav_capture.sh` 主看 `menu.log`（`rkgame.log` 仅兼容兜底），新增 `log_sha256_16` |
| 2 | **stdout 被全缓冲吃掉** | `ioctl(1,TCGETS)=ENOTTY`（stdout 是管道）⇒ glibc 全缓冲；被测程序 `abort()`/被信号杀死 ⇒ 缓冲区**不 flush** ⇒ 连 `puts("rkgame v1.42")` 都没有 ⇒ "没有输出"是**假象** | 新增 `tools/pty_exec.py`：**只把 fd0/1 挂 pty**（行缓冲），**fd2 保持独立**（不像 `script(1)` 会把 qemu 自身报错混进 stdout） |
| 3 | **两侧路径不同** | 工厂用 `get_executable_path()`（=`/proc/self/exe` 的目录）当 `work_path`，再拼出 `setting.xml` / `cores/config.xml` / `menu.log` / `joystick.zip` / `saves` / `states`。两个二进制各放各自目录 ⇒ `directory:` 行不同、能读到的资源也不同 ⇒ **比的是路径差异** | 两侧都从**同一绝对路径** `/sdcard/cubegm/rkgame` 运行：`tools/stage_sdcard_env.sh` 先铺环境+放二进制→跑→**重新铺环境**+放另一个二进制→再跑 |
| 4 | **可执行位** | `golden/factory.rkgame.bin` 由 git 检出是 **0644**；qemu-user 对不可执行目标走 `execve` 回退 → `EACCES` → **静默 exit 1、零输出、零 syscall** | 运行前 `chmod +x`；并在 `push_1to1.py` 对该文件树条目标 **100755**（权限位是执行语义，不是元数据） |

#### 二、新增最小真机环境 `golden/sdcard_min/`（355 KB，只读拷贝）

`setting.xml`(819B) / `menu.log`(444B) / `favorites.lst` / `recent.lst` / `fileinfo` /
`joystick.zip`(332KB) / `cores/config.xml`（**原厂格式** 3822B）+ `MANIFEST.sha256`（铺设时逐个核验）。
不放大件（`ui_*.zip` 4.9MB、`font.ttf`、`resource.cpd`）—— 启动阶段走不到 `main_Menu()`。
`joystick.zip` 必须放：`InitJoystick()` 会读它，正好检验我们重建的 unzip（`TUnzip`）。

#### 三、判定维度加强（`behav_diff.py`）

| 维度 | 规则 |
|---|---|
| **P0a** | 两侧 `workdir` 必须相同，否则 FAIL（比的是路径差异） |
| **P0b** | 两侧二进制 sha **必须不同**（相同 = 拿同一份自比，无意义） |
| **B0** | 参考侧**必须产生可观测行为**，否则 INCONCLUSIVE(3)。★ 判据用 `observed` 字段（stdout/stderr/新增/变更），**不能用 `log_lines`** —— 运行目录预置了 `menu.log`，`log_lines` 恒 ≥1 |
| B1~B3 | 退出码 / 语义事件（`O|`stdout `E|`stderr `L|`日志）/ 新增文件路径 |
| **B4 / B5** | 变更文件路径 / `menu.log` 内容 sha（两侧都有日志时） |
| B6 / B7 | 帧缓冲哈希 / shm 心跳（两侧都可读时） |

事件归一：剥 ANSI、`\r`、`0x…`→`ADDR`、≥3 位数字→`N`，并给每个源加前缀。

#### 四、本机空跑验证（假 `qemu-arm-static` 垫片 + 假 guest，**不烧 CI 分钟**）

空跑立刻又抓到两个自身缺陷（这正是它存在的意义）：

5. ★ **探针污染基线快照**：`-strace` 探针先跑并可能新建/改写 `saves`/`states`/`menu.log`，
   紧接着采集 ⇒ "前置快照"已含探针痕迹 ⇒ `new_files`/`changed_files` **永远为空**（静默丢一个维度）。
   修复：探针跑完后**重新铺环境**再采集。
6. ★ `"${PY:-python3}" … | tee "$OUT/behav_diff.txt"; rc=$?` —— POSIX sh **没有** `${PIPESTATUS[@]}`，
   `rc` 拿到的是 **`tee`** 的退出码 ⇒ 门禁永远"成功"。改为落文件再 `cat`。

分支用例（全部本地跑通）：

| 用例 | 期望 | 实测 |
|---|---|---|
| 行为相同 / 字节不同 | 0 PASS | **0** ✓ |
| 行为不同（退出码+事件） | 2 FAIL | **2** ✓ |
| 参考侧完全静默 | 3 INCONCLUSIVE | **3** ✓ |
| 两侧同一份二进制 | 2 FAIL（P0b） | **2** ✓ |
| 重建侧新建文件 / 改 menu.log | 2 FAIL（B3 / B4+B5） | **2** ✓ |

`pty_exec.py` 本身：退出码透传(3)、超时(124)、命令不存在(127)、**stderr 独立** 全部本机验过
（本机无 `termios` ⇒ 走降级路径；CI 走 pty 路径）。

**下一步**：推 CI，读「工厂侧到底跑到哪一步」——现在 stdout 不会再丢，`event` 序列里有
`O|rkgame v1.42` / `O|directory:…` / `O|appname:…` / `GetConfig()` 的报错，差分才真正开始说话。

---

### 2026-09-14 第十四轮：P5 qemu 行为差分接入（环境打通；被测程序仍在驱动中）

**先决问题：qemu 在哪跑？**（用户提示「本机 / cnb.cool 都有 qemu 环境」，故彻底搜了一遍）

| 位置 | 结论 | 证据 |
|---|---|---|
| 本机 | **没有 qemu** | PATH 上 `qemu-arm/arm-static/system-arm…` 全无；`Program Files`/`Program Files (x86)`/`D:`/用户目录 5 层深 `find -iname "qemu*.exe"` 零命中；无 Docker；`wsl.exe` 被**安全策略黑名单**拦截（不可用） |
| cnb.cool | **没有交互式 qemu 环境** | `cnb workspace list-workspaces` → 仅 2 个云原生开发环境（`lieguch/hello-cnb`、`lieguch/cubeGM`）**均为 `closed`**；CNB 侧的 qemu 是 **pipeline 阶段**（`lieguch/cubeGM/.cnb.yml` → `test-emu`）⇒ 本质仍是 CI |
| GitHub Actions | ✅ **有先例可复用** | `cnb-rkgame-final/.github/workflows/build.yml` 的 `Setup qemu` + `Test (emu)`：ubuntu-22.04 + `qemu-user-static` + armhf sysroot |

⇒ 按用户指示「都没有就提 CI」，落在 **GitHub Actions**。

**新增（全部经本机预演，不烧 CI 分钟）**

| 文件 | 作用 |
|---|---|
| `tools/fetch_armhf_sysroot.py` | 读 ports.ubuntu.com 的 `Packages.gz` 索引 → 解析 `Filename` → 直接下 `.deb` + 解包。**不碰任何 apt 状态**。带纯 Python（ar+tar+zstd）解包兜底，可在 Windows 上完整预演 |
| `tools/ci_qemu_env.sh` | 装 `qemu-user-static` + 建 sysroot + **动态查找**校验 10 个运行库 |
| `tools/ci_qemu_behav.sh` | 两侧同环境采集 + **运行时探针**（`-strace` syscall 轨迹 / `-d in_asm` 翻译级尾部）+ 差分 |
| `.github/workflows/1to1-qemu-behav.yml` | **独立 workflow**（与静态门禁分离），内部**无 `continue-on-error`** |
| `golden/factory.rkgame.bin` | 工厂二进制入库（3,921,108 B，sha256 `8ff3b4b7…`）—— 差分**必须两侧同环境各跑一次**，否则比的是环境差异 |

**CI 首轮实测（commit `5e05448e`）**：环境 ✓ / 工作目录 ✓ / 构建 ✓ / 采集 ✓（**跑到了真正运行被测程序**），门禁 FAIL。

**已修 3 个真问题**

1. ★ `behav_capture.sh` 的 `SHM=$(ipcs … | grep -c … || echo 0)` —— `grep -c` 0 命中时**已输出 `0`**，
   `|| echo 0` 再补一行 ⇒ JSON 里出现裸 `0` ⇒ `behav_diff.py` 的 `json.load` **直接崩**。
   已修（只保留 `grep -c`，加数值兜底），并**本地复现**了新/旧两种输出对比。
2. ★ **sysroot 不能用 apt 取**：`dpkg --add-architecture armhf` 后全局 `apt-get update` 会去
   `security.ubuntu.com` 拉 `binary-armhf/Packages` → **404**（Ubuntu security 源没有 armhf）→ 返回 100 → 步骤挂。
3. ★ **sysroot 必须与工具链同 glibc**：CI 是 Ubuntu 22.04(glibc **2.35**)；沿用先例的 Debian 9(2.24)
   会让重建产物 `version GLIBC_2.35 not found`。工厂 rkgame 只要 ≥2.7，向下兼容。
   （另：Ubuntu 22.04 armhf 的库**分两处** —— glibc/zlib 在 `lib/`，libstdc++/libdrm/libasound 在 `usr/lib/`，
   故 `LD_LIBRARY_PATH` 两个都要给。）

**下一轮待解（已有探针，等 CI 证据）**

#### ★★ 已定位并修复：`DT_INIT = 0`（这是"重建产物起不来"的真因）

CI 探针（`-strace` + `-d in_asm`）给出决定性证据：
```
--- SIGILL {si_signo=SIGILL, si_code=2, si_addr=0x00000020} ---
翻译级轨迹尾部：
  0x3fe8d89c:  4798    blx  r3          ← r3 = *(r6) + r1，而 *(r6) == 0
  IN: 0x00000000:  464c457f  undefined   ← 跳到地址 0，把 ELF 头当指令执行
  IN: 0x00000020:  00509a94  ldrbeq r9, [r0], #-164   ← 到这里遇未定义指令 → SIGILL
```
**成因链**：链接脚本里写了**裸赋值** `_init = 0;`（本意只是"兜底占位"）→ 它**压掉了 crti.o 的真 `_init`**
→ 链接器在 `.dynamic` 写下 **`DT_INIT = 0`** → glibc 的 `call_init` 见到 `DT_INIT` 就调用 → `blx` 到 0。
又因为**非 PIE 时 vaddr 0 正是我们自己 ELF 头所在的 PT_LOAD（已映射）**，所以不是 SIGSEGV 而是 SIGILL。

**修复**：所有兜底一律改成 `PROVIDE_HIDDEN(sym = 0)`（"别人定义了就不生效"）。
CI（GCC 链了 crti.o）实测：`DT_INIT = 0x00401428`、`_init shndx=14`（真实 `.init` 节）⇒ **修复生效**。

#### 新增静态门禁 `tools/dyn_audit.py`（**不需要 qemu** 就能拦住这类 bug）

| 检查 | 判定 |
|---|---|
| `DT_INIT`/`DT_FINI` 存在但为 0 | FAIL（= 初始化链会调到地址 0） |
| `_init`/`_fini` 被定义成 **ABS 0** | FAIL（裸赋值残留特征） |
| `e_entry` 不在可执行 PT_LOAD 内 | FAIL |
| `DT_*_ARRAY` 已声明但 SZ == 0 | WARN（C 程序无构造子时合法） |
| `.rel.plt` 对应 GOT 槽静态值为 0 | WARN |

★ 本地/CI 差异**条件判定**：本机 zig 不带 crti.o ⇒ 无 `.init` 节 ⇒ 判 WARN；
CI 用 GCC 必然链 crti.o ⇒ 判 FAIL。同一条门禁两侧都给出正确结论。
已接入 `1to1-verify`（**硬门禁**，已 success）+ qemu workflow + `link_full.sh`。

**修复后的实测（commit `903e8bb8`）**

| 项 | 结果 |
|---|---|
| `1to1-verify` | **success**（含 dyn_audit 硬门禁 PASS：`DT_INIT=0x00401428` / `_init shndx=14`） |
| 重建产物在 qemu 下 | **从 SIGILL 前进到 `*** stack smashing detected ***`（SIGABRT, exit=134）** ⇒ CRT + `main()` 都跑起来了 |
| `behav_diff.py` | 正确判 **INCONCLUSIVE(3)** —— B0 非空洞前置检查生效，拒绝"两侧都空"的假通过 |
| 工厂二进制 | 仍在 **3 ms 内 exit=1、stdout/stderr 全空**，连"裸跑"（无 `-strace` / 无 `-E`）也一样 ⇒ **问题在 qemu 自身，不在 guest**（guest 一个 syscall 都没发）。已加宿主 `strace` 观察 qemu 进程 + 「加可执行位」「不带 `-cpu`」两条试探 |

**下一步**：① 读宿主 strace → 定位工厂二进制为何在 qemu 下**加载阶段**即退（参考侧驱动起来，差分才有意义）；
② 定位重建产物的 stack smashing（这是 1:1 保真度的**真实、可行动信号**：某个局部数组/结构尺寸与工厂不一致）。

#### ★★ 工厂侧"静默 exit=1"也已定位（宿主 strace 一刀切开）

宿主 `strace` 显示 qemu 进程自身只做了 4 个系统调用就退：
```
execve("/usr/bin/qemu-arm-static", [... "golden/factory.rkgame.bin"], ...)
readlink("/proc/self/exe", ...)                              = 24
openat(AT_FDCWD, "golden/factory.rkgame.bin", O_RDONLY)      = 3
openat(AT_FDCWD, "/proc/sys/vm/mmap_min_addr", O_RDONLY)     = 4
ioctl(1, TCGETS, ...)                                        = -1 ENOTTY
+++ exited with 1 +++            ← 零错误输出
```
**决定性对照实验：给该文件加可执行位后立刻变成 `rc=139`（guest 真的跑起来并 SIGSEGV）**。

⇒ **真因：仓库检出的 `golden/factory.rkgame.bin` 权限是 `0644`（git 存的是 100644），
而重建产物 `build/rkgame.rebuilt.elf` 是编译产生的 `0755`。** qemu-user 对**不可执行**的目标
会走 `execve` 回退路径 → `EACCES` → **静默 exit 1**（连一行报错都没有）。这不是二进制的问题，
**是我把"权限"当成了无关紧要的元数据**。

**顺带解释"输出为空"**：qemu 的 `ioctl(1, TCGETS)=ENOTTY` 说明 stdout 是**管道**（非 tty）
⇒ glibc 采用**全缓冲**；重建产物是 `abort()`（SIGABRT）退出的，**缓冲区不会 flush** ⇒
`puts("rkgame v1.42")` 的内容丢失。参考侧同理。（下一轮可用 `script -qec` 造一个 pty 拿到行缓冲。）

**下一轮要做的两件小事**（都很小，但都是"必须"）：
1. 运行前对两侧都 `chmod +x`（并从 git 侧把该文件置为 100755）；
2. 用 `script -qec` 或 `stdbuf -oL` 拿到可用的 stdout。

之后再读两侧行为指纹，`behav_diff.py` 才会给出有意义的结论。

---

### 2026-09-14 第十二轮：★ CI 治理 —— 清除「假绿」（门禁失败却报 success）

**触发**：本轮新增的「可映射性门禁」在 CI 上 **FAIL**（`__TMC_END__` 越界），
但 `1to1-verify` 仍报 **success** —— 我只在**手动下载制品**时才看到 `结论: FAIL`。
根因：P3 两个步骤带着 `continue-on-error: true`，失败被静默吞掉。这正是长期记录的
「假绿必除」问题在 CI 层的残留。

**改动**（`.github/workflows/1to1-verify.yml`）：

| 步骤 | 之前 | 现在 |
|---|---|---|
| P3 链接就绪审计 | `continue-on-error: true` | **硬门禁**：脚本 rc 透传 + **显式硬断言** `重复定义==0 && MISSING==0`（不满足即 `exit 1` 并打 `::error::`） |
| P3 完整链接 + ABI/布局门禁 | `continue-on-error: true` | **硬门禁**：`link_full` / `verify_layout` / `abi_check` 任一非零即失败 |
| 新增 | — | **门禁汇总**步骤写入 `$GITHUB_STEP_SUMMARY`（双轨通过率 / 审计 / 布局 / 命名自洽 / 可映射性 / link_err 字节数） |

**证据**：`grep -E '^[[:space:]]*continue-on-error:'` → **无匹配**（已全部移除）；
断言逻辑**双向单元测试**通过 —— 伪造 `重复定义=1` → **退出码 1**；`重复定义=0 / MISSING=0` → **退出码 0**。

> 之所以值得单独成轮：门禁本身不可信，等于没有门禁。现在「本地 PASS」与「CI PASS」
> 才是同一件事，回退也会立刻变红而不是静默放过。

---

### 2026-09-14 第十一轮：★★ P3 三期① 工厂 `.text` 全镜像 → **MISSING 归零**

**问题**：最后 3 个 `MISSING`（`UNK_000d2f00` / `UNK_00118000` / `UNK_002e0938`）在链接脚本里被
**显式置 0** 占位。这不是"无害占位"——三个引用点都会真的读地址 0：
`if (&UNK_000d2f00 < puVar3)` 的循环闸门、`scr_data = UNK_00118000 + off` 的缓冲基址、
`UNK_002e0938 + i != pbVar12` 的数组上界。**是运行期地雷**。

**根因（实测，非推测）**：

| 事实 | 证据 |
|---|---|
| 三个地址**都不落在任何函数内** | `functions.txt` 区间判定 |
| `0xd2f00` / `0x118000` 处 Ghidra 已标为 **`.word` 数据**（非代码） | `disasm_text.txt` |
| 工厂 `.text` 的 `0x30000…0x2b4d60` 区间**没有任何函数** | 函数地址序列在此断档 |
| `0x2e0938` = `asc2_1608`(0x2e0928) **+ 0x10**，在 `.rodata` 内 | 工厂 symtab |
| 全文件字节搜索：三个值**都不以 32 位常量形式出现** | 说明是「基址+偏移」算出来的，不是 movw/movt 常量 |

⇒ 结论：工厂 `.text` 段内嵌了 **~2.7MB 只读数据表**，这 3 个是其中的表地址。
唯一忠实做法 = **镜像整段工厂 `.text` + `.set` 别名**（与其它段同一套架构）。

**落地**：

- `gen_data_module.py`：`SEC_DEF`/`FIMG` 加入 `.text`；`RE_UNK` 让 MISSING 解析同时接受 `UNK_<hex>`；
  新增 `MIRROR_END` 收口段声明 size（工厂 `.text` 声明 size 恰好止于 `.fini` 前，已实测确认）。
- 链接脚本重构为三段：
  ① **工厂地址区**（`.fimg_text`@0x9b10 / `.fimg_rodata`@0x2dbca4 / `.fimg_data_rel_ro_local`@0x3ae5c4 /
  `.fimg_data`@0x3af000 / `.fimg_bss`@0x3b2178）—— VMA 一律取「工厂节地址 + SKIP_HEAD」，**不再手写常量**；
  ② **ELF 元数据**（0x400000 起；此前它被挤在工厂地址区里）；
  ③ **运行时区**（`.rodata`@0x410000 / `.data`@0x1000000 / `.bss`@0x2000000 / **`.text`@0x5000000**）。
- 移除 `UNK_*` 的 `sym = 0` 占位（改由镜像真实供应）。

**结果**

| 指标 | 结果 |
|---|---|
| **重复定义** | **0** |
| **MISSING** | **0**（↑ 从 3 归零） |
| upstream | 0 |
| 剩余未解析 | 110 = libc 100 + eabi 6 + libstdc++ 4（链接期由 `-lc/-ldl/-lm/-lpthread/-lgcc` 提供） |
| **ABI 门禁** | **PASS** |
| **布局门禁** | **PASS**：全局 193/194 = 99.5%；**`UNK_*` 三个全部落在精确工厂地址** |
| `link_full_err.txt` | **0 字节** |
| ELF | `build/rkgame.rebuilt.elf` 17,299,316 B |

**新增两条零成本强不变式（已入布局门禁，任一失败即 FAIL）**：

1. **命名自洽**：凡 `UNK_<hex>` / `DAT_<hex>` 符号，其符号值必须 == 名字里的 `<hex>`。
   受检 **162 个，全部通过** —— 任何别名算错偏移都会立刻暴露。
2. **可映射性**：凡我们定义的符号，其值必须落在某个 `PT_LOAD` 内（否则运行期访问即段错）。
   9 个 LOAD 段，**越界 0 个**。
   （实测发现 `.rodata` 镜像尾部有 96B 不在 LOAD 内 —— 但该区间**零符号引用**，属工厂自身
   声明 size 越界所致，已确认无风险。）
   ★ **首轮 CI 就抓到 1 例**：GCC/binutils ld 的段划分与 zig/lld 不同，`__TMC_END__` 正好落在
   `.data` 段尾后一字节 → 门禁 FAIL。这是**误报**（链接器段尾标记按约定就在"最后一字节之后"），
   已把判定口径改为**含终点** `lo <= v <= hi`。该口径仍能抓住真地雷（落在**空洞**里的地址），
   且本地 0 越界、CI 亦 0 越界。**这正是新门禁的价值：它在两个工具链之间暴露了差异。**

**下一步**：① P5 行为差分（本地无 qemu → 需在 CI 挂 `qemu-user-static` + ARM rootfs，或真机采集）；
② P6 真机验收。

---

### 2026-09-13 第十轮：★★ P3 二期④ 重名符号按 TU 拆分（全局命中率 98.5% → **99.5%**）

**问题**：工厂有 4 个名字各存在**同名的两份**（分属不同编译单元）。别名生成器
`syms.setdefault(name, …)` 按名去重 ⇒ 只保留第一份 ⇒ **另一份的所有引用指向错误地址 = 静默语义错误**。

| 名字 | 主名（globals.h） | 另一份 | 实测引用分布 |
|---|---|---|---|
| `handle` | 0x3b21c8 `os_windows_rk.c` static | 0x3cf988 `EmuRun.c` static | **4 vs 17** 个函数 |
| `diff_prev` | 0x3bc414 `ui_jkt.c` static | 0x3e1a38 **全局** | 15 直引 vs **4 经 GOT** |
| `SoundBuffer` | 0x3ceaf0 `ui_jkt.c` static | 0x3e1944 全局 | 1 vs **0（DEAD）** |
| `ArchivePath` | 0x3ae610 `ui_jkt.c` static | 0x3e18d4 全局 | 4（TU 推定）vs **0（DEAD）** |

**新增工具（全部二进制实测，非推测）**

| 工具 | 作用 |
|---|---|
| `tools/xref_scan.py` | A32 **PIC 指令级**交叉引用：还原 `ldr pc+add pc`→基址、GOT 中介访问、`ldr [pc,Rm]`、**「锚点+立即数偏移」直访内存**（地址从不进寄存器）、移位寄存器偏移；产出 `report/xref.json` |
| `tools/dup_syms.py` | 从 symtab 的 `STT_FILE` 还原「符号 → 编译单元」，列出跨 TU 重名组 |
| `tools/dup_assign.py` | 按「F 与 static 是否同 TU」判定归属（TU 多数票），产出 `report/dup_assign.tsv` |
| `tools/apply_dup_split.py` | 按实测表改写 21 个 `.c` 的标识符（预演/`--write` 两档） |

**落地**：拆成 `handle_emurun` / `diff_prev_global`（另两份 DEAD 也补别名以便账本对账）→
`gen_data_module.py` 新增 `SPLIT_ALIASES` 幂等发射 `.set` → 只改需要改的 21 个 `.c`。

| 门禁 | 结果 |
|---|---|
| 宽松/严格编译 | **213/213 = 100%**，假绿 **0** |
| **ABI 门禁** | **PASS**（e_flags=0x5000400 / interp=`/lib/ld-linux-armhf.so.3`） |
| **布局门禁** | **PASS：全局 193/194 = 99.5%**（↑98.5%），4 个拆分条目**全部一致** |
| 剩余唯一偏差 | `_IO_stdin_used`（CRT 内部，镜像按设计跳过 4B） |

★ **扫描器三大漏判陷阱（已全部修掉）**：① 数据处理立即数是 `imm8 ROR(2*rot)`
（`add r2,r3,#2368` 的 imm12 读出是 0xD25）——取错则「基址+偏移」全落空；
② `bl`/`cmp`/`b` **不写 Rd**，误当写 Rd 会清掉正在用的指针（`bl PlaySound` 吃掉 GOT 基址 ⇒ PlayFrame 整条漏判）；
③ Ghidra 导出的 function `size` **越过下一函数** ⇒ 边界必须用「下一函数入口」。

★ **生成头文件地雷（本轮最痛）**：`gen_compat.py` **不可单独重跑** ——
它只生成主块，globals.h 还需要补丁区（`named_array_blobs.h` include + 4 条大对象/常量兜底 +
2 条拆分声明）。漏掉会让通过率从 **100% 崩到 48%（103/213）**。
已固化 `tools/gen_compat_all.sh`（gen_compat → normalize_types → fix_ptr_globals →
patch_globals_extra → check_types）+ 幂等补丁 `tools/patch_globals_extra.py`。
★ 同类坑：`str.partition` 的 **tail 不含分隔符** ⇒ 补丁把 `#include` 整行吃掉
（症状 = 42 个文件报 `game_blob` 未声明）。

**下一步**：① 行为差分（P5，`behav_diff.py`）打头；② `.text` 常量镜像（3 个 `UNK_*`）；
③ 真机验收（P6）。

---

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

---

## 第四十二轮（2026-09-17）：新门禁「调用点实参寄存器对拍（工厂=对照组）」+ 一类新缺陷

### 一、本轮成果

| 项 | 结果 |
|---|---|
| 新工具 | `tools/scan_livein_args.py`（1298 行反汇编 × 两侧，逐调用点对拍） |
| 新门禁 | `1to1-verify` 第 20 步 ★ 硬门禁（新增差异即失败，带台账棘轮） |
| 检出 | **HIGH 5 对 / LOW 70 对**（总计 75） |
| 已修 | `stbtt_GetFontVMetrics` 显式化第 4 实参（`proto.h` 改真原型 + 2 处调用点） |
| 自证 | 三级：① 同 ELF 对拍 = 0；② 锚点被量到；③ 锚点出现在最终违例表 |
| 技能铁律 | 107 → **109** |

### 二、四轮口径演进（每一轮都被自证拦下）

| 轮 | 口径 | 结果 | 被拦下的原因 |
|---|---|---|---|
| 40 | 单侧（我们）"被调者会读而未设" | 工厂对照组 **541 处** | 变参函数 / 跨基本块 / 同对调用实参个数本就不同 |
| 41 | 对拍工厂**反编译 C** | 0 项 | Ghidra 两侧一起丢参数 ⇒ 结构性看不见 |
| 42a | 对拍机器码，`max` | 229 对 | 把"入口参数原样透传"误报 |
| 42b | + 可用性三档（entry/call/jump） | 75 对 | —— 收敛 |
| 42c | + 跨调用仅缺 r0 降级为 LOW | **HIGH 5 / LOW 70** | 收敛 |

### 三、新缺陷类别：**依赖寄存器副产物的脆弱性**

原厂源码 `stbtt_GetFontVMetrics(&font,&fontascent,0)` 是 **3 参**（Ghidra 渲染两侧同为 3 参），
但 GCC 6.2.0 在构造 `r2=0` 时顺带 `mov r3,#0` ⇒ 恰好安全；
我们换 clang 后 r3 留下层残值 ⇒ 被调函数 `if (lineGap) *lineGap = ...` 变成**野写**。

⇒ **不是漏参，而是"原厂偶然确定 → 我们不确定"**。1:1 替代必须显式化（已修 + 改真原型）。

### 四、提交

`tools/scan_livein_args.py`（新）、`tools/livein_args_pending.txt`（台账 75 项）、
`src/compat/proto.h`、`src/proprietary/mui/FUN_0001bbf8_mui_outputxy_t.c`、
`src/proprietary/mui/FUN_0001b240_mui_outputxy_length.isra.19.c`、`.github/workflows/1to1-verify.yml`。

### 五、第 42 轮·终：门禁口径第 3–6 次修正 + 最终台账

- 假阳性四来源全部定位并修正：① 判据不对称（`jump` 档单边跳过）② 透传形参
  （`OWNER_ARITY` 上界）③ 指令译码缺 `ldm*/stm*/smlal` ④ 锚点写死结论 → 状态感知 + 负向锚点。
- 收敛：`229 → 75 → 74 → 47 → 40 → 41`；**最终 HIGH 2 / LOW 39**。
- 剩余 HIGH 2 = `mui_DispBlock`（已裁决：两侧共有脆弱性，工厂 ≥22/99 处也不设 r3）。
- CI（`73ce2f81`）：`1to1-verify` / `rkgame-rebuild` / `1to1-qemu-behav` **全部 success**。


---

## 第四十三轮 ★ `mui_setting` 窄指针转型缺陷定案并修复（场景 E 首个"我们自己的"可修分歧）

### 一、判决性修复

| 项 | 内容 |
|---|---|
| 缺陷 | `src/proprietary/mui/FUN_0002b2b4_mui_setting.c` 两处 `(gh_byte *)*(gh_byte *)puVar15` |
| 本质 | 多一层窄转型 ⇒ 编译器发射**字节读** ⇒ 取到**指针低字节**（0..255）当指针用 |
| 证据 | 工厂 `2b490: ldr r2,[r6,#4]!`（取**字**）vs 我们 `ldrb r1,[r1,#4]`（取**字节**） |
| 现场 | 崩溃 `pc=mui_outputxy_t+0x84`、故障指令 `ldrb sl,[r2]`、**故障地址 0x80**、`r2=arg6=0x80` |
| 吻合度 | 该槽指针低字节 = `0x80` ⇒ **与崩溃值逐位匹配** |
| 修法 | `(gh_byte *)*puVar15`（取字=指针）；本地重编+重链后机器码 `ldrb→ldr` ✓ |

### 二、两处「假分歧」定案（都反转了我此前的判断）

1. **`ClearBuffer` 在 A/B/C/E 全部 4 场景"仅工厂执行"** ⇒ 实为**内联 vs 外联**的编译产物：
   我们把它内联成 `memset`/`vst1.32`，**尺寸多重集与工厂完全相同**
   （工厂 8 次调用 `[2032,56,328,284,4624,840,6944,8708]`；我们 `[28+2004,56,328,284,4624,840,6944,8708]`）。
2. **`mui_setting -> mui_outputxy_t` 的 `bl` 数 13 vs 8** ⇒ 实为 clang 的 **cross-jumping**：
   源码级两侧都是 13 处；我们把 `sub r2,#10`/`sub r2,#6` 合并成一处（`mvn r7,#9`+`mvneq r7,#5`）。

### 三、两道新硬门禁（`1to1-verify` 现 **10 道 ★**）

- `tools/scan_call_counts.py`：**逐函数调用点个数对拍（源码级）**。
  自证 = 正向 2 条（`mui_setting→mui_outputxy_t` 13/13、`get_items_from_zipfile→FindZipItemA` 1/1）
  + **负向 4 条**（`openzipu→operator_new` 2/2 等，证明 mangled 名归一化真的生效）。首跑 **0 项**。
- `tools/scan_narrow_deref.py`：**窄指针转型 + 解引用**。判据收窄至 `(窄*) *(窄*)`（首版误报 13/15）；
  构造性自证 3 危险 + 6 安全；反向验证命中恰好 2 行。首跑 **0 项**。

### 四、仪器/纪律修正

- **`--tag` 空值导致场景 A 覆盖率从未产出**（argparse 直接退出，脚本只打 `[note]`）⇒
  改为仅在非空时追加 + 覆盖率失败升级为 **`::error::` 注解 + 打印工具输出前 12 行**。
- 执行集合差集在 4 场景全部产出（A/B/C/E）；**A 的报告名是 `coverage_*.stdout.txt`**，CI 已兼容。

### 五、当前"仅我们执行"清单（E 场景，修后待复测）

`UnzipItem` / `get_item_from_line` / `mui_DispBlock` / `mui_outputxy_t` / `strtrim{,l,r}` ——
它们都是**下游**：因为我们 `ui.cfg` 查找成功（工厂失败、已归因环境）⇒ 解析出内容 ⇒ 走到渲染。
修掉窄解引用后应能继续前进，需下一轮 CI 复测确认。


---

## 第四十三轮·补

### 九·补八 ★ 修复后实测：崩溃点**前移一大步**（从"参数垃圾"进到"真实字形渲染"）

修复 `(gh_byte *)*(gh_byte *)puVar15` 后同一场景（E）的崩溃现场：

| | 修前 | **修后** | 工厂（对照） |
|---|---|---|---|
| 崩点函数 | `mui_outputxy_t+0x84` | **`stbtt_FindGlyphIndex+0x8`** | `mui_setting+0x114` |
| 调用者 | — | `stbtt_GetCodepointBitmapBoxSubpixel+0x2C` | — |
| 故障指令 | `ldrb sl,[r2]`（读字符串首字节） | 解引用 `[r3+4]`（字形表查找） | `ldrh r0,[r3,#4]`（图像描述符） |
| 故障地址 | **0x80**（= arg6 低字节） | **0x4**（= NULL + 4） | **0x4** |

**读法**：修前我们崩在"**传进来的参数本身是垃圾**"（`0x80`）；修后已进到
**真正的字形渲染**（`stbtt_FindGlyphIndex` 里访问 font 表），崩因是
`mui_InitFont` 失败（`find font.ttf in …ui_cn.zip fail`，**两侧都打印**）导致 font 指针无效。
⇒ **这一处是我们自己的缺陷，已修死**；剩下的分歧属"环境缺 `font.ttf`/SFC 安全数据"那一类
（工厂同样在此区域崩溃，只是崩点函数不同）。

**仍存的真实分歧**（E 场景门禁 FAIL 的具体项）：
`[FAIL] B2 events 可判定前缀 20/59 行一致；重建侧共 58 行 ★ 未到达参考侧的确定性前缀（提前终止）`
—— 我方 stdout 21 行 vs 工厂 23 行，差的正是两条 find-fail
（`find ui.cfg … fail` 我们**没有**，因为查找成功；`find setting.raw fail` 我们**没走到**）。

### 九·补九 门禁首跑在 CI 上红（本地绿）—— 缺"目录不存在即跳过"守卫

`tools/scan_call_counts.py` 依赖本机 Ghidra 反编译目录（本机产物、不进仓库）。
首跑 CI 时该步骤直接 `[FATAL] 索引为空` 退出 ⇒ 打红。已按 `tools/scan_call_args.py` 的既有做法
加 `[SKIP]` 优雅跳过（本地模拟 CI：`--ghidra D:/no_such_dir` ⇒ SKIP、退出 0 ✓；
正常路径仍 213 对可比对、PASS）。
**纪律**：任何依赖**本机产物**的门禁，都必须显式处理"产物缺席"，并**打印 SKIP 原因**而不是静默/报错。


### 第四十三轮补：修复后崩溃点前移入真实字形渲染；门禁补 CI 守卫

- 修复 `(gh_byte *)*(gh_byte *)puVar15` 后，场景 E 崩溃点从
  `mui_outputxy_t+0x84`（故障地址 **0x80** = arg6 低字节）**前移到**
  `stbtt_FindGlyphIndex+0x8`（调用者 `stbtt_GetCodepointBitmapBoxSubpixel+0x2C`，故障地址 **0x4**）
  ⇒ 已从"参数本身是垃圾"进到**真实字形渲染**；崩因变为 `mui_InitFont` 失败导致 font 无效
  （两侧都打印 `find font.ttf … fail`）⇒ 属环境缺口那一类。
- E 门禁仍 FAIL，具体项：`可判定前缀 20/59 行一致；重建侧 58 行，未到达参考侧确定性前缀`；
  stdout 我们 21 行 vs 工厂 23 行，差的正是 `find ui.cfg … fail`（我们查找成功）与
  `find setting.raw fail`（我们没走到）。
- **门禁 CI 守卫**：`scan_call_counts.py` 依赖本机 Ghidra 目录（不进仓库）⇒ 首跑 CI 时
  `[FATAL] 索引为空` 打红。已加 `[SKIP]` 优雅跳过（本地模拟验证 ✓）。
  纪律：依赖本机产物的门禁必须**显式处理缺席并打印原因**。


---

## 第四十四轮 ★ `setting.raw` 判决（在包里、我们读对） + 关键地址命中普查定案工厂侧失败分支

### 一、判决性证据

| 证据 | 内容 |
|---|---|
| 我们侧探针（已撤） | `DBGUI2 req=setting.raw zr=0 HIT size=2857048` |
| `ui_cn.zip` 真实条目 | 6 个，其中 **`setting.raw` = 2,857,048 B** ⇒ 与我们读出的**逐字节一致** |
| 工厂侧 | `find ui.cfg … fail` / `find font.ttf … fail` / `find setting.raw fail`（对**存在**的条目全部失败） |

### 二、★ 关键地址命中普查（新 CI 设施 `CGM_TRACE_ADDRS`）

在 `-d exec` 原始日志被删之前统计目标地址命中（制品只留尾部 800 行，覆盖不到）：

| 地址 | 含义 | 工厂命中 |
|---|---|---|
| `000119f4` | `unzLocateFile` 的 -99 早退（`unz->[24]==0`） | **1** |
| `0001162c` | `unzGoToFirstFile` 入口 | **1** |
| `00010ea0` | `unzStringFileNameCompare` | **0** |
| `000115ec` | `unzGetCurrentFileInfo` | **0** |

⇒ 一次调用在 `[24]==0` 处**早退**；另一次**通过检查**但 `unzGoToFirstFile` **返回非 0**
⇒ **遍历体零执行**（从未比过任何名字）。
⇒ **工厂侧 zip 条目查找在沙箱里坏在"中央目录遍历"这一层**；我们的实现（已逐指令核对，
同样含 `[24]==0 → -99`）在同一条件**全部成功** ⇒ 归因**沙箱环境缺一环**（真机由
`menu.log` 证明能打开资源包）⇒ **不影响 1:1 替代，保留为待真机对照项**。

### 三、本轮三处仪器/脚本层静默失效（全部已修 + 已上门禁）

1. `set -e` + `_n=$(grep -c …)` 无匹配返回 1 ⇒ 脚本整体退出（`trace_hits` 空、rebuild 侧没跑）。
   修：`|| true`。
2. YAML `run:` **注释插进 `\` 续行链** ⇒ 链断裂、后续变成独立命令 ⇒
   `CGM_KEY2_SEED`/`KEY2_HOOK`/`IO_TRACE`/`DBGUI2` **静默丢失** ⇒ 重建侧退回 `open … fail`，
   而**行为门禁假绿 PASS**。修：注释移出链 + 新门禁 `tools/lint_workflow_continuation.py`。
3. Python heredoc 里 `\\n` 被 Bash 工具折叠成真换行 ⇒ 含反斜杠的锚点永不匹配。
   修：一律 `chr(92)`。连带发现仓库有 **181 个 CRLF 文件** ⇒ 多行替换必须先做换行归一。

### 四、门禁与提交

`1to1-verify` 现 **11 道 ★ 硬门禁**（新增「工作流续行链 lint」+ 上一轮的「窄指针转型」「调用点个数」）。
本轮提交：`00e1cf68` → `6bd7e2dd`（set -e 修复）→ `332d96c7`（续行链修复 + lint 门禁）→ 本轮文档。

---

## 第四十五轮（2026-09-18）：C++ 包装层对齐 + 一处自我更正 + 第 12 道硬门禁

### 一、★ 自我更正：`TUnzip::Find` **不缺** `unzCloseCurrentFile`（第 44 轮结论作废）

第 44 轮报的"独立缺陷"是**错的**：全 ELF 里 `bl unzCloseCurrentFile` 的调用者为 **0**，
但我们 `TUnzip::Find` 的尾部机器码（`ldr r7,[r8,#124]` → `free` → `inflateEnd` → `free`
→ `str r9,[r8,#124]`）与独立函数体**逐指令同构** ⇒ 同 TU 内联（与 `ClearBuffer` 同一物种）。
⇒ **判据回到机器码语义，不用"有没有 bl"**。

### 二、两处真差异（均已修，机器码级验证）

| # | 差异 | 工厂 | 我们（改前） | 修法 |
|---|---|---|---|---|
| 1 | `TUnzip::Find` 多余的 264 B 栈拷贝 | `bl unzLocateFile` 前 r1 从未被写（透传） | `bl strcpy` + `sub sp,#264` | 删除本地缓冲 ⇒ `0x120→0x100`，`strcpy`/`#264` 消失 |
| 2 | `unzOpenCurrentFile` 参数个数 | `_Z18unzOpenCurrentFileP5unz_s`（单参） | `_Z18unzOpenCurrentFileP5unz_sPKc`（双参） | 定义/声明/2 调用点收成单参 ⇒ mangled 名**完全一致** |

### 三、第 12 道硬门禁：C++ mangled 签名对拍

`tools/scan_cxx_abi.py`（Itanium ABI：参数个数与类型全在 mangled 名里，与编译器无关）。
归一化 `.isra/.part/.constprop/.cold/.llvm`；排除 `_ZL/_ZZ`；判据收窄到"共有名字的签名不一致"；
"仅一侧有"列入棘轮。自证 3+1，**反向验证**：改前版 `.o` 入链接 ⇒ 精确报出唯一一条并 `exit 1`。
**首跑：共有 62 个名字，签名不一致 = 0**。

### 四、新发现（入台账）：我们独有 5 个 C++ 函数

`Uupdate_keys` / `Udecrypt_byte` / `ucrc32` / `zdecode`（加密残留）+ `EnsureDirectory`
（工厂无 ⇒ 工厂疑似删掉了 `TUnzip::Unzip` 的 ZIP_FILENAME 分支）。
与 `TUnzip::Unzip` 尺寸 516 B vs 1600 B 互相印证 ⇒ 下一轮入口。

### 五、本地门禁回归（8 道全绿）

调用点个数 213 对 / 窄指针转型 0 命中 / 调用点实参 1279 对 / 上游 API 无新增（台账 14）/
**C++ 签名 0 不一致（独有 5）** / 续行链 lint 0 处 / shim 格式化器 12/12 / 实参寄存器台账 41 项。
链接门禁：全局符号 **193/194**、越界 **0**、GLIBC 上限 **2.7**。

### 六、提交

`eefe0a68`（6 blob：workflow + unzip.cpp + XUnzip.o + .XUnzip 源哈希 + 新工具 + 新台账）。

---

## 第四十六轮（2026-09-18）★★ 修掉一个"门禁全绿但功能为零"的真实缺陷

### 一、★ 缺陷本体

`TUnzip::Unzip` 两侧签名**完全一致**，但工厂**从不读 `len`**：
- 工厂 memory 路：`unzReadCurrentFile(uf, dst, 16384)` **循环推进 dst**（`1285c: mov r2,#16384` /
  `12868: add r6,r6,r2`）；
- 我们（上游语义）：`unzReadCurrentFile(uf,dst,len)` **只读一次**，`res>0` 返 `ZR_MORE`；
- 而**全部 15 个专有调用点都传 `len==0`**（`UnzipItem(hz,idx,malloc(条目大小),0,3)`）
  ⇒ `unzReadCurrentFile(...,0)` **一个字节都不写**、返回 `res==0` ⇒ 我们返回 **`ZR_OK`（假成功）**；
- ⇒ UI 包 / 字体 / 设置 / 缩略图 / 存档等**所有资源解压都拿到空缓冲**。

判定为真差异的三条独立证据：① 工厂 `UnzipItem` 把 `len` 原样转发，而调用点都传 0（若工厂读 len 则资源永不成功，与"真机可跑"矛盾）；
② 工厂 memory 路用的是**常量** 16384；③ 每个调用点都 `malloc(条目大小)`（否则分配无意义）。

### 二、修复 + 清理

- `TUnzip::Unzip` 重写为与工厂逐分支一致（memory 路 16384 循环；文件路改 `fopen/fwrite/fclose`，
  去掉 `EnsureDirectory`/`CreateFile`/`WriteFile` 与目录项特判）。
- 删掉 5 个「工厂没有的 C++ 符号」：`EnsureDirectory`、加密簇 `Uupdate_keys`/`Udecrypt_byte`/`zdecode`、
  以及重复的 C++ 版 `_Z6ucrc32`（改绑 C 符号 `ucrc32`，与工厂调用图一致）。
- ⇒ C++ ABI 门禁：**「0 不一致 / 独有 5」→「0 不一致 / 独有 0」**。

### 三、验证

5 符号消失 ✓｜`bl ucrc32`×2 与工厂一致 ✓｜memory 路 `#16384` 循环 ✓｜调用方 `malloc(条目大小)` ✓｜
尺寸 `0x640 → 0x550`（工厂 `0x204`）｜本地 8 道门禁 PASS｜链接 193/194、越界 0。

### 第四十六轮·补：运行期铁证 + 续行链第二种破坏形态

**① 运行期证据（`CGM_DBGUNZ`，场景 E）**

```
DBGUNZ req=setting.raw size=2857048 sum=6830339 nz=65512 head=50 00 00 00 00 05 d0 02
```

前 64 KiB 中 **65,512 字节非零**（99.96%）⇒ 缓冲区**真被写满**（修复前必然 `sum=0/nz=0`）。
场景 E 重建侧 stdout **21 → 22 行**（工厂 23）；A/B/C 仍 PASS、E 仍 FAIL(1)。
CI 三 workflow 全绿（12 道 ★ 门禁）。

**② 续行链形态 ②（本轮第二次被同一类问题咬）**

把 `CGM_DBGUNZ=1` 追加到**已以 `\` 结尾的行后面** ⇒ `\ ` 被当转义空格 ⇒ 赋值词切碎 ⇒
CI 报 `CGM_DBGUNZ=1: command not found`，**真正的脚本没执行**（`report/qemu_e` 整目录缺失），
而 step 因 `|| true` 仍 ✓。
**修**：环境变量加在最后一个 `\` 之前。**门禁**：`lint_workflow_continuation.py` 加判据 ②
（`(?<!\\)\\[ \t]+NAME=` 且行尾 `\`），自证 2 坏 + 6 好；修前命中、修后归零。

## 第四十七轮：缺原型 = ABI 级错位（D1）+ `fontscale` 类型错（D2）+ 第 13 道门禁

### 一、本轮修的两个真缺陷

| # | 缺陷 | 修复前 | 修复后 |
|---|---|---|---|
| D1 | stb 调用**缺原型** ⇒ 隐式声明 ⇒ float 按 double 传、`r0` 未设 | 崩在 `stbtt_FindGlyphIndex+0x8`（`ldr r4,[r0,#4]`，故障地址 **0x4**，r0=0）| 调用点形状与工厂一致（`r0=&font`、`s0..s3` 传 float）|
| D2 | `fontscale` 写成 `unsigned int`（真为 `float`）| `vcvt.u32.f32` **截断** ⇒ scale 恒为 0 | `vstr s0,[..]` float 直存，与工厂 `vstr s0,[r5,#672]` 同形 |
| — | `proto.h` 漏声明 `shmat` | 返回类型被假定 `int` | 补 `void *shmat(int,const void*,int)` |

### 二、新门禁（第 13 道 ★）

`tools/scan_implicit_decl.py`：**编译器真值**口径（逐文件 `-fsyntax-only`），自证正负双向，
台账棘轮。首跑 213 个文件检出 1 个（`shmat`）⇒ 补掉后 **0 项**；串行 70s → 并行 20.5s。
★ `--jobs 8` 在本机触发 `WinError 1455`（页面文件）⇒ 默认 4；**派生失败必须 FATAL**。

### 三、两处归因修正

1. 「`key2` 被某处覆写」**撤回**：场景 E 崩溃时 key2 仍是注入值 `50 4b 05 06 50 4b 07 08`。
2. 工厂 zip 查找失败**仍归因沙箱**，但理由换成：分支普查显示遍历循环体**零执行**
   （`unzStringFileNameCompare` / `unzGetCurrentFileInfo` 命中 0）⇒ `unzGoToFirstFile` 返回非零。

### 四、门禁与状态

- `1to1-verify` 现 **13 道 ★**；本地 8 道全绿；链接 193/194、越界 0。

### 第四十七轮·补 ★★ M7「菜单存活」首次达成

| 指标 | 工厂 | 我们 | 控制组 |
|---|---|---|---|
| M7 菜单存活 | X | **v（首次）** | X |
| 崩溃 / exit_code | SIGSEGV 139 | **0 次崩溃 / 124（存活至超时）** | 139 |
| 专有函数覆盖 | 51/223 | **68/223** | 51/223 |
| A/B/C 回归 | — | 48 / 48 / 6（无回归） | — |

- 三条"活着而非自旋"的否定证据：stdout 23 行无重复、末行停在输入设备打开、
  io 轨迹走到 `/dev/input/js0` + `/proc/bus/input/devices` + `joystick.zip`（等待输入是预期行为）。
- 场景 E 现在的 B1/B2 失败**方向**是"参照侧崩、我们存活"（已让 `behav_diff.py` 自动标注）。
- 新增执行覆盖：`ReadJoystick`/`ReadUSBJoy`/`GetInputInfo`/`mui_WaitNMI`/`dispFlip` 等 18 个。
- 第 14 道 ★ 门禁：`proto.h` 声明 vs 上游真签名对拍（台账 1 项 = `UnzipItem` 厂商扩展）。

## 第四十八轮（2026-09-19）：打开输入子系统（场景 F）+ 方向标注 + 一处误导性证据修正

### 一、为什么这一轮攻输入

第 47 轮拿到 M7（菜单存活）后，stdout 停在 `js0 Opened!`。查到最底：
shim 把 `/dev/input/*` 重定向到 `/dev/zero` ⇒ `ReadUSBJoy` 的 `read(fd,buf,8)` 读回 8 个**零**字节
⇒ `type=0`（既非 BUTTON(1) 也非 INIT(2)）⇒ 直接 `return` 旧值 ⇒ **菜单永远收不到输入**。
代价：`mui` 模块（42 函数 / 70,396 B = **重构量 57%**）零覆盖。

### 二、实现：shim 把 `/dev/input/jsN` 变成内存事件源

| 项 | 内容 |
|---|---|
| 手段 | 命中 `/dev/input/js<N>` 且 `CGM_INPUT_HEX` 非空时，`memfd_create` 造内存 fd + 预置 `js_event` 字节流 + `lseek` 回 0 |
| 关键取舍 | **不拦 `read`/`write`** ⇒ guest 读语义 100% 原生，也不牵扯 stdio 内部（已踩过 stdio 再入的坑） |
| 顺带 | 接管 `access()`（guest 确实导入），把"设备节点是否存在"从宿主文件系统状态变为显式可控 |
| 注入内容 | `0000000001000100`（value=1,type=1,number=0 ⇒ 按下 button 0）× 4；EOF 后返回旧值 ⇒ 等价"持续按住"，配合 Delay 连发（`0x27` 阈值）覆盖整个运行窗口 |
| 公平性 | 两侧共用同一 shim + 同一脚本 ⇒ 差分公平；仅在 `CGM_INPUT_HEX` 非空时生效（默认关） |
| 导出核对 | `access`/`open`/`open64`/`openat`/`fopen`/`fopen64`/`mmap`/`munmap` **均已导出**；`read` **不在表内** |

### 三、场景 F（观测项，`|| true`）

`SYSROOT=/arm-root CGM_WORK=/sdcard/cubegm CGM_TIMEOUT=30 CGM_KEY2_SEED=1 CGM_KEY2_HOOK=1
CGM_IO_TRACE=1 CGM_COV_TAG=F CGM_INPUT_HEX=<64 字符> sh tools/ci_qemu_behav.sh ... report/qemu_f`

制品路径已加 `1to1/report/qemu_f/`；`1to1-qemu-behav` 现 **5 个场景**（A/B/C/E/F）。

### 四、附带修掉两处（仪器可信度）

1. **`behav_diff.py` 新增方向标注**（文档此前已承诺、代码里却没有 ⇒ 本轮让文档成真）：
   `方向：**重建侧更健康**：参照侧 exit=139 疑似异常终止，重建侧 exit=124（超时被杀 ⇒ 一直运行）`
   + `△ 疑似参照侧环境缺口`。已用**真实制品**验证：E 出标注、A（PASS）不出。
2. **shim 的 key2 探针文案过时**：原写 `（注入值应为 50 4b 05 06 50 4b 06 06）`，那是第 42 轮
   **修正前**的错误值；正确注入值是 `PK\x05\x06 PK\x07\x08`。该文案会让读者把
   "现值 = 注入值"误读成"未生效"⇒ **误导性证据**（比没有证据更糟），已改为动态口径。

### 五、校验

- 本地：`behav_diff.py` 语法 + 用真实制品跑通（E=FAIL+方向标注 / A=PASS 无标注）；
  shim 重编成功（919,016 B，新文案在场、旧文案清除）；`ci_qemu_behav.sh` 语法 OK；
  workflow YAML 有效（13 步 / 5 场景）；续行链 lint **0 问题**。
- 门禁回归：见本轮末尾。

### 第四十八轮·补 ★ 场景 F 首跑 + 一次自我引入的事故（三场景静默失效）

**场景 F 首跑**（CI `86cb9e81` 三 workflow 全 success，制品 313 文件）：

| 观测项 | E | **F** |
|---|---|---|
| `js 输入注入已启用` | — | 两侧各一行（32 B / 4 个 js_event） |
| `open(js-inject)` | — | 我们侧 **js0..js3 全部**（fd 3/5/8/11）；工厂侧无（已在 E 崩溃） |
| 我们 stdout | 23 行 | **25 行**（多出 js1/js2/js3 `Opened!`） |
| 覆盖率 | 68/223 | **68/223（未变）** |
| 里程碑 | M7 ✓ | M7 ✓（无新增） |

⇒ **注入生效**（设备枚举从 1 个变 4 个），但**尚未驱动菜单逻辑**（覆盖率/里程碑未动）。
⇒ 副作用：我的 `access` 接管**过宽**（4 个 js 设备全变"在线"）⇒ 下一轮应限定到指定编号。

**★ 事故（我引入的）**：CI success，但 `qemu_b`/`qemu_e`/`qemu_f` 的 `behav_diff.txt` 末行全是
`json.decoder.JSONDecodeError: Invalid control character` ⇒ **三个场景判定根本不存在**。

- 根因：我改 key2 探针文案时写了 `PK\x05\x06`（**真转义**）⇒ 输出带 ENQ/ACK 控制字节
  ⇒ `behav_capture.sh` 收进 JSON ⇒ 非法 ⇒ `behav_diff.py` 抛异常。
- 为何没早发现：脚本只 `echo` 退出码不报错；且 B/E 是观测项（`|| true`）。

**修复三件**：
1. 文案改纯可打印（十六进制文本）；
2. **第 15 道 ★ 门禁** `tools/check_shim_charset.py`（扫字符串字面量的真控制字符转义；
   判据区分反斜杠奇偶；构造性自证 + **反向验证**）；
3. `ci_qemu_behav.sh`：`behav_diff` 退出码非 `0/2/3` ⇒ **`::error::` + `exit 1`**（仪器故障不再静默）。
