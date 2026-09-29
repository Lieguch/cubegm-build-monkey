#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打印某产物的链接保真指标 —— 与**工厂**逐项对拍。

用法: python tools/probe_link_binding.py <elf>

输出（全是机械可复算的）：
  1. `mem*/str*` 的归属（静态定义 vs 动态导入）—— 工厂全部是动态导入
  2. DT_NEEDED 条数与顺序
  3. `.dynsym` 三个数：工厂 / 我方 / 交集，以及**两个方向的差集**（最关键的保真指标）
"""
import sys

from elftools.elf.elffile import ELFFile

FACTORY = "golden/factory.rkgame.bin"
KEYS = ("memcpy", "memset", "memmove", "strlen", "memcmp",
        "putc", "getc", "strdup", "_IO_putc", "_IO_getc", "__strdup", "islower")


def imports(path):
    e = ELFFile(open(path, "rb"))
    dyn = e.get_section_by_name(".dynsym")
    return ({s.name for s in dyn.iter_symbols()
             if s.name and s["st_shndx"] == "SHN_UNDEF"} if dyn is not None else set()), e


def main():
    p = sys.argv[1]
    fi, _ = imports(FACTORY)
    oi, e = imports(p)
    st = e.get_section_by_name(".symtab")
    defs = {}
    if st is not None:
        for s in st.iter_symbols():
            if s.name and s["st_shndx"] != "SHN_UNDEF":
                defs.setdefault(s.name, s["st_size"])
    need = [t.needed for t in e.get_section_by_name(".dynamic").iter_tags()
            if t.entry.d_tag == "DT_NEEDED"]
    print("   动态导入 %d 个（工厂 %d）| DT_NEEDED %d: %s"
          % (len(oi), len(fi), len(need), need))
    print("   工厂有/我方无 %d: %s" % (len(fi - oi), sorted(fi - oi)))
    print("   我方有/工厂无 %d: %s" % (len(oi - fi), sorted(oi - fi)))
    for k in KEYS:
        tag = []
        if k in defs:
            tag.append("静态定义(%dB)" % defs[k])
        if k in oi:
            tag.append("动态导入")
        mark = ""
        if k in fi and k not in oi:
            mark = "  ★工厂有、我方无"
        elif k not in fi and k in oi:
            mark = "  ★我方有、工厂无"
        print("   %-9s %s%s" % (k, " + ".join(tag) if tag else "—", mark))
    return 0


if __name__ == "__main__":
    sys.exit(main())
