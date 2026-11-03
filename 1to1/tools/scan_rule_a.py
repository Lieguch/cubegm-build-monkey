#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_rule_a.py —— 「Rule A：malloc 家族尺寸实参取自未初始化局部」硬门禁。

## 为什么需要它（R305，真机崩溃现场级已定案）

真机 0.2–0.4s 闪重启 = SIGSEGV（`si_code=1 MAPERR`，`si_addr=0x10001000` 野指针），
崩溃链 `mui_DisplayThumbnail → UnzipItem → TUnzip::Unzip → unzReadCurrentFile → inflate`。
根因 = 重建二进制里 **3 处 malloc 的尺寸实参取自从未赋值的局部**：

  · `mui/FUN_00014f84_mui_DisplayThumbnail.c`  `malloc(local_30)`          ⇒ 实为 malloc(0)
  · `core/FUN_00016f08_FilePreEmu.c`           `malloc(local_30 + 0x10)`  ⇒ 栈垃圾尺寸
  · `core/FUN_002b7510_run_game.c`             `malloc(local_30 + 0x10)`  ⇒ 栈垃圾尺寸

⇒ 分配尺寸与真实解压尺寸无关 ⇒ 16KB 块循环越界写 ⇒ 毁堆 ⇒ 崩。
工厂原厂二进制按 ZIPENTRY+296（`_296_4_`）分配；R305 已逐条对齐修正。

本门禁把**这一类缺陷**固化，防止回归。

## 口径：编译器真值 + 源码跨度窄化（两级）

### 第一级 —— 编译器真值：`clang -Wuninitialized`
不用源码启发式（"找没有初始化的声明"）：
  · 源码启发式要维护巨量白名单（入参寄存器别名 `in_d0`、宏、外部赋值），必然假阳性；
  · 编译器能沿 CFG 判断"这个变量在此处是否被赋值"。

⚠ 实测（2026-11-03，CNB 云开发，ziglang 0.16.0）：
  `-fsyntax-only` **不可用** —— zig 0.16.0 的 cc 驱动报 `error: FileNotFound`
  且 **rc=1**、**一个诊断都不出**（既有模板 `scan_implicit_decl.py` 用的正是
  `-fsyntax-only`，见 R306 记录）。必须用 `-c -o <tmp>` 才拿得到真诊断。

### 第二级 —— 窄化到「未初始化变量出现在 malloc 家族调用的实参区」
（连系法与编译器列号无关，见文末「实现要点 1」；语义等价于"诊断点落在实参括号内"。）
实测全树 `-Wuninitialized` 命中 **6 个 TU**，其中**只有 3 个真是 Rule A**
（= R305 修掉的那 3 处）；另 3 个是**同族但不同类**的未初始化使用：
  · `input/FUN_0000b014_TestUSBJoy.c:71`   printf 实参（Ghidra 拆栈缓冲的别名）
  · `misc/FUN_00029b44_progress.c:18`      加法右值（`in_d0` = 入参寄存器别名，编译器不可见）
  · `misc/FUN_002b4e20_gpsp_unzip.c:32`    return 值（而非分配尺寸）
⇒ 直接用 `-Wuninitialized` 全量门禁，这 3 个会变成**永久噪声红灯**，
门禁很快会被 `continue-on-error` 化掉而失去意义（本项目反复吃亏于"仪器被静默降级"）。
故：诊断点必须落在 malloc 家族（malloc/calloc/realloc/aligned_alloc/
memalign/valloc/posix_memalign）调用的**实参区**内，才算 Rule A。

## 地面真值校验（R306，CNB 云开发实测）

| 树 | `-Wuninitialized` 命中 TU | Rule A 命中 | 判读 |
|---|---|---|---|
| R259（**修复前**镜像） | 6 | **3** | 恰为 R305 修的 3 处 ⇒ 仪器正确 |
| R305f（修复后 GitHub main） | 3 | **0** | 修完即 0 ⇒ 棘轮可用 |

⇒ 仪器在**已修复**与**未修复**两侧都得到正确答案，不是只会报红的噪音门禁。

## 台账棘轮

`--ledger` 每行一条 `relpath:line:var`。
  · **新增命中 ⇒ 失败**（红灯）；
  · 台账条目不再命中 ⇒ 仅告警（提示删行，防"源码已修但 CI 用旧账"的假绿）。

## fail-closed

任何 TU 编译失败（rc≠0）⇒ **FATAL**。
绝不允许把"编译失败"当成"无命中"——那会让门禁在不完整输入上给绿色。
确需豁免的 TU 写入 `--skip` 文件并附理由（每行一条，`#` 注释）。

## 实现要点（R306 修掉的 3 个真实缺陷，勿回退）

1. **不能用编译器的列号做定位**（R306 实测踩坑）：clang 的 `-Wuninitialized` 列号
   **并不总是指向变量**。实测三例：`pos.c:3:65` 指向 `malloc` 的 `(`、
   `pos.c:4:64` 同样指向 `(`、而真实代码 `FilePreEmu.c:105:28` 指向 `malloc` 的
   **最后一个字母** `c` —— 三例各不相同 ⇒ 按列号做字节偏移比对会**漏报**
   （自证当场抓到「2 个正向样本只中 1 个」）。
   ⇒ 改用**与列号无关**的连系法：**诊断行与分配调用的行区间相交，且该变量名
   （整词）出现在调用实参文本内**。编译器只负责判「是否未初始化」，
   源码只负责判「是否在分配实参里」——各司其职，不猜列号语义。
2. **并行共享输出文件会竞态**：`-c -o <同一文件>` 在多线程下互相覆盖 ⇒ 编译产物损坏、
   rc 随机非 0。故**每个 TU 用独立输出文件**。
3. **`zip(files, ex.map(...))` 的元组嵌套**：map 已返回 `(f, result)`，
   再 zip 会得到 `r=(f, result)` ⇒ `r.get()` 抛 AttributeError。已改为直接用 map 的结果。
4. **正则必须加 `re.MULTILINE`**（R306 实测踩坑，最隐蔽的一个）：
   诊断正则以 `^` 开头锚行首，而 `re.finditer` **默认 `^` 只匹配整个输出的开头**，
   不加 `re.MULTILINE` 时 ⇒ 一个 TU 里**只有第一条诊断**能被解析，
   其余全部**静默丢失** ⇒ 门禁**漏报**且看起来一切正常（假绿）。
   实测症状：自证样本 2 个正向只中 1 个（第一个），第二个（同文件第二条诊断）丢失。
   ⇒ 三条诊断正则（RE_WARN / RE_MAYBE / RE_ERR）**一律加 `re.MULTILINE`**。

用法：
    python3 tools/scan_rule_a.py --root . --zig "$ZIG" --ledger tools/rule_a_pending.txt
"""
import argparse
import bisect
import os
import re
import shutil
import subprocess
import sys
import tempfile

# ─────────────────────────────── 编译真值口径 ───────────────────────────────
FAMILY = ("malloc", "calloc", "realloc", "aligned_alloc",
          "memalign", "valloc", "posix_memalign")

RE_FAMILY = re.compile((r"\b(" + "|".join(FAMILY) + r")\s*\(").encode("ascii"))

# clang 措辞随版本变化，两种都收（PAT_WARN 允许 warning/error 前缀）
RE_WARN = re.compile(
    rb"^(?P<f>[^:\n]+):(?P<line>\d+):(?P<col>\d+):\s+"
    rb"(?:warning|error):\s+variable\s+'(?P<var>[A-Za-z_]\w*)'\s+"
    rb"is uninitialized when used here", re.MULTILINE)
RE_MAYBE = re.compile(
    rb"^(?P<f>[^:\n]+):(?P<line>\d+):(?P<col>\d+):\s+"
    rb"warning:\s+variable\s+'(?P<var>[A-Za-z_]\w*)'\s+"
    rb"may be used uninitialized", re.MULTILINE)
RE_ERR = re.compile(rb"^(?P<f>[^:\n]+):(?P<line>\d+):(?P<col>\d+):\s+error:",
                     re.MULTILINE)

# 正向样本：必须检出
SELF_BAD = b"""#include <stdlib.h>
#include <stddef.h>
void rule_a_bad_plain(void)   { size_t ze_z_1; void *p = malloc(ze_z_1); (void)p; }
void rule_a_bad_offset(void) { size_t ze_z_2; void *p = malloc(ze_z_2 + 0x10); (void)p; }
"""
# 负向样本：已初始化 / 常量 / 形参 / 分支全赋值 ⇒ 必须不检出
SELF_GOOD = b"""#include <stdlib.h>
#include <stddef.h>
void rule_a_ok_init(void)      { size_t n = 296; void *p = malloc(n); (void)p; }
void rule_a_ok_const(void)     { void *p = malloc(296); (void)p; }
void rule_a_ok_param(size_t n) { void *p = malloc(n); (void)p; }
void rule_a_ok_assigned(size_t n) {
    size_t v; if (n > 2) { v = 296; } else { v = 304; }
    void *p = malloc(v); (void)p;
}
"""
# 形态分离样本：未初始化使用**不在** malloc 实参区 ⇒ 必须不被判为 Rule A
SELF_OTHER = b"""#include <stdio.h>
#include <stddef.h>
int  rule_a_other_return(void) { size_t v; return (int)v; }
void rule_a_other_printf(void)  { int w; printf("%d", w); }
"""


def find_zig(explicit=None):
    """定位 zig（CI 上由 pip 装在 site-packages、**不在 PATH**）。"""
    if explicit:
        return explicit
    c = shutil.which("zig")
    if c:
        return c
    try:
        import ziglang
        p = os.path.join(os.path.dirname(ziglang.__file__), "zig")
        if os.path.exists(p):
            return p
    except Exception:
        pass
    return "zig"


def cc_flags(root, outfile):
    """与 CI 口径一致；**不用 -fsyntax-only**（zig 0.16.0 下 rc=1 且零诊断）。

    `-c -o <独立文件>` 才拿到真诊断；产物落 tmpdir 并及时清理（.o 不入库）。
    ★ outfile 必须**每个 TU 独立** —— 共享同一路径在并行下会互相覆盖。
    """
    return ["-c", "-o", outfile,
            "-I", os.path.join(root, "src", "compat"),
            "-target", "arm-linux-gnueabihf",
            "-mfloat-abi=hard", "-mfpu=neon",
            "-Wall", "-Wextra"]


# ───────────────────────── 第二级：malloc 实参区定位（字节口径） ─────────────────────────
def strip_c_bytes(src):
    """把注释与字符串/字符字面量**原位**替换成等长空格（**字节** 1:1）。

    必须做：源注释里出现 `malloc(local_30)` 字样时，若不去掉会造出假跨度。
    """
    out = bytearray(src)
    i, n = 0, len(src)
    state = None          # None | line | block | str | chr
    while i < n:
        c = src[i:i + 1]
        if state is None:
            if c == b"/" and src[i + 1:i + 2] == b"/":
                out[i] = out[i + 1] = 32
                i += 2
                state = b"line"
                continue
            if c == b"/" and src[i + 1:i + 2] == b"*":
                out[i] = out[i + 1] = 32
                i += 2
                state = b"block"
                continue
            if c == b'"':
                out[i] = 32
                i += 1
                state = b"str"
                continue
            if c == b"'":
                out[i] = 32
                i += 1
                state = b"chr"
                continue
            i += 1
            continue
        if state == b"line":
            if c == b"\n":
                state = None
            else:
                out[i] = 32
            i += 1
            continue
        if state == b"block":
            if c == b"*" and src[i + 1:i + 2] == b"/":
                out[i] = out[i + 1] = 32
                i += 2
                state = None
                continue
            if c != b"\n":
                out[i] = 32
            i += 1
            continue
        q = b'"' if state == b"str" else b"'"
        if c == b"\\" and i + 1 < n:
            out[i] = 32
            if src[i + 1:i + 2] != b"\n":
                out[i + 1] = 32
            i += 2
            continue
        if c == q:
            out[i] = 32
            i += 1
            state = None
            continue
        if c != b"\n":
            out[i] = 32
        i += 1
    return bytes(out)


# ★★★ 各分配函数的「尺寸实参」在实参列表中的下标（0-based）。
#
#   malloc(size)                      calloc(nmemb, size)
#   realloc(ptr, size)                aligned_alloc(size, alignment)
#   memalign(alignment, size)         valloc(size)
#   posix_memalign(&p, alignment, size)
#
# ★ 为什么必须区分：Rule A 的定义是「**尺寸**实参取自未初始化局部」。
#   把 nmemb / alignment 也当尺寸 ⇒ `calloc(n, size)` 里 n 未初始化就会误报，
#   `posix_memalign(&p, align, size)` 里 align 未初始化也会误报 ⇒ 假阳性。
#   （glibc 的 memalign 原型是 memalign(alignment, size) ⇒ 尺寸是**第 2**个。）
SIZE_ARG_IDX = {
    "malloc": 0, "calloc": 1, "realloc": 1, "aligned_alloc": 0,
    "memalign": 1, "valloc": 0, "posix_memalign": 2,
}


def alloc_calls(clean):
    """返回每个分配调用的 (函数名, 左括号偏移, [各**顶层**实参区间])。

    ★ 必须按**顶层逗号**切分实参：括号/方括号/花括号内的逗号不算分隔符，
      否则 `malloc(a, f(b, c))` / `malloc(v[1], 2)` 会被切错。
    ★ 字符串与注释已在 strip_c_bytes 里抹成等长空格 ⇒ 里面的逗号不会干扰。
    """
    out = []
    n = len(clean)
    for m in RE_FAMILY.finditer(clean):
        name = m.group(1).decode("ascii")
        open_pos = m.end() - 1          # '(' 的字节下标
        depth = 0
        close_pos = None
        i = open_pos
        while i < n:
            ch = clean[i:i + 1]
            if ch == b"(":
                depth += 1
            elif ch == b")":
                depth -= 1
                if depth == 0:
                    close_pos = i
                    break
            i += 1
        if close_pos is None:
            close_pos = n - 1
        args = []
        depth = 0
        start = open_pos + 1
        for j in range(open_pos + 1, close_pos):
            ch = clean[j:j + 1]
            if ch in (b"(", b"[", b"{"):
                depth += 1
            elif ch in (b")", b"]", b"}"):
                depth -= 1
            elif ch == b"," and depth == 0:
                args.append((start, j))
                start = j + 1
        args.append((start, close_pos))
        out.append((name, open_pos, args))
    return out


def size_arg_spans(clean):
    """返回每个分配调用的**尺寸实参**区间 [(函数名, start, end)]（闭区间）。"""
    out = []
    for (name, _open_pos, args) in alloc_calls(clean):
        idx = SIZE_ARG_IDX.get(name, 0)
        if idx < len(args):
            s, e = args[idx]
            out.append((name, s, e))
    return out


def alloc_arg_spans(clean):
    """返回每个分配调用**实参区**的字节区间 [(start_off, end_off)]（闭区间）。

    start_off = 开括号后一字节；end_off = 闭括号字节。
    """
    spans = []
    for m in RE_FAMILY.finditer(clean):
        open_pos = m.end() - 1          # '(' 的字节下标
        depth = 0
        i = open_pos
        n = len(clean)
        while i < n:
            ch = clean[i:i + 1]
            if ch == b"(":
                depth += 1
            elif ch == b")":
                depth -= 1
                if depth == 0:
                    spans.append((open_pos + 1, i))
                    break
            i += 1
        else:
            spans.append((open_pos + 1, n - 1))
    return spans


def line_starts(b):
    """每行起始字节偏移；index[0]=0，index[i]=第 i+1 行起点。"""
    idx = [0]
    p = b.find(b"\n")
    while p != -1:
        idx.append(p + 1)
        p = b.find(b"\n", p + 1)
    return idx


def top_level_blocks(clean):
    """文件级大括号块（函数体 / 结构体体）的字节区间 [(start, end)]。

    ★ 为什么需要：clang 的 `-Wuninitialized` 只报变量的**第一次**使用处，
      而那次使用**未必**在 malloc 调用里。
      实测（R306）：`FUN_00016f08_FilePreEmu.c` 的诊断在 105 行
      （`ZIP_BUF_SIZE = local_30;`），而真正的 `malloc(local_30 + 0x10)`
      在 **106 行** ⇒ 按「诊断行」连系会**漏报**。
      ⇒ 连系范围必须放大到**所在函数体**。
    """
    out = []
    depth = 0
    start = None
    for i in range(len(clean)):
        c = clean[i:i + 1]
        if c == b"{":
            if depth == 0:
                start = i
            depth += 1
        elif c == b"}":
            depth -= 1
            if depth == 0 and start is not None:
                out.append((start, i))
                start = None
    return out


# ───────────────────────────────── 单文件扫描 ─────────────────────────────────
def scan_one(zig, root, path, outfile):
    """返回 {'hits':[(line,col,var)], 'errors':[str], 'fatal':str|None}"""
    try:
        raw = open(path, "rb").read()
    except Exception as e:
        return {"hits": [], "errors": [], "fatal": "读取失败 %s" % e}

    r = subprocess.run([zig, "cc"] + cc_flags(root, outfile) + [path],
                       capture_output=True)
    out = r.stdout + r.stderr

    errs = [m.group(0).decode("utf-8", "replace")
            for m in RE_ERR.finditer(out)]
    warns = []
    for m in list(RE_WARN.finditer(out)) + list(RE_MAYBE.finditer(out)):
        warns.append((int(m.group("line")), int(m.group("col")),
                      m.group("var").decode(),
                      m.group(0).decode("utf-8", "replace").strip()))

    clean = strip_c_bytes(raw)
    spans = size_arg_spans(clean)
    blocks = top_level_blocks(clean)
    ls = line_starts(raw)

    hits = []
    for (line, col, var, dmsg) in warns:
        if line - 1 >= len(ls):
            continue
        lstart = ls[line - 1]
        lend = ls[line] if line < len(ls) else len(raw)
        # ★ 连系范围 = **所在函数体**（不是诊断那一行！）：
        #   clang 只报变量的**第一次**使用，那处未必在 malloc 调用里。
        #   用「行区间相交」判定所属函数体（函数体可能整个写在同一行，
        #   此时块起点在行中段，不能拿行首偏移去比）。
        body = None
        for (bs, be) in blocks:
            if be < lstart or bs >= lend:
                continue                       # 该块与诊断行无交集
            body = (bs, be)
            break
        if body is None:
            continue
        vb = re.compile(rb"\b" + re.escape(var.encode("ascii", "replace")) + rb"\b")
        for (name, s, e) in spans:
            if e < body[0] or s > body[1]:
                continue                       # 分配调用不在同一函数体里
            if vb.search(clean[s:e + 1]):
                # ★ 只在「变量整词真的出现在该分配调用的**尺寸实参**里」时才算命中。
                #   （此处曾误留一条**无条件** hits.append，会把
                #     「同函数体内存在任意 malloc」误判成 Rule A ⇒ 假阳性。）
                # ★ 同时记下**证据**：编译器诊断原文 + 匹配到的尺寸实参原文 + 行号。
                #   门禁报告必须能自证「为什么这一条算命中」，否则无法人工复核。
                arg = clean[s:e + 1].decode("utf-8", "replace").strip()
                mline = bisect.bisect_right(ls, s)   # 1-based 行号
                ev = ("%s || 尺寸实参 %s(...) = (%s) @L%d"
                      % (dmsg[:130], name, arg[:70], mline))
                hits.append((line, col, var, ev))
                break
    return {"hits": hits, "errors": errs,
            "fatal": None if r.returncode == 0 else
                     "cc rc=%d %s" % (r.returncode, " | ".join(errs[:2]) or "无诊断")}


def iter_c(root, base):
    files = []
    for dp, _dn, fs in os.walk(base):
        for f in sorted(fs):
            if f.endswith(".c"):
                files.append(os.path.relpath(os.path.join(dp, f), root)
                             .replace(os.sep, "/"))
    return sorted(files)


# ─────────────────────────────────── 自证 ───────────────────────────────────
def selftest(zig, root, tmpdir):
    """正/负/形态分离 三向自证。任一不过 ⇒ 拒绝出结论。"""
    paths = {}
    for tag, body in (("bad", SELF_BAD), ("good", SELF_GOOD), ("other", SELF_OTHER)):
        p = os.path.join(tmpdir, "rule_a_%s.c" % tag)
        with open(p, "wb") as f:
            f.write(body)
        paths[tag] = p

    res = {}
    for tag, p in paths.items():
        res[tag] = scan_one(zig, root, p,
                            os.path.join(tmpdir, "self_%s.o" % tag))

    problems = []
    bad_hits = set(res["bad"]["hits"])
    if len(bad_hits) < 2:
        problems.append("正向失效：应检出 plain+offset 两个样本，实得 %d（fatal=%s）"
                        % (len(bad_hits), res["bad"].get("fatal")))
    if res["good"]["hits"]:
        problems.append("负向失效：正常样本被误报 %r" % (res["good"]["hits"],))
    if res["other"]["hits"]:
        problems.append("形态分离失效：非 malloc 用途被误报 %r" % (res["other"]["hits"],))
    for tag in ("bad", "good", "other"):
        if res[tag].get("fatal"):
            problems.append("自证 TU 编译失败[%s]：%s" % (tag, res[tag]["fatal"]))
    return problems, sorted(bad_hits), res["good"]["hits"], res["other"]["hits"]


# ─────────────────────────────────── 主流程 ───────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--zig", default=None)
    ap.add_argument("--ledger", default="tools/rule_a_pending.txt")
    ap.add_argument("--skip", default="tools/rule_a_skip.txt")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-scan", action="store_true", help="只做自证，不扫全树")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    zig = find_zig(args.zig)
    if not (os.path.exists(zig) or shutil.which(zig)):
        print("!! 找不到 zig（--zig 显式指定）: %s" % zig)
        return 3

    tmpdir = tempfile.mkdtemp(prefix="rule_a_")
    try:
        problems, bad_hits, good_hits, other_hits = selftest(zig, root, tmpdir)
        print("== 自证 ==")
        print("  正向样本命中: %r" % (bad_hits,))
        print("  负向样本命中: %r" % (good_hits,))
        print("  形态分离样本命中: %r" % (other_hits,))
        if problems:
            for p in problems:
                print("!! 自证失败：%s" % p)
            print("⇒ 仪器不可信，拒绝出结论")
            return 4
        print("  正/负/形态分离 全部符合预期 ⇒ 仪器可信")
        if args.no_scan:
            return 0

        ledger = set()
        lp = os.path.join(root, args.ledger)
        if os.path.exists(lp):
            for ln in open(lp, encoding="utf-8"):
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    ledger.add(ln)
        skip = set()
        sp = os.path.join(root, args.skip)
        if os.path.exists(sp):
            for ln in open(sp, encoding="utf-8"):
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    skip.add(ln.split("\t")[0].strip())

        base = os.path.join(root, "src", "proprietary")
        all_files = iter_c(root, base)
        files = [f for f in all_files if f not in skip]
        skipped = [f for f in all_files if f in skip]

        from concurrent.futures import ThreadPoolExecutor
        jobs = max(1, min(args.jobs, len(files) or 1))

        def work(idx_f):
            idx, f = idx_f
            # ★ 每个 TU 独立输出文件 —— 共享会在线程间互相覆盖
            of = os.path.join(tmpdir, "tu_%04d.o" % idx)
            return f, scan_one(zig, root, os.path.join(root, f), of)

        results = {}
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            for rel, r in ex.map(work, list(enumerate(files))):
                results[rel] = r

        all_hits, fatals = [], []
        for rel in sorted(results):
            r = results[rel]
            if r.get("fatal"):
                fatals.append((rel, r["fatal"]))
            for (ln, col, var, ev) in r["hits"]:
                all_hits.append((rel, ln, var, ev))

        # 台账棘轮用的**稳定标识**（路径:行号:变量名）；证据单独存，不进台账。
        hit_ids = ["%s:%d:%s" % (rel, ln, var) for (rel, ln, var, ev) in all_hits]

        print("\n== 全树扫描 ==")
        print("  受检 TU=%d（豁免 %d）；Rule A 命中 TU=%d，命中点数 %d"
              % (len(files), len(skipped),
                 len({h[0] for h in all_hits}), len(all_hits)))
        for (rel, ln, var, ev) in all_hits:
            print("   RULE-A  %s:%d:%s" % (rel, ln, var))
            print("           证据: %s" % ev)

        # fail-closed：编译失败的 TU 一律 FATAL（不允许当作"无命中"）
        if fatals:
            print("\n!! FATAL：以下 TU 编译失败 ⇒ 无法判定，门禁拒绝给绿")
            for rel, why in fatals[:20]:
                print("   %s :: %s" % (rel, why))
            if len(fatals) > 20:
                print("   … 共 %d 个" % len(fatals))
            print("   （确需豁免：写入 %s 并附理由，每行一条）" % args.skip)
            return 2

        new = sorted(set(hit_ids) - ledger)
        gone = sorted(ledger - set(hit_ids))
        if new:
            print("\n!! Rule A **新增**命中 ⇒ 失败（台账棘轮）")
            for h in new:
                print("   NEW  %s" % h)
            return 2
        if gone:
            print("\n（提示）台账条目已不再命中，可删行：")
            for h in gone:
                print("   GONE %s" % h)
        print("\nRule A 门禁：PASS（命中 %d 点，全部已在台账内）" % len(all_hits))
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
