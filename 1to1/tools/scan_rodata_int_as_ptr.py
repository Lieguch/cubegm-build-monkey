#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
门禁：**`.rodata` 字符串被 Ghidra 渲染成整数类型，使用时"多解引用一次"**（技能铁律 93）

背景（rkgame 1:1 重构，P5 第八个真实分歧）
------------------------------------------------
工厂 ELF 里 `0x002dcea4` 处**就是字符串 `"font.ttf"`**，但 Ghidra 把它渲染成
`/* @0x002dcea4 undefined4 */ extern unsigned int DAT_002dcea4;`，
而使用点写成 `FindZipItemA(res_hz, (char *)DAT_002dcea4, 1, &idx, ze);`。

C 语义下 `(char *)DAT_002dcea4` = **把该处 4 字节的内容当指针** ⇒ 反汇编出现**连续两条 ldr**
（先取符号地址、再取内容），实际拿到 `0x746e6f66`（ASCII `"font"`）
⇒ `TUnzip::Find` 里 `strcpy(name,tname)` 立刻 SIGSEGV（访问地址 `0x746e6f66`）。

判据（零误报，逐条可核）
------------------------
1. 源码里出现 `(char *)DAT_xxx` / `(const char *)DAT_xxx` / `(TCHAR *)DAT_xxx`；
2. 该 `DAT_xxx` 在 `src/compat/globals.h` 里被声明为**整数类型**
   （`unsigned int` / `int` / `undefined4` —— 而非 `char[]` / `char *`）；
3. **工厂 ELF** 在该符号地址处的字节是**可打印 ASCII 字符串**（至少 3 字符、以 NUL 结束）。

⇒ 三条同时成立即报 FAIL：这是「字符串被当整数、于是被多解引用一次」。

用法
----
    python3 tools/scan_rodata_int_as_ptr.py [--factory <elf>] [--src src] [--globals <path>]

退出码：0 = 无违规；1 = 有违规（每处都会让运行时拿到垃圾指针）
"""
import os
import re
import struct
import sys


def load_segments(path):
    d = open(path, "rb").read()
    if d[:4] != b"\x7fELF":
        raise SystemExit("FATAL %s 不是 ELF" % path)
    phoff = struct.unpack_from("<I", d, 28)[0]
    phentsize = struct.unpack_from("<H", d, 42)[0]
    phnum = struct.unpack_from("<H", d, 44)[0]
    segs = []
    for i in range(phnum):
        o = phoff + i * phentsize
        t, off, va, pa, fs, ms, fl, al = struct.unpack_from("<8I", d, o)
        if t == 1:                       # PT_LOAD
            segs.append((va, va + fs, off - va))
    return d, segs


def read_va(d, segs, va, n=32):
    for a, b, delta in segs:
        if a <= va < b:
            o = va + delta
            return d[o:o + n]
    return None


def printable_string(buf):
    if not buf or buf[0] == 0:
        return None
    s = buf.split(b"\x00")[0]
    if len(s) < 3:
        return None
    if all(32 <= b < 127 or b in (9, 10, 13) for b in s):
        return s
    return None


def main():
    argv = sys.argv[1:]

    def opt(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else default

    fac = opt("--factory", None)
    if fac is None:
        for c in ("golden/factory.rkgame.bin", "D:/output/rkgame/rkgame"):
            if os.path.exists(c):
                fac = c
                break
    srcroot = opt("--src", "src")
    globals_h = opt("--globals", "src/compat/globals.h")

    if not fac or not os.path.exists(fac):
        print("FATAL 找不到工厂 ELF（--factory）")
        return 3

    # ① globals.h 里 DAT_* 的声明类型与地址
    INT_TYPES = {"unsigned int", "int", "undefined4", "undefined", "uint32_t", "gh_u4", "gh_uint"}
    decl = {}
    # ★ 必须**跨行**匹配：`/* @0xADDR ... */` 注释块可能很长（含说明文字），
    #   `extern ...;` 在其后若干行。曾写成单行匹配 ⇒ 加长注释后解析不到符号
    #   ⇒ 门禁**静默漏检**（真实 globals.h 的 PASS 是假绿）。自检用例必须覆盖这一点。
    tx = open(globals_h, encoding="utf-8", errors="replace").read()
    for m in re.finditer(r"/\*.*?@(0x[0-9a-fA-F]+).*?\*/\s*"
                         r"extern\s+([^;{}]*?)\b(DAT_[0-9a-fA-F]+)\s*(\[\s*\])?\s*;", tx, re.S):
        decl[m.group(3)] = (int(m.group(1), 16), " ".join(m.group(2).split()), bool(m.group(4)))

    # ② 源码里 (char *)DAT_xxx 形式的用法
    use_re = re.compile(r"\((?:const\s+)?(?:char|TCHAR|unsigned\s+char)\s*\*\)\s*(DAT_[0-9a-fA-F]+)")
    uses = {}
    for dirpath, _dirs, fnames in os.walk(srcroot):
        for fn in fnames:
            if not fn.endswith((".c", ".cpp")):
                continue
            p = os.path.join(dirpath, fn)
            for i, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
                for m in use_re.finditer(line):
                    uses.setdefault(m.group(1), []).append((p, i, line.strip()[:120]))

    d, segs = load_segments(fac)

    print("== 门禁：`.rodata` 字符串被当整数 ⇒ 多解引用一次（技能铁律 93）==")
    print("   工厂: %s" % fac)
    print("   扫描: %s 里 %d 个 (char *)DAT_xxx 用法点，涉及 %d 个符号"
          % (srcroot, sum(len(v) for v in uses.values()), len(uses)))

    bad = []
    for sym, sites in sorted(uses.items()):
        if sym not in decl:
            continue
        va, typ, is_arr = decl[sym]
        if is_arr or typ not in INT_TYPES:
            continue                       # 已是数组/指针 ⇒ 语义正确
        s = printable_string(read_va(d, segs, va))
        if not s:
            continue                       # 工厂该处不是字符串 ⇒ 当整数是对的
        bad.append((sym, va, typ, s[:26], sites))

    if not bad:
        print("\n  ✓ 结论：未发现「字符串被声明为整数并被当 char* 使用」")
        return 0

    print("\n  ✗ 违规 %d 处（每处都会让运行时拿到垃圾指针）：" % len(bad))
    for sym, va, typ, s, sites in bad:
        print("\n   ★ %s  @0x%08x  声明=%s  工厂内容=%r" % (sym, va, typ, s))
        print("     ⇒ 应改为 `extern char %s[];`（`.S` 里的地址别名无需改动）" % sym)
        for p, i, txt in sites[:4]:
            print("       %s:%d  %s" % (p.replace("\\", "/"), i, txt))
    print("\n  ✗ 结论：存在「字符串当整数」的 Ghidra 类型陷阱")
    return 1


if __name__ == "__main__":
    sys.exit(main())
