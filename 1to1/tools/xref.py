#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xref.py —— 在 ARM32 ELF 里找"谁调用了某个地址/符号"（BL/BLX/B 目标扫描）。

为什么需要它（2026-09-28）：
  判定某个函数是否**真的被使用**、以及**调用者如何解读它的返回值**，
  是"按工厂机器行为对齐实现"的前提。工厂没有 DWARF（应用对象），只能静态 xref。

用法:
    python tools/xref.py <elf> <符号名或 0x地址> [--ours <elf>]
"""
import argparse
import bisect
import sys

from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN


def load(path):
    e = ELFFile(open(path, "rb"))
    st = e.get_section_by_name(".symtab")
    funcs = []
    addr2name = {}
    if st is not None:
        for s in st.iter_symbols():
            if s.name and s["st_info"]["type"] == "STT_FUNC" and isinstance(s["st_shndx"], int):
                va = s["st_value"] & ~1
                funcs.append((va, s["st_size"], s["st_value"] & 1, s["st_shndx"], s.name))
                addr2name.setdefault(va, s.name)
    funcs.sort()
    return e, funcs, addr2name


def scan(e, funcs, addr2name, target_va):
    """返回 [(调用者名字, 调用点地址, 助记符)]"""
    out = []
    for va, size, thumb, shndx, name in funcs:
        if not size:
            continue
        sec = e.get_section(shndx)
        if sec is None:
            continue
        off = va - sec["sh_addr"]
        code = sec.data()[off:off + size]
        md = Cs(CS_ARCH_ARM, (CS_MODE_THUMB if thumb else CS_MODE_ARM) | CS_MODE_LITTLE_ENDIAN)
        for i in md.disasm(code, va):
            if not i.mnemonic.startswith(("bl", "b")):
                continue
            try:
                tgt = int(i.op_str.replace("#", "").split(",")[0], 16)
            except Exception:
                continue
            if (tgt & ~1) == target_va:
                out.append((name, i.address, i.mnemonic))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf")
    ap.add_argument("sym")
    a = ap.parse_args()

    e, funcs, addr2name = load(a.elf)
    if a.sym.lower().startswith("0x"):
        tgt = int(a.sym, 16) & ~1
    else:
        cands = [va for va, _, _, _, n in funcs if n == a.sym or n.startswith(a.sym)]
        if not cands:
            print("找不到符号 %s" % a.sym)
            return 2
        tgt = cands[0]
    print("目标 %s = 0x%x（名 %s）" % (a.sym, tgt, addr2name.get(tgt, "?")))
    hits = scan(e, funcs, addr2name, tgt)
    print("调用点 %d 处：" % len(hits))
    for name, at, mn in hits:
        print("   %-46s @0x%05x  %s" % (name, at, mn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
