#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gen_local_alias.py — 为「我们代码引用、但属工厂 LOCAL 数据对象」的符号生成别名模块。

背景：账本 factory_globals.tsv 只收录全局（g）数据对象；工厂另有 LOCAL（l）
数据对象（如 .data.rel.ro.local 里的 KayName/number/p_name/mui_typename/crc_table），
我们的反编译代码会引用它们 → 链接期 UNDEF。
本工具：取我们 .o 的 UNDEF 名 ∩ 工厂 symtab 的「l O 数据对象」，生成
  .set NAME, <段镜像基址> + <偏移>
别名（不另占空间，与 gen_data_module.py 的镜像机制一致）。

用法:
  python tools/gen_local_alias.py <symtab.txt> <link_syms.tsv> <factory_layout.tsv> <out.S>
"""
import sys

def read_symtab(p):
    """→ {name: (addr, size, section)}  仅 LOCAL OBJECT 数据符号"""
    out = {}
    for line in open(p, encoding='utf-8', errors='replace'):
        parts = line.strip().split()
        if len(parts) < 6:
            continue
        addr, bind, typ, sec, size, name = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
        if bind != 'l' or typ != 'O':
            continue
        if not sec.startswith('.'):
            continue
        try:
            a = int(addr, 16); sz = int(size, 16)
        except ValueError:
            continue
        if name not in out:
            out[name] = (a, sz, sec)
    return out

def read_undefs(p):
    s = set()
    for line in open(p, encoding='utf-8', errors='replace'):
        f = line.strip().split('\t')
        if len(f) == 3 and f[0] == 'UNDEF':
            s.add(f[1])
    return s

def read_sections(p):
    secs = {}
    for line in open(p, encoding='utf-8', errors='replace'):
        f = line.strip().split('\t')
        if len(f) >= 4 and f[0] == 'SH':
            try:
                secs[f[1]] = int(f[2], 16)
            except ValueError:
                pass
    return secs

def main():
    symtab, linksyms, layout, outp = sys.argv[1:5]
    loc = read_symtab(symtab)
    undef = read_undefs(linksyms)
    secs = read_sections(layout)
    # 只为「已镜像段」内的对象生成别名（未镜像段如 .init_array 由 CRT/链接器提供）
    MIRRORED = {'.rodata', '.data.rel.ro.local', '.data', '.bss'}
    # 手工补充：Ghidra 恢复名（非真实符号）→ 真实地址（工厂证据）
    # crc_table = _ZL9crc_table @0x002e01c4 (l O .rodata, 1024B) —— XUnzip.cpp 内嵌 zlib 的 CRC 表
    EXTRA = {'crc_table': ('.rodata', 0x002e01c4 - 0x002dbca0)}
    hits = sorted(set(n for n in undef if n in loc and loc[n][2] in MIRRORED)
                  | set(n for n in undef if n in EXTRA))
    skipped = sorted(n for n in undef if n in loc and loc[n][2] not in MIRRORED)
    for n in skipped:
        print('  跳过 %s（段 %s 未镜像，由 CRT/链接器提供）' % (n, loc[n][2]))
    L = ['/* 自动生成：gen_local_alias.py — 工厂 LOCAL 数据对象别名（不占空间） */']
    for n in hits:
        if n in EXTRA:
            sec, off = EXTRA[n]
            L.append('.globl %s' % n)
            L.append('.set %s, __f%s_base + 0x%x' % (n, sec.replace('.', '_'), off))
            print('  alias(extra) %-24s %s+0x%x' % (n, sec, off))
            continue
        a, sz, sec = loc[n]
        base = secs.get(sec)
        if base is None:
            print('  跳过 %s（段 %s 不在布局中）' % (n, sec))
            continue
        off = a - base
        L.append('.globl %s' % n)
        L.append('.set %s, __f%s_base + 0x%x' % (n, sec.replace('.', '_'), off))
        print('  alias %-24s %s+0x%x (size 0x%x)' % (n, sec, off, sz))
    open(outp, 'w', encoding='utf-8', newline='\n').write('\n'.join(L) + '\n')
    print('共 %d 个别名 → %s' % (len(hits), outp))

if __name__ == '__main__':
    main()
