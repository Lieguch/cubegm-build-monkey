#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203：遍历 cubegm-work/stock_cores 找真机 libemu_*.so，核实架构+retro符号。"""
import os
from elftools.elf.elffile import ELFFile
from elftools.elf.enums import ENUM_E_MACHINE

BASE = r'C:\Users\Administrator\cubegm-work\stock_cores'
so_files = []
for root, dirs, files in os.walk(BASE):
    for f in files:
        if f.startswith('libemu') and f.endswith('.so'):
            so_files.append(os.path.join(root, f))

print('找到 libemu_*.so =', len(so_files))
print()
print('%-28s %-12s %-8s %-9s' % ('文件', 'e_machine', 'retro数', '大小KB'))
for p in sorted(so_files):
    name = os.path.basename(p)
    size = os.path.getsize(p)
    try:
        with open(p, 'rb') as fh:
            e = ELFFile(fh)
            m = e.header['e_machine']
            mach = m if isinstance(m, str) else ENUM_E_MACHINE.get(m, '0x%x' % m)
            ds = e.get_section_by_name('.dynsym')
            retro = set()
            if ds:
                for s in ds.iter_symbols():
                    if s.name and s['st_shndx'] != 'SHN_UNDEF' and \
                       (s.name.startswith('retro_') or s.name == 'SetFrameSkip'):
                        retro.add(s.name)
            print('%-28s %-12s %-8d %-9d' % (name, mach, len(retro), size // 1024))
            if name in ('libemu_sfc.so', 'libemu_gpsp.so', 'libemu_nes.so',
                        'libemu_md.so', 'libemu_pcsx.so', 'libemu_tgbdual.so'):
                print('      => %s' % ', '.join(sorted(retro)))
    except Exception as ex:
        print('%-28s 解析失败: %s' % (name, ex))

# 也统计 cubegm 目录完整清单（rkgame/driver.so/icube 等）
for root, dirs, files in os.walk(BASE):
    if root.endswith('cubegm'):
        print()
        print('=== %s ===' % root)
        for f in sorted(files):
            print('   ', f)
        break