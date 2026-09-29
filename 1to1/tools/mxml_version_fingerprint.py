#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mxml 版本指纹：用**工厂 LOCAL 符号集**去比对候选 tag 的**静态函数集**。

为什么这个方法可信（2026-09-27）：
  · 工厂 .symtab 完整（未 strip）⇒ 每个 file-scope static 函数都是一个 STB_LOCAL 符号，
    名字与源码里的名字**逐字相同**（GCC 不改名，只可能加 .part.N/.isra.N 后缀 ⇒ 已归一）。
  · 静态函数的**名字集合**只由源码决定，**与编译器/优化级别无关**
    ⇒ 这是把"版本"从"编译器差异"里分离出来的**唯一干净指纹**。
  · 反过来，公有 API 集合只能给出"≥/≤"的区间（会受 --gc-sections / 内联影响）。

输出：每个候选 tag 与工厂集合的 (命中 / 工厂独有 / 版本独有)。
"""
import re
import subprocess
import sys

REPO = r"D:\output\_mxml_clone"
TAGS = ["release-2.6", "release-2.7", "release-2.8", "release-2.9",
        "release-2.10", "v2.11", "v2.12", "v3.0", "v3.1"]

# 工厂 .symtab 里的 mxml 静态函数（STB_LOCAL STT_FUNC，.part.N 已归一）
FACTORY_STATICS = [
    "_mxml_destructor", "_mxml_fini", "_mxml_init",
    "mxml_add_char", "mxml_fd_getc", "mxml_fd_putc", "mxml_fd_read", "mxml_fd_write",
    "mxml_file_getc", "mxml_file_putc", "mxml_get_entity", "mxml_isspace",
    "mxml_load_data", "mxml_new", "mxml_set_attr", "mxml_string_getc",
    "mxml_string_putc", "mxml_write_name", "mxml_write_node",
    "mxml_write_string", "mxml_write_ws",
]

SRC_RE = re.compile(r"^mxml[^/]*\.c$")

# ★ 只用**库本体**的 10 个源文件（排除 mxmldoc / testmxml 等工具，
#   它们的静态函数与库版本无关，会把指纹搅浑 —— 2026-09-27 实测踩过）。
LIB_FILES = [
    "mxml-attr.c", "mxml-entity.c", "mxml-file.c", "mxml-get.c", "mxml-index.c",
    "mxml-node.c", "mxml-private.c", "mxml-search.c", "mxml-set.c", "mxml-string.c",
]


def git(*args):
    return subprocess.run(["git", "-C", REPO] + list(args),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def statics_of(tag):
    """→ set(库本体静态函数名)"""
    names = set()
    for base in LIB_FILES:
        # tag 下文件可能不在根目录，先找路径
        ls = git("ls-tree", "-r", "--name-only", tag)
        path = None
        for cand in ls.stdout.splitlines():
            if cand.split("/")[-1] == base:
                path = cand
                break
        if path is None:
            continue
        blob = git("show", "%s:%s" % (tag, path))
        if blob.returncode != 0:
            continue
        txt = blob.stdout
        # static <类型,可能跨行>\n<函数名> ( ... )
        for m in re.finditer(
                r"\bstatic\b[^;{}\n]*(?:\n[^;{}\n]*)*?\n"
                r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", txt):
            names.add(m.group(1))
    return names


def norm(n):
    return re.sub(r"\.(part|isra|constprop)\.\d+$", "", n)


def main():
    fac = {norm(n) for n in FACTORY_STATICS}
    print("工厂 mxml 静态函数（归一后）= %d 个" % len(fac))
    print("  " + ", ".join(sorted(fac)))
    print()
    best = []
    for t in TAGS:
        s = {norm(n) for n in statics_of(t)}
        hit = fac & s
        fac_only = fac - s
        ver_only = s - fac
        best.append((len(fac_only), len(ver_only), t, fac_only, ver_only))
        print("=== %-14s 版本内静态函数 %d 个 ｜ 命中工厂 %d/%d ｜ 工厂独有 %d ｜ 版本独有 %d"
              % (t, len(s), len(hit), len(fac), len(fac_only), len(ver_only)))
        if fac_only:
            print("     工厂独有（该版本没有 ⇒ 不是这个版本）: %s" % ", ".join(sorted(fac_only)))
        if ver_only:
            print("     版本独有: %s" % ", ".join(sorted(ver_only)))
    print()
    best.sort()
    print("★ 按「工厂独有」升序（越少越像）:")
    for fo, vo, t, a, b in best:
        print("   %-14s 工厂独有 %d" % (t, fo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
