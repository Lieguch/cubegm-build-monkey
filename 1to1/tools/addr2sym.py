#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
addr2sym.py —— 把诊断产物里的**裸地址**翻成"函数名+偏移"

为什么需要（R261）：
    本轮给诊断仪加了两类**语义探针**，它们输出的是地址而不是名字：
        trace.log :  ZIPOPEN ... caller=0x00xxxxxx        （谁打开的 zip）
                     ZIPNAME ... caller=0x00xxxxxx        （哪段代码在比对名字）
        crash.txt :  pc=/lr=  /  --- call chain --- 的 [n] 0x00xxxxxx
    产物是**非 PIE**，地址固定，所以这些裸地址可以直接对符号表解析。
    没有这个工具，每轮都要手工翻 symbol；有了它，一条命令出结论。

用法：
    python tools/addr2sym.py <diag_elf> <trace.log|crash.txt> [...更多文件]
    python tools/addr2sym.py <diag_elf> --addr 0x12cd0 0x1f39c ...

输出：
    ① 每个输入文件里"出现过的地址 → 符号+偏移"，按首次出现顺序（不重复）
    ② 无法归属的地址显式标注 `[unmapped]`（**不许静默丢弃**：区分"解析失败"与"没走到"）
"""
import io
import os
import re
import struct
import sys


def load_syms(path):
    """返回 [(addr, size, name)]，只保留 STT_FUNC / STT_OBJECT 里有名字的。"""
    d = io.open(path, 'rb').read()
    if d[:4] != b'\x7fELF':
        raise SystemExit('not an ELF: %s' % path)
    e_shoff = struct.unpack_from('<I', d, 0x20)[0]
    e_shentsize = struct.unpack_from('<H', d, 0x2e)[0]
    e_shnum = struct.unpack_from('<H', d, 0x30)[0]
    secs = []
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        name, typ, flags, addr, off, size, link, info, align, ent = struct.unpack_from('<10I', d, o)
        secs.append(dict(name=name, typ=typ, addr=addr, off=off, size=size,
                         link=link, ent=ent or 16))
    out = []
    for s in secs:
        if s['typ'] not in (2, 11):        # SHT_SYMTAB / SHT_DYNSYM
            continue
        stro = secs[s['link']]['off']
        for j in range(s['size'] // s['ent']):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s['off'] + j * s['ent'])
            if nmn == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            nm = d[stro + nmn:k].decode('utf-8', 'replace')
            if inf & 0xF in (2, 1):        # FUNC / OBJECT
                out.append((val, sz, nm))
    out.sort()
    return out


def sym_of(syms, a):
    """精确或"落在 [addr, addr+size)"内 → (name, off)；否则 None。"""
    lo, hi = 0, len(syms) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if syms[mid][0] <= a:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    if best is None:
        return None
    addr, size, nm = syms[best]
    if a == addr:
        return nm, 0
    if size and addr < a < addr + size:
        return nm, a - addr
    return None


HEX = re.compile(r'0x([0-9a-fA-F]{6,8})\b')
# 只关心"是地址"的上下文，避免把 off=/len=/sz= 这类数值当代码地址
CTX = re.compile(r'(caller=|pc=|lr=|bp=|ret=|\[[ \d]*\]\s)(0x[0-9a-fA-F]{6,8})\b')


def scan(path, syms):
    print('== %s' % path)
    seen = set()
    lines = io.open(path, 'rb').read().decode('utf-8', 'replace').splitlines()
    for ln in lines:
        cands = []
        for m in CTX.finditer(ln):
            cands.append(int(m.group(2), 16))
        if not cands:
            # 兼容 crash.txt 的 "  12 ENTER 00f2a1b4" 形式
            m = re.match(r'\s*\d+\s+(?:ENTER|EXIT)\s+([0-9a-fA-F]{8})\s*$', ln)
            if m:
                cands.append(int(m.group(1), 16))
        for a in cands:
            if a in seen:
                continue
            seen.add(a)
            r = sym_of(syms, a)
            if r:
                print('  0x%08x  %s+0x%x' % (a, r[0], r[1]))
            else:
                print('  0x%08x  [unmapped]   << 不在本模块符号范围（外部 so / 栈值 / 已损坏）' % a)
    if not seen:
        print('  (本文件没有出现可解析的地址字段)')
        print('  ★ 判据提示：探针只在 -DCGM_DIAG_TRACE_ZIP 的诊断版里生效；')
        print('    crash.txt 里若没有 pc=/lr=，说明崩溃处理段仍未生效（先修仪器，别下结论）。')


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    elf = sys.argv[1]
    syms = load_syms(elf)
    rest = sys.argv[2:]
    if rest[0] == '--addr':
        for t in rest[1:]:
            a = int(t, 16) if not t.lower().startswith('0x') else int(t, 16)
            r = sym_of(syms, a)
            print('0x%08x  %s' % (a, ('%s+0x%x' % r) if r else '[unmapped]'))
        return 0
    for p in rest:
        if not os.path.exists(p):
            print('!! 缺文件: %s' % p)
            continue
        scan(p, syms)
    return 0


if __name__ == '__main__':
    sys.exit(main())
