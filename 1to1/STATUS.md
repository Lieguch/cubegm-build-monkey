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
