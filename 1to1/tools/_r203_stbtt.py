#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203：产物里 stbtt 符号全量清单，核实 stbtt__csctx_rline_to / stbtt__cuberoot 是否真缺失。"""
from elftools.elf.elffile import ELFFile

for tag, p in [('我方', 'build/rkgame.rebuilt.elf'), ('工厂', 'golden/factory.rkgame.bin')]:
    e = ELFFile(open(p, 'rb'))
    st = e.get_section_by_name('.symtab')
    print('==== %s ====' % tag)
    names = []
    for s in st.iter_symbols():
        if s.name and 'stbtt' in s.name:
            names.append((s.name, s['st_info']['type'], s['st_size'],
                          hex(s['st_value'])))
    for n in sorted(names):
        print('  %-48s %-10s size=%-5d val=%s' % n)
    # 明确点名两个
    for target in ('stbtt__csctx_rline_to', 'stbtt__cuberoot'):
        hit = [n for n in names if n[0] == target]
        print('  >>> %s: %s' % (target, '存在' if hit else '★ 缺失'))
    print()