#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203 审计：段布局 + dynsym strdup/islower 两侧对拍（临时，读产物与工厂）。"""
import sys
from elftools.elf.elffile import ELFFile

for tag, p in [('我方', 'build/rkgame.rebuilt.elf'), ('工厂', 'golden/factory.rkgame.bin')]:
    with open(p, 'rb') as f:
        e = ELFFile(f)
        print('==== %s  %s' % (tag, p))
        print('  -- 段布局 --')
        for s in e.iter_sections():
            n = s.name
            if n in ('.text', '.rodata', '.data', '.bss', '.plt', '.got', '.got.plt') \
               or n.startswith('.fimg'):
                print('    %-16s addr=0x%-8x off=0x%-8x size=%-9d flags=0x%x'
                      % (n, s['sh_addr'], s['sh_offset'], s['sh_size'], s['sh_flags']))
        ds = e.get_section_by_name('.dynsym')
        print('  -- dynsym: strdup / islower --')
        if ds:
            for sym in ds.iter_symbols():
                if sym.name and ('strdup' in sym.name or sym.name == 'islower'):
                    print('    %-18s type=%s bind=%s shndx=%s size=%s'
                          % (sym.name, sym['st_info']['type'], sym['st_info']['bind'],
                             sym['st_shndx'], sym['st_size']))
        # 工厂函数规模（用于刻度 A/C）
        st = e.get_section_by_name('.symtab') or e.get_section_by_name('.dynsym')
        print('  -- 符号表统计（FUNC 且 size>0）--')
        if st:
            cnt = sum(1 for sym in st.iter_symbols()
                      if sym['st_info']['type'] == 'STT_FUNC' and sym['st_size'] > 0)
            print('    FUNC&size>0 = %d' % cnt)
        print()