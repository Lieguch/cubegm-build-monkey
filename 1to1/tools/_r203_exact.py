#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203 精确口径：835 工厂符号在产物里的类型分布（FUNC/OBJECT/缺失），
消除"47 vs 50 缺失"的同一分母两值假象。"""
import json
from elftools.elf.elffile import ELFFile

F = json.load(open('golden/factory.funcs.json', encoding='utf-8'))['functions']
names = set(F.keys())
print('factory.funcs.json 键数 =', len(names))

e = ELFFile(open('build/rkgame.rebuilt.elf', 'rb'))
st = e.get_section_by_name('.symtab')

func = {}   # name -> size
obj = {}    # name -> size
for s in st.iter_symbols():
    n = s.name
    if not n or n not in names:
        continue
    t = s['st_info']['type']
    sz = s['st_size']
    if t == 'STT_FUNC' and sz > 0:
        func[n] = sz
    elif t == 'STT_OBJECT':
        obj[n] = sz

defined_any = set(func) | set(obj)
missing = sorted(names - defined_any)

print('产物 FUNC+size>0 命中数        =', len(func))
print('产物 OBJECT（工厂函数名）命中数 =', len(obj))
print('=> 定义口径 FUNC+OBJECT        =', len(defined_any))
print('=> 缺失（只按 FUNC 口径）       =', len(missing))
print('=> 缺失（FUNC+OBJECT 口径）     =', 835 - len(defined_any))
print()
print('★ 只以 OBJECT 存在的工厂"函数"（3 个差异的源头）:')
for n, sz in sorted(obj.items(), key=lambda kv: -kv[1]):
    print('      %-44s OBJECT size=%d' % (n, sz))
print()
print('缺失清单(%d):' % len(missing))
for n in missing:
    print('      ', n)