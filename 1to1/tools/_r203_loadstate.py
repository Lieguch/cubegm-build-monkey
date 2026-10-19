#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203：定性 load_state/save_state（工厂 size=4）是否"尾跳板→retro_*等价"。"""
import json
from elftools.elf.elffile import ELFFile

F = json.load(open('golden/factory.funcs.json', encoding='utf-8'))['functions']
for n in ('load_state', 'save_state', 'retro_load_state', 'retro_save_state'):
    if n in F:
        print('%-18s addr=%s n=%d' % (n, F[n]['addr'], F[n]['n']))
        print('     t1 前3条:', F[n]['t1'][:3])
    else:
        print('%-18s 不在 factory.funcs.json' % n)

print()
# 我方产物里 retro_load_state/retro_save_state 是否存在
e = ELFFile(open('build/rkgame.rebuilt.elf', 'rb'))
st = e.get_section_by_name('.symtab')
for s in st.iter_symbols():
    if s.name in ('retro_load_state', 'retro_save_state', 'load_state', 'save_state'):
        print('我方 %-20s type=%s size=%d value=%s shndx=%s'
              % (s.name, s['st_info']['type'], s['st_size'], hex(s['st_value']), s['st_shndx']))