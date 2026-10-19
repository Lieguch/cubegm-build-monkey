#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203 刻度 C：工厂函数在我方产物中的落位（自有.text / 工厂镜像区 / 缺失）。"""
import json
from elftools.elf.elffile import ELFFile

F = json.load(open('golden/factory.funcs.json', encoding='utf-8'))['functions']  # {name: {addr,n,...}}
e = ELFFile(open('build/rkgame.rebuilt.elf', 'rb'))
st = e.get_section_by_name('.symtab')
ours = {}
for s in st.iter_symbols():
    if s['st_info']['type'] == 'STT_FUNC' and s['st_size'] > 0:
        ours.setdefault(s.name, s['st_value'])

fimg = [(s.name, s['sh_addr'], s['sh_addr'] + s['sh_size'])
        for s in e.iter_sections() if s.name.startswith('.fimg')]
text = e.get_section_by_name('.text')
text_lo, text_hi = text['sh_addr'], text['sh_addr'] + text['sh_size']

import collections
c = collections.Counter()
missing = []
for n in F:
    if n not in ours:
        c['缺失'] += 1
        missing.append(n)
    else:
        v = ours[n]
        if text_lo <= v < text_hi:
            c['自有.text'] += 1
        elif any(lo <= v < hi for _, lo, hi in fimg):
            c['工厂镜像区'] += 1
        else:
            c['其它'] += 1

total = len(F)
print('工厂具名函数总数 =', total)
for k, v in c.most_common():
    print('  %-14s %d  (%.1f%%)' % (k, v, 100.0 * v / total))
print('  缺失清单(%d):' % len(missing), sorted(missing))