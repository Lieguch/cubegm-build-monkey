# 构建事实对齐 · 第二部分（2026-09-28）：工厂是 **per-TU 优化档**

> 本文件是 `BUILD-FACT-ALIGNMENT.md` 的续篇。
> 为什么单独成文：**C 盘满**导致沙箱"写入前备份"失败 ⇒ **既有文件被拒改**，只能新建。
> 见 `BLOCKERS-2026-09-28.md`。

---

## 一、决定性推论

真 glibc 2.24 里三个名字的**门控条件不同**：

| 名字 | 位置 | 形态 | 门控 |
|---|---|---|---|
| `putc` | `stdio.h:587` | **无条件宏** `#define putc(_ch,_fp) _IO_putc(_ch,_fp)` | **与优化档无关** |
| `putchar` | `bits/stdio.h:79` | `__extern_inline` | **仅 `__USE_EXTERN_INLINES`**（`__OPTIMIZE__ && !__OPTIMIZE_SIZE__` ⇒ **-Os/-O0 关、-O1+ 开**） |
| `strdup` | `string.h` | `__extern_inline` | 同上 |

工厂**同时**导入 `_IO_putc`（putc 宏产生）、**`putchar`**（⇒ extern-inline **关**）、**`__strdup`**（⇒ extern-inline **开**）。
⇒ 两者互相矛盾 ⇒ **工厂不可能是单一优化档**。

## 二、单变量实测（同一份源码，只改头文件与优化档）

| 源码 | zig 头 `-Os` | 真头 `-Os` | 真头 `-O2` | 工厂实际 |
|---|---|---|---|---|
| `upstream/mxml/mxml-file.c`（用 `putc`/`strdup`） | `putc`, `strdup` | `_IO_putc`, `strdup` | **`_IO_putc`, `__strdup`** | `_IO_putc`, `__strdup` ✓ |
| `proprietary/flash/FUN_0000ac44_UpdateROM.c`（用 `putchar`） | `putchar` | **`putchar`** | `_IO_putc` | `putchar` ✓ |
| `proprietary/misc/FUN_00016ebc_strupr.c`（用 `islower`） | `__ctype_b_loc` | `__ctype_b_loc` | `__ctype_b_loc` | 需 `islower`（**仍未复现，另案**） |
| `upstream/libcharset/localcharset.c`（`-O0` + 真头） | — | — | **`nl_langinfo`** | `nl_langinfo` ✓ |

⇒ 结论：**应用代码 `-Os`**（要 `putchar`）、**上游 mxml/stb 等 `-O2`**（要 `__strdup`）、
**libiconv `-O0`**（代码形态普查已定案：304/304 与 Thumb 同一集合）。

## 三、行为尺（唯一判据）实测

| 臂 | 配置 | 共有 / PASS / **DIVERGE** | 结论 |
|---|---|---|---|
| 基线 | 主链（zig 头；专有 `-Os` / 上游 `-O1`） | 782 / 732 / **45** | — |
| **B** | 真头 + **全 `-O2`** + `-fno-builtin-strcmp` | 782 / 731 / **46** | **无改善** ⇒ 反证"全 -O2" |
| **C** | 真头 + **per-TU**（应用 `-Os` / 上游 `-O2`）+ `-fno-builtin-strcmp` | **未测出** | C 盘满导致专有对象 **0/213** |
| A | 真头 + 现档 | 无效 | XUnzip 因 zig 缓存竞态未编出 ⇒ 链接失败（已改 fail-closed） |

★ 臂 B 的"无改善"本身就是有效结论：**它把"全 -O2"这条路证伪了**，与 per-TU 推论一致。

## 四、头集合的**顺序**（两次失败换来，不可随意调）

```
组件自己的 -I  →  GCC include  →  GCC include-fixed  →  sysroot/usr/include
```

| 失败 | 原文 | 原因 |
|---|---|---|
| 1 | `undefined symbol: libiconv_close` / `field has incomplete type 'struct iconv_fallbacks'` | `-I<glibc 头>` 排到组件自己的 `-I` **之前** ⇒ 盖住 libiconv 自己的 `iconv.h`（glibc 也有同名） |
| 2 | `error: function-like macro '__GLIBC_USE' is not defined` | 真 glibc `limits.h` 的 `#include_next` 跳进 **zig 自带的更新版 glibc `limits.h`**（`-nostdinc` **挡不住** zig 注入的内建头） |

（注：官方规范见 `BUILD-FACT-ALIGNMENT.md` 前文；本文件只补 per-TU 结论与行为尺对照。）

## 五、恢复后第一件事

`CACHE_TAG=C sh tools/buildfact_align_exp.sh C`
判据：① `.dynsym` 双向差集继续收敛；② **DIVERGE < 45**；③ `abi_check` / 体量 / UB 三道门禁仍 PASS。
若不达 ②，则按纪律回退（脚本不改主链；主链 `link_full.sh` 的配置由 `EXTRA_INC_TRAIL`/`UPOPT`/`LIBOPT` 旋钮控制）。
