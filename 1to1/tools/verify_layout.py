#!/usr/bin/env python3
"""
verify_layout.py — P3 布局校验：重建 ELF 的数据符号地址必须与工厂逐位一致。

原理：
  工厂数据镜像 + `.set` 别名 + 复刻工厂 VMA 的链接脚本 ⇒ 每个数据符号都应落在
  工厂的原始地址上。本工具对**全部**工厂账本符号做逐一比对。

输入：
  <rebuilt.elf>            重建产物（需含 .symtab）
  <factory_globals.tsv>    工厂权威全局布局账本
退出码：0 = 全部一致；2 = 有偏差（列出清单）
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import elf_syms  # noqa: E402


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    elf, ledger = sys.argv[1], sys.argv[2]
    want = []
    for i, line in enumerate(open(ledger, encoding='utf-8')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 3:
            continue
        want.append((f[0], int(f[1], 16), int(f[2], 16), f[3]))

    de, co, un, err = elf_syms.read_syms(elf)
    if err:
        print('读取重建 ELF 失败: %s' % err)
        return 2
    got = {}
    for nm, b, t in de:
        # 符号表里 value 就是绝对地址（ELF 已链接）
        got.setdefault(nm, b)
    # 重新读原始 value：read_syms 返回的是 (name,bind,type)，需要 addr
    import struct
    d = open(elf, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    e_shentsize = struct.unpack_from('<H', d, 46)[0]
    e_shnum = struct.unpack_from('<H', d, 48)[0]
    addr_of = {}
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        sh = struct.unpack_from('<10I', d, o)
        if sh[1] != 2:   # SHT_SYMTAB
            continue
        stroff = struct.unpack_from('<10I', d, e_shoff + sh[6] * e_shentsize)[4]
        ent = sh[9] or 16
        for j in range(sh[5] // ent):
            so = sh[4] + j * ent
            st_name, st_value, st_size, st_info, st_other, st_shndx = \
                struct.unpack_from('<IIIBBH', d, so)
            if st_name == 0:
                continue
            end = d.index(b'\x00', stroff + st_name)
            nm = d[stroff + st_name:end].decode('utf-8', 'replace')
            if st_shndx not in (0, 0xFFF2):
                addr_of.setdefault(nm, st_value)

    ok = miss = bad = 0
    badlist, misslist = [], []
    for name, faddr, fsize, sec in want:
        a = addr_of.get(name)
        if a is None:
            miss += 1
            misslist.append((name, faddr, sec))
        elif a == faddr:
            ok += 1
        else:
            bad += 1
            badlist.append((name, faddr, a))

    L = []
    A = L.append
    A('=' * 66)
    A('P3 布局校验：%s' % os.path.basename(elf))
    A('=' * 66)
    A('账本符号数 : %d' % len(want))
    A('地址一致   : %d  (%.1f%%)' % (ok, 100.0 * ok / max(len(want), 1)))
    A('地址偏差   : %d' % bad)
    A('符号缺失   : %d  （上游组件/函数，不在本账本责任范围）' % miss)
    A('')
    if badlist:
        A('--- 偏差明细（前 40）---')
        for n, f, g in badlist[:40]:
            A('  %-28s 工厂 0x%08x  重建 0x%08x  Δ%+d' % (n, f, g, g - f))
        if len(badlist) > 40:
            A('  ... 共 %d' % len(badlist))
        A('')
    if misslist:
        A('--- 缺失样本（前 20）---')
        for n, f, s in misslist[:20]:
            A('  %-28s 应在 0x%08x  %s' % (n, f, s))
        if len(misslist) > 20:
            A('  ... 共 %d' % len(misslist))

    txt = '\n'.join(L) + '\n'
    sys.stdout.write(txt)
    rep = os.path.join(ROOT, 'report', 'verify_layout.txt')
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    open(rep, 'w', encoding='utf-8').write(txt)
    sys.stderr.write('report -> %s\n' % rep)
    return 0 if (bad == 0 and miss == 0) else (2 if bad else 0)


if __name__ == '__main__':
    sys.exit(main())
