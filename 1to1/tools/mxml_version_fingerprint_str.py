#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mxml 版本指纹 v2：用**字符串字面量**判别（静态函数名无判别力 —— 2.6~3.1 完全一致）。

方法（2026-09-27 定案）：
  · 从候选 tag 的**库本体 10 个 .c** 里抽出所有字符串字面量（长度 ≥ 6，去重）；
  · 逐条在工厂二进制里做**原始字节包含**判定（`bytes in blob`，1 次索引）；
  · 覆盖率高 = 该版本的字符串集与工厂一致 ⇒ 版本匹配。
  · 反向也要看：版本里有而工厂里没有的字符串（若属"新版本才加的报错文案"，即为版本证据）。

为什么可信：字符串字面量进 .rodata 时**内容逐字保留**（与编译器/优化无关），
这是比"函数尺寸"干净得多的版本判据（尺寸受 -O2 内联/分割影响，本项目已多次踩坑）。
"""
import re
import subprocess
import sys

REPO = r"D:\output\_mxml_clone"
FACTORY = r"D:\output\rkgame-1to1\golden\factory.rkgame.bin"
TAGS = ["release-2.6", "release-2.7", "release-2.8", "release-2.9",
        "release-2.10", "v2.11", "v3.0"]
LIB_FILES = ["mxml-attr.c", "mxml-entity.c", "mxml-file.c", "mxml-get.c",
             "mxml-index.c", "mxml-node.c", "mxml-private.c", "mxml-search.c",
             "mxml-set.c", "mxml-string.c"]


def git(*a):
    return subprocess.run(["git", "-C", REPO] + list(a), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def strings_of(tag, minlen=6):
    out = set()
    for base in LIB_FILES:
        ls = git("ls-tree", "-r", "--name-only", tag).stdout.splitlines()
        path = next((c for c in ls if c.split("/")[-1] == base), None)
        if not path:
            continue
        txt = git("show", "%s:%s" % (tag, path)).stdout
        for m in re.finditer(r'"((?:[^"\\\n]|\\.)*)"', txt):
            s = m.group(1)
            if len(s) >= minlen:
                out.add(s)
    return out


def main():
    blob = open(FACTORY, "rb").read()
    res = []
    for t in TAGS:
        ss = strings_of(t)
        hit = {s for s in ss if s.encode("latin1", "ignore") in blob}
        miss = ss - hit
        res.append((len(miss), len(ss), t, sorted(miss)))
        print("=== %-14s 字符串 %d 条 ｜ 命中工厂 %d ｜ 缺 %d"
              % (t, len(ss), len(hit), len(miss)))
        if miss:
            print("     工厂里没有的字符串（前 12）: %s"
                  % " ｜ ".join(sorted(miss)[:12]))
    print()
    res.sort()
    print("★ 按「未命中」升序（越少越像）:")
    for m, n, t, _ in res:
        print("   %-14s 未命中 %d / %d" % (t, m, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
