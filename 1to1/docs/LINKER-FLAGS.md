# 链接器开关决策表（**规范推导，非试错**）

> 本文件存在的理由（2026-09-27，第 67 轮）：`-nostdlib` / `-nostartfiles` / `-z undefs`
> 这几个开关我此前是**用 CI 失败反推**的 —— 一轮 CI 只能排除一个猜想，代价 25 分钟/轮。
> 而 GCC 与 ld 的官方手册**逐字写明**了它们的语义。**凡链接/编译开关，先查手册再改代码。**
> 引用来源（2026-09-27 核对）：
> * GCC Link Options — <https://gcc.gnu.org/onlinedocs/gcc/Link-Options.html>
> * GNU ld Options — <https://sourceware.org/binutils/docs/ld/Options.html> 与
>   `-z` 选项 — <https://sourceware.org/binutils/docs/ld.html>

## 1. 三个"不要标准库"开关的确切语义（GCC 手册原文）

| 开关 | 手册原文（要点） | 影响 |
|---|---|---|
| `-nostartfiles` | "Do not use the standard system startup files when linking. **The standard system libraries are used normally**, unless -nostdlib, -nolibc, or -nodefaultlibs is used." | **只去掉 crt1/crti/crtbegin/crtend/crtn；`-lc` 等照常** |
| `-nodefaultlibs` | "Do not use the standard system libraries when linking... **The standard startup files are used normally**, unless -nostartfiles is used." | 只去掉 `-lc/-lgcc/...`；startfiles 照常 |
| `-nostdlib` | "Do not use the standard system startup files **or** libraries when linking." | **= `-nodefaultlibs` + `-nostartfiles`**；手册补一句：用了它"you should usually specify `-lgcc` as well" |

### 本工程为什么用 `-nostartfiles` 而不是 `-nostdlib`

本工程**自带 CRT**（`src/compat/crt_init.S` → 提供 `_init`/`_fini`）并在数据镜像里提供
`__dso_handle`。用**真 GCC + 真 glibc 2.24 sysroot** 链接时：

* BFD ld 会按 sysroot 自动拉 `crti.o`/`crtbegin.o` ⇒ 与本工程对象
  **`multiple definition of '_init'/'_fini'/'__dso_handle'`** ⇒ 链接 rc=1。
  ⇒ 需要 **`-nostartfiles`**（只要去掉启动文件，**保留 libc**）。
* 若改用 `-nostdlib` ⇒ 连 `-lc` 一起去掉 ⇒ **zig/lld 侧立刻全崩**
  （`ld.lld: error: undefined symbol: printf/malloc/sprintf/...`，实测）。

**⇒ 结论：`-nostartfiles` 是本工程需要的那个；`-nostdlib` 是过度手段，会引入新故障。**

## 2. "允许未解析符号"的两种写法（ld 手册原文）

| 写法 | 手册原文 | 备注 |
|---|---|---|
| `-z undefs` | "Do not report unresolved symbol references from regular object files, either when creating an executable, or when creating a shared library. This option is the inverse of `-z defs`." | **本文档核对的当前版 ld 支持**；但**旧 binutils 未必有**（本项目对照工具链是 binutils **2.27**）⇒ 用之前必须 `ld --help` 问工具自己 |
| `--unresolved-symbols=ignore-all` | "Determine how to handle unresolved symbols... '**ignore-all**' Do not report any unresolved symbols." | 语义等价，**出现得更早**，2.27 一定有 |

**⇒ 结论：跨链接器（lld / BFD ld）与跨版本时，用 `--unresolved-symbols=ignore-all`；
`-z undefs` 保留给 lld。两者同时给也无害（各自认得的那个生效）。**

### 规范里没有的、必须**问工具自己**的一条

```
<工具链>/bin/arm-…-ld --help | grep -i undefs
<工具链>/bin/arm-…-gcc -dumpspecs | grep -c nostartfiles
```
手册描述的是**当前版本**；对照工具链可能是**旧版本**（本项目是 GCC 6.3 + binutils 2.27）。
⇒ **规范给语义，`--help` 给该版本的事实。两者都要。**

## 3. 本工程的实际 flag 组合（按腿区分）

| 项 | zig/lld 腿 | 真 GCC/BFD 腿 | 依据 |
|---|---|---|---|
| CRT 启动文件 | 不加任何开关（lld 侧不冲突） | **`-nostartfiles`** | §1 |
| 未解析符号 | `-Wl,-z undefs`（脚本内置） | **`-Wl,--unresolved-symbols=ignore-all`** | §2 |
| 工厂同样拥有的库 | clang 驱动自动加 | **`-lm -lpthread -ldl`** | 工厂 ELF `DT_NEEDED` = `libz.so.1 libdl.so.2 libm.so.6 libstdc++.so.6 libpthread.so.0 libgcc_s.so.1 libc.so.6` |
| 严禁 | `-nostdlib` | `-nostdlib` | §1（会砍掉 `-lc`） |

外部传入通道：`link_full.sh` 的 **`EXTRA_LDFLAGS`**（默认空 ⇒ 主链行为逐字不变）。
