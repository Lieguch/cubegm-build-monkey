#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""elf_header_diff.py —— **ELF 头部/装载侧的可执行性对比**（工厂 vs 我方产物）

为什么要有它
------------------------------------------------------------------
真机表现是「无法开机 + 零日志」。零日志意味着**我们自己的代码一行都没跑**，
所以嫌疑集中在「内核/ld.so 是否愿意加载这个文件」这一层。
本工具把「加载前就能判定、且能单独说明哪一项不同」的字段全部列出来，
逐项与工厂对比 —— 而不是继续在行为尺（DIVERGE）上打磨。

只看**加载语义相关**的字段，不做行为判据：
  · ELF 头：EI_CLASS/DATA/VERSION/OSABI/ABIVERSION、e_type/e_machine/e_version/e_flags/e_entry
  · PT_INTERP 的**实际字符串**（长度、路径是否存在于设备侧清单）
  · PT_GNU_STACK / PT_GNU_RELRO / PT_GNU_EH_FRAME / PT_ARM_EXIDX 等各段
  · 节：.ARM.attributes（浮点 ABI）、.note.gnu.build-id、.interp、.note.ABI-tag
  · DT_NEEDED 清单、DT_FLAGS_1、DT_BIND_NOW、DT_RPATH/RUNPATH（**主机路径泄漏是硬伤**）

用法
    python tools/elf_header_diff.py build/rkgame.rebuilt.elf golden/factory.rkgame.bin
退出码：0 = 打印完成；11 = 读不到输入（硬失败）
"""
import io
import struct
import sys

PT = {0: 'PT_NULL', 1: 'PT_LOAD', 2: 'PT_DYNAMIC', 3: 'PT_INTERP', 4: 'PT_NOTE',
      5: 'PT_SHLIB', 6: 'PT_PHDR', 7: 'PT_TLS',
      0x6474e550: 'PT_GNU_EH_FRAME', 0x6474e551: 'PT_GNU_STACK',
      0x6474e552: 'PT_GNU_RELRO', 0x6474e553: 'PT_GNU_PROPERTY',
      0x70000001: 'PT_ARM_EXIDX', 0x70000000: 'PT_ARM_ARCHEXT'}
E_TYPE = {1: 'REL', 2: 'EXEC', 3: 'DYN', 4: 'CORE'}
E_MACH = {40: 'ARM'}
EF_ARM = {0x0200: 'EF_ARM_ABI_FLOAT_SOFT', 0x0400: 'EF_ARM_ABI_FLOAT_HARD'}
SHT = {0: 'NULL', 1: 'PROGBITS', 2: 'SYMTAB', 3: 'STRTAB', 7: 'NOTE', 8: 'NOBITS',
       9: 'REL', 0x6ffffff6: 'GNU_HASH', 0x6ffffffd: 'GNU_verdef',
       0x70000001: 'ARM_EXIDX', 0x70000003: 'ARM_ATTRIBUTES'}


def load(path):
    try:
        d = io.open(path, 'rb').read()
    except Exception as e:
        print('!! 读不到输入 %s: %s' % (path, e))
        sys.exit(11)
    if d[:4] != b'\x7fELF':
        print('!! %s 不是 ELF' % path)
        sys.exit(11)
    return d


def cstr(d, off):
    e = d.find(b'\x00', off)
    return d[off:e].decode('latin-1')


def analyse(path, d):
    r = {}
    r['path'] = path
    r['size'] = len(d)
    r['EI_CLASS'] = d[4]
    r['EI_DATA'] = d[5]
    r['EI_VERSION'] = d[6]
    r['EI_OSABI'] = d[7]
    r['EI_ABIVERSION'] = d[8]
    # ★ 必须按真实布局解：e_type/e_machine 是 2 字节，其后才是 4 字节字段。
    #   （用 '<7I' 从 16 读会整体错位，e_type 变成 0x280002、e_shoff 变成垃圾值。）
    e_type, e_machine = struct.unpack_from('<HH', d, 16)
    e_version, e_entry, e_phoff, e_shoff, e_flags = struct.unpack_from('<5I', d, 20)
    r['e_type'] = e_type
    r['e_machine'] = e_machine
    r['e_version'] = e_version
    r['e_entry'] = e_entry
    r['e_flags'] = e_flags
    r['ehsize'] = struct.unpack_from('<H', d, 40)[0]
    r['phentsize'] = struct.unpack_from('<H', d, 42)[0]
    r['phnum'] = struct.unpack_from('<H', d, 44)[0]
    r['shentsize'] = struct.unpack_from('<H', d, 46)[0]
    r['shnum'] = struct.unpack_from('<H', d, 48)[0]
    r['shstrndx'] = struct.unpack_from('<H', d, 50)[0]

    r['ph'] = []
    for i in range(r['phnum']):
        o = e_phoff + i * r['phentsize']
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        r['ph'].append(dict(i=i, type=t, off=off, vaddr=va, paddr=pa,
                            filesz=fsz, memsz=msz, flags=fl, align=al))

    # INTERP
    r['interp'] = None
    for p in r['ph']:
        if p['type'] == 3:
            r['interp'] = cstr(d, p['off'])

    # 节表（必须做边界防护：裸 ELF / 节表被误写的产物会让 e_shoff 越界）
    r['sh'] = []
    r['sh_note'] = None
    sh_ok = (e_shoff != 0 and r['shnum'] > 0
             and e_shoff + r['shnum'] * r['shentsize'] <= len(d))
    if not sh_ok:
        r['sh_note'] = ('节表不可用：e_shoff=0x%x shnum=%d shentsize=%d 文件=%d'
                        % (e_shoff, r['shnum'], r['shentsize'], len(d)))
    if sh_ok:
        shstr_off = None
        if r['shstrndx'] and r['shstrndx'] < r['shnum']:
            o = e_shoff + r['shstrndx'] * r['shentsize']
            # ★ 节头布局：name(0) type(4) flags(8) addr(12) **offset(16)** size(20) …
            #   旧写法用 `<10I` 取第 10 个字段（= entsize）当 shstrtab 偏移 ⇒ 全表名字变成 '?'。
            sh_off = struct.unpack_from('<I', d, o + 16)[0]
            if sh_off < len(d):
                shstr_off = sh_off
        for i in range(r['shnum']):
            o = e_shoff + i * r['shentsize']
            name, typ, flags, addr, offset, size, link, info, align, entsize = struct.unpack_from('<10I', d, o)
            nm = cstr(d, shstr_off + name) if shstr_off is not None else '?'
            r['sh'].append(dict(name=nm, type=typ, addr=addr, offset=offset, size=size))

    # 动态段
    r['needed'] = []
    r['dt'] = {}
    for p in r['ph']:
        if p['type'] == 2:  # PT_DYNAMIC
            off = p['off']
            end = off + p['filesz']
            strtab = None
            ents = []
            while off + 8 <= end:
                tag, val = struct.unpack_from('<iI', d, off)
                ents.append((tag, val))
                off += 8
                if tag == 0:
                    break
            for tag, val in ents:
                if tag == 5:  # DT_STRTAB
                    for q in r['ph']:
                        if q['type'] == 1 or q['type'] == 4:
                            if q['vaddr'] <= val < q['vaddr'] + max(q['filesz'], q['memsz']):
                                strtab = q['off'] + (val - q['vaddr'])
                    r['dt']['DT_STRTAB'] = val
                elif tag == 1:  # DT_NEEDED
                    ents.append(('NEEDED_PENDING', val))
            if strtab is not None:
                for tag, val in ents:
                    if tag == 1:
                        r['needed'].append(cstr(d, strtab + val))
                    elif tag in (14, 15, 29, 30):  # SONAME/RPATH/RUNPATH/FLAGS1
                        r['dt'][{14: 'DT_SONAME', 15: 'DT_RPATH', 29: 'DT_RUNPATH', 30: 'DT_FLAGS_1'}.get(tag, str(tag))] = cstr(d, strtab + val)
                    elif tag in (8, 12, 24, 26):  # FLAGS/BIND_NOW/INIT/INIT_ARRAY
                        key = {8: 'DT_FLAGS', 12: 'DT_BIND_NOW', 24: 'DT_INIT', 26: 'DT_INIT_ARRAY'}.get(tag)
                        if tag == 8:
                            r['dt']['DT_FLAGS'] = val
                        elif tag in (24, 26):
                            r['dt'][key] = val
                        else:
                            r['dt'][key] = True
            break
    return r


def show(tag, a, b):
    same = (a == b)
    mark = '  ' if same else '★ '
    print('%s%-14s | %-34s | %-34s' % (mark, tag, a, b))
    return same


def main():
    if len(sys.argv) < 3:
        print('用法: python tools/elf_header_diff.py <ours> <factory>')
        return 11
    da, db = load(sys.argv[1]), load(sys.argv[2])
    A = analyse(sys.argv[1], da)
    B = analyse(sys.argv[2], db)
    print('=' * 108)
    print('ELF 加载侧逐字段对比   ★ = 不同')
    print('  左 = 我方产物：%s' % A['path'])
    print('  右 = 原厂    ：%s' % B['path'])
    print('=' * 108)
    print('%-16s | %-34s | %-34s' % ('字段', '我方', '原厂'))
    print('-' * 108)
    show('size', A['size'], B['size'])
    show('EI_CLASS', A['EI_CLASS'], B['EI_CLASS'])
    show('EI_DATA', A['EI_DATA'], B['EI_DATA'])
    show('EI_OSABI', A['EI_OSABI'], B['EI_OSABI'])
    show('EI_ABIVERSION', A['EI_ABIVERSION'], B['EI_ABIVERSION'])
    show('e_type', E_TYPE.get(A['e_type'], A['e_type']), E_TYPE.get(B['e_type'], B['e_type']))
    show('e_machine', E_MACH.get(A['e_machine'], A['e_machine']), E_MACH.get(B['e_machine'], B['e_machine']))
    show('e_flags', '0x%x %s' % (A['e_flags'], ' '.join(v for k, v in EF_ARM.items() if A['e_flags'] & k)),
         '0x%x %s' % (B['e_flags'], ' '.join(v for k, v in EF_ARM.items() if B['e_flags'] & k)))
    show('e_entry', '0x%x' % A['e_entry'], '0x%x' % B['e_entry'])
    show('phnum', A['phnum'], B['phnum'])
    show('INTERP', A['interp'], B['interp'])
    print()
    print('--- PT 段 ---')
    print('%-16s | %-34s | %-34s' % ('PT_LOAD', '我方', '原厂'))
    for p in A['ph']:
        if p['type'] == 1:
            print('  L  v=0x%-9x fsz=0x%-8x msz=0x%-8x fl=%d al=0x%x' % (p['vaddr'], p['filesz'], p['memsz'], p['flags'], p['align']))
    print('  ---')
    for p in B['ph']:
        if p['type'] == 1:
            print('  L  v=0x%-9x fsz=0x%-8x msz=0x%-8x fl=%d al=0x%x' % (p['vaddr'], p['filesz'], p['memsz'], p['flags'], p['align']))
    print()
    for p in A['ph']:
        if p['type'] != 1:
            q = [x for x in B['ph'] if x['type'] == p['type']]
            qs = ('v=0x%x fsz=%d msz=%d fl=%d' % (q[0]['vaddr'], q[0]['filesz'], q[0]['memsz'], q[0]['flags'])) if q else '(工厂无)'
            print('★ %-22s 我: v=0x%-9x fsz=%-8d msz=%-10d fl=%d | 厂: %s'
                  % (PT.get(p['type'], hex(p['type'])), p['vaddr'], p['filesz'], p['memsz'], p['flags'], qs))
    for p in B['ph']:
        if p['type'] != 1 and not [x for x in A['ph'] if x['type'] == p['type']]:
            print('★ %-22s 我: (我方无) | 厂: v=0x%x fsz=%d msz=%d fl=%d'
                  % (PT.get(p['type'], hex(p['type'])), p['vaddr'], p['filesz'], p['memsz'], p['flags']))
    print()
    print('--- DT_NEEDED / 主机路径泄漏 ---')
    print('我方 NEEDED (%d): %s' % (len(A['needed']), A['needed']))
    print('原厂 NEEDED (%d): %s' % (len(B['needed']), B['needed']))
    print('我方 DT: %s' % A['dt'])
    print('原厂 DT: %s' % B['dt'])
    print()
    print('--- 关键字节 ---')
    if A.get('sh_note'):
        print('★ 我方 %s' % A['sh_note'])
    if B.get('sh_note'):
        print('★ 原厂 %s' % B['sh_note'])
    for k in ('.interp', '.ARM.attributes', '.note.gnu.build-id', '.note.ABI-tag', '.ARM.exidx', '.dynamic'):
        sa = [s for s in A['sh'] if s['name'] == k]
        sb = [s for s in B['sh'] if s['name'] == k]
        f = lambda xs: ('addr=0x%x size=%d' % (xs[0]['addr'], xs[0]['size'])) if xs else '(无)'
        mark = '  ' if f(sa) == f(sb) else '★ '
        print('%s%-22s 我: %-30s 厂: %s' % (mark, k, f(sa), f(sb)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
