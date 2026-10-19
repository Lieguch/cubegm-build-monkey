#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203：反汇编 4 处 .fimg_text 引用点上下文，判定"数据引用 vs 代码跳转"。"""
from elftools.elf.elffile import ELFFile
import struct
import capstone

d = open('build/rkgame.rebuilt.elf', 'rb').read()
e = ELFFile(open('build/rkgame.rebuilt.elf', 'rb'))
ft = [s for s in e.iter_sections() if s.name == '.fimg_text'][0]
text = e.get_section_by_name('.text')
lo, hi = ft['sh_addr'], ft['sh_addr'] + ft['sh_size']

hits = []
for off in range(text['sh_offset'], text['sh_offset'] + text['sh_size'] - 3, 4):
    w = struct.unpack_from('<I', d, off)[0]
    if lo <= w < hi:
        vaddr = text['sh_addr'] + (off - text['sh_offset'])
        hits.append((vaddr, w))

md_arm = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
md_th = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

# 反查归属函数
st = e.get_section_by_name('.symtab')
funcs = sorted([(s['st_value'], s['st_size'], s.name) for s in st.iter_symbols()
                if s['st_info']['type'] == 'STT_FUNC' and s['st_size'] > 0])

for v, w in hits:
    owner = '?'
    for fv, fsz, fn in funcs:
        if fv <= v < fv + fsz:
            owner = fn
            break
    # 反汇编引用点前后 4 条指令（Thumb）
    base = v - 8
    code = d[text['sh_offset'] + (base - text['sh_addr']):
             text['sh_offset'] + (base - text['sh_addr']) + 20]
    ins = list(md_th.disasm(code, base))
    print('== 引用点 0x%x -> 0x%x  属于 %s ==' % (v, w, owner))
    for i in ins:
        mark = ' <== 常量' if (i.address == v or i.address + 4 == v) else ''
        print('    0x%x: %-8s %s%s' % (i.address, i.mnemonic, i.op_str, mark))
    # 目标地址是不是函数开头？
    tgt_owner = '?'
    for fv, fsz, fn in funcs:
        if fv <= w < fv + fsz:
            tgt_owner = '%s+0x%x' % (fn, w - fv)
            break
    # 目标在工厂 funcs 里查
    import json
    F = json.load(open('golden/factory.funcs.json', encoding='utf-8'))
    lab = F['labels'].get(hex(w))
    print('    目标 0x%x => 工厂符号: %s | 我方函数: %s' % (w, lab, tgt_owner))
    print()