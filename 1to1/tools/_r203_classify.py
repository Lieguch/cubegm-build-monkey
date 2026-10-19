#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203：把工厂缺失的 50 个符号精确分类，定性"真缺口 vs 工具链/分片/音效族"。"""
import json
from elftools.elf.elffile import ELFFile

F = json.load(open('golden/factory.funcs.json', encoding='utf-8'))['functions']  # name -> {addr,n,t1}
e = ELFFile(open('build/rkgame.rebuilt.elf', 'rb'))
st = e.get_section_by_name('.symtab')
ours = {s.name for s in st.iter_symbols() if s['st_info']['type'] == 'STT_FUNC' and s['st_size'] > 0}

# 工厂 .symtab 拿 type/size
fe = ELFFile(open('golden/factory.rkgame.bin', 'rb'))
fst = fe.get_section_by_name('.symtab')
fmeta = {}
for s in fst.iter_symbols():
    if s.name and s['st_info']['type'] == 'STT_FUNC':
        fmeta[s.name] = (s['st_size'], str(s['st_info']['bind']))
# 有的符号是 NOTYPE / OBJECT，也查
fmeta2 = {}
for s in fst.iter_symbols():
    if s.name:
        fmeta2[s.name] = (s['st_info']['type'], s['st_size'])

missing = [n for n in F if n not in ours]

CRT = {'_start', 'call_weak_fn', 'register_tm_clones', 'deregister_tm_clones',
       'frame_dummy', '__do_global_dtors_aux'}
AEABI = {'__aeabi_idiv', '__aeabi_uidiv'}

import re
buckets = {
    'CRT样板': [], '编译器内建': [], 'GCC分片(.part/.isra/.constprop)': [],
    '音效族(NOTYPE/size0)': [], '真缺口': [], '待定': [],
}
for n in sorted(missing):
    tsz = fmeta2.get(n, ('-', '-'))
    if n in CRT:
        buckets['CRT样板'].append(n)
    elif n in AEABI or n.startswith('__aeabi') or n.startswith('.div'):
        buckets['编译器内建'].append(n)
    elif ('.part' in n or '.isra' in n or '.constprop' in n):
        buckets['GCC分片(.part/.isra/.constprop)'].append(n)
    elif tsz[0] == 'STT_NOTYPE' or tsz[1] == 0:
        buckets['音效族(NOTYPE/size0)'].append(n)
    else:
        buckets['真缺口'].append(n)

for k, v in buckets.items():
    print('%-34s %2d 个' % (k, len(v)))
    for n in v:
        tsz = fmeta2.get(n, ('-', '-'))
        print('      %-44s 工厂type=%s size=%s' % (n, tsz[0], tsz[1]))

print()
print('合计:', sum(len(v) for v in buckets.values()))