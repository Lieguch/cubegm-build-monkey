#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
门禁：**对象/指针算术被按元素大小缩放**（Ghidra 渲染陷阱，铁律 89）

背景（rkgame 1:1 重构，P5 第六个真实分歧）
------------------------------------------------
Ghidra 把「字节偏移」渲染成 `*(u32 *)(this + 0x138)`，其中 `this` 声明为 `TUnzip *`。
`TUnzip` 是 576 字节的类 ⇒ C 语言按 `sizeof(TUnzip)` 缩放 ⇒ 实际写 `+0x2BE00`（180 KB）
⇒ 对 576 字节的对象越界 180 KB ⇒ SIGSEGV。
而工厂机器码是**字节偏移**：`str ip, [r0, #312]`（= 0x138）。

判据
----
只有「左操作数**声明为指针类型**且 `sizeof(pointee) > 1`」才会被缩放：

| 左操作数声明 | `x + 0x138` 的含义 | 危险？ |
|---|---|---|
| `int iVar2;`（标量）| 整数加法 | 否 |
| `char *p;` / `gh_byte *p;` | 字节偏移（×1）| 否（等价）|
| `gh_u4 *p;` | ×4 | **是** |
| `TUnzip *this;` | ×sizeof(TUnzip) | **是** |

用法
----
    python3 tools/scan_scaled_ptr_arith.py [src_root] [--all]

退出码：0 = 无嫌疑；1 = 有嫌疑（需人工对照反汇编确认）。
`--all` 会把「已显式转字节」的正确写法也列出来做对照。
"""
import os
import re
import sys

# 指针基类型里，步长恒为 1 的（安全）
BYTE_TYPES = {
    "char", "signed char", "unsigned char",
    "gh_byte", "gh_char", "uint8_t", "int8_t", "u8", "gh_u1", "byte",
    "signed_char", "schar", "uchar",
}

# 已知尺寸（字节）；未列出的按「未知（≥1 且可能 >1）」处理
KNOWN_SIZE = {
    "gh_u2": 2, "gh_ushort": 2, "unsigned short": 2, "short": 2, "uint16_t": 2, "u16": 2,
    "gh_u4": 4, "gh_uint": 4, "unsigned int": 4, "int": 4, "uint32_t": 4, "u32": 4,
    "float": 4, "gh_float": 4,
    "gh_u8": 8, "uint64_t": 8, "u64": 8, "double": 8, "gh_double": 8,
    "FILE": 108,
}

DECL_RE = re.compile(
    r"^[ \t]*(?:(?:const|static|volatile|register|extern)\s+)*"
    r"((?:struct\s+|class\s+|union\s+)?[A-Za-z_][A-Za-z0-9_]*(?:\s+[A-Za-z_][A-Za-z0-9_]*)?)\s*"
    r"\*+\s*([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s*\[[^\]]*\])?\s*(?:[;,)])",
    re.M)

# `x + 0x138` / `x - 0x10` / `x + 312`
ARITH_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*([+\-])\s*(0x[0-9a-fA-F]+|\d+)\b")
# `p[0x40]`（下标也按元素缩放）
INDEX_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*(0x[0-9a-fA-F]+|\d+)\s*\]")
# 显式转字节的正确写法：((char *)x + N) / ((gh_byte *)x + N)
BYTECAST_RE = re.compile(r"\(\(\s*(?:char|gh_byte|unsigned char|uint8_t)\s*\*+\s*\)\s*([A-Za-z_][A-Za-z0-9_]*)")


def base_token(t):
    t = re.sub(r"\b(struct|class|union)\b", " ", t)
    return " ".join(t.split()).strip()


def is_dangerous(t):
    b = base_token(t)
    if b.startswith("*"):
        return None
    if b in BYTE_TYPES:
        return None
    return KNOWN_SIZE.get(b, -1)  # -1 = 未知尺寸（可能 >1）


def scan_file(path, show_all=False):
    src = open(path, encoding="utf-8", errors="replace").read()
    # 1) 收集本文件里所有指针声明：name -> 基类型
    ptrs = {}
    for m in DECL_RE.finditer(src):
        typ, name = m.group(1), m.group(2)
        ptrs.setdefault(name, typ)
    # 2) 找出被显式转字节的变量（同一表达式已正确处理，跳过）
    bytecast = set(BYTECAST_RE.findall(src))

    hits = []
    for m in ARITH_RE.finditer(src):
        name, op, lit = m.group(1), m.group(2), m.group(3)
        if name not in ptrs:
            continue
        d = is_dangerous(ptrs[name])
        if d is None:
            continue
        const = int(lit, 16) if lit.lower().startswith("0x") else int(lit)
        # 常量太小（0/1/2/…）在结构体成员访问里也可能是对的；保守起见全报但分级
        line = src[:m.start()].count("\n") + 1
        ctx = src.splitlines()[line - 1].strip()
        # 若同一行里该变量已被转成字节指针，则不是嫌疑
        if name in bytecast and ("(char *)" in ctx or "(gh_byte *)" in ctx
                                 or "unsigned char *)" in ctx):
            continue
        if d > 1:
            sev = "HIGH"
        elif d == -1:
            # 未知尺寸：只有当偏移量"不像结构体成员"（> 0x400）时才高危
            sev = "HIGH" if const > 0x400 else "LOW"
        else:
            sev = "SAFE"
        if sev == "SAFE" and not show_all:
            continue
        hits.append((line, sev, name, ptrs[name], op, lit, const, d, ctx))

    for m in INDEX_RE.finditer(src):
        name, lit = m.group(1), m.group(2)
        if name not in ptrs:
            continue
        d = is_dangerous(ptrs[name])
        if d is None:
            continue
        const = int(lit, 16) if lit.lower().startswith("0x") else int(lit)
        line = src[:m.start()].count("\n") + 1
        ctx = src.splitlines()[line - 1].strip()
        sev = "HIGH" if (d > 1 or (d == -1 and const > 0x100)) else "LOW"
        hits.append((line, sev, name, ptrs[name], "[]", lit, const, d, ctx))
    return hits


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show_all = "--all" in sys.argv
    root = args[0] if args else "src"
    files = []
    for dirpath, _dirs, fnames in os.walk(root):
        for fn in fnames:
            if fn.endswith(".c"):
                files.append(os.path.join(dirpath, fn))
    files.sort()

    total_high = total_low = 0
    report = []
    for f in files:
        hits = scan_file(f, show_all)
        high = [h for h in hits if h[1] == "HIGH"]
        low = [h for h in hits if h[1] == "LOW"]
        if not high and not low:
            continue
        total_high += len(high)
        total_low += len(low)
        report.append((f, high, low))

    print("== 指针算术缩放扫描（铁律 89：`ptr + 常量` 按 sizeof(pointee) 缩放）==")
    print("   扫描 .c 文件 %d 个" % len(files))
    for f, high, low in report:
        rel = os.path.relpath(f).replace("\\", "/")
        if high:
            print("\n  ★ %s" % rel)
            for line, sev, name, typ, op, lit, const, d, ctx in high:
                size = "未知(>1?)" if d == -1 else str(d)
                prod = "" if d <= 1 else "  ⇒ 实际偏移 0x%X" % (const * d)
                print("    %4d [HIGH] %s (%s *, sizeof=%s) %s %s%s"
                      % (line, name, typ, size, op, lit, prod))
                print("           %s" % (ctx[:110],))
        if low and show_all:
            for line, sev, name, typ, op, lit, const, d, ctx in low:
                print("    %4d [LOW ] %s (%s *) %s %s" % (line, name, typ, op, lit))

    print("\n  小计：HIGH=%d（需人工对照反汇编，确认常量是否原样出现如 `#312`） LOW=%d"
          % (total_high, total_low))
    if total_high:
        print("  ✗ 结论：存在疑似被缩放的指针算术（见上）")
        return 1
    print("  ✓ 结论：未发现疑似被缩放的指针算术")
    return 0


if __name__ == "__main__":
    sys.exit(main())
