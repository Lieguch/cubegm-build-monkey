#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""codegen_style_census —— 按**序言形态**给工厂函数分档，判断哪些 TU 用了不同的优化档。

为什么（2026-09-27）：
  工厂 DWARF 只覆盖 8 个 CRT/glibc CU ⇒ **应用对象没有 DWARF**，拿不到 per-TU 的 `-O`。
  但代码本身会说话：
    · **-O0 典型序言**：`push {r7}` / `sub sp, sp, #N` / `add r7, sp, #0`，然后把 **r0..r3 逐个 str 到 [r7,#..]**
      （帧指针 + 参数全部落栈，不做寄存器分配）。
    · **-O2 典型序言**：`push {r4,lr}`/`push {r4,r5,r6,lr}`，参数留在 r0..r3 里直接用。
  实测：`cns11643_1_mbtowc`（libiconv）是第一种；`mxmlDelete`（应用）是第二种。
  ⇒ 若某一族函数**整族**是第一种，就能判定"该 TU 用了不同优化档"，从而**按档重编**（根治 ABI 位移）。

判据（机械）：
  O0_STYLE = 前 8 条指令内同时出现 `add r7, sp`（帧指针建立）与 ≥2 条 `str r[0-3], [r7`（参数落栈）
  其余记 OTHER。按前缀分族统计。
"""
import collections
import sys

from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN


def classify(e, s):
    va = s['st_value'] & ~1
    thumb = bool(s['st_value'] & 1)
    if not isinstance(s['st_shndx'], int):
        return None
    sec = e.get_section(s['st_shndx'])
    if sec is None:
        return None
    off = va - sec['sh_addr']
    code = sec.data()[off:off + max(s['st_size'], 4)]
    md = Cs(CS_ARCH_ARM, (CS_MODE_THUMB if thumb else CS_MODE_ARM) | CS_MODE_LITTLE_ENDIAN)
    fp_setup = False
    arg_spills = 0
    cnt = 0
    for i in md.disasm(code, va):
        t = '%s %s' % (i.mnemonic, i.op_str)
        if i.mnemonic in ('add', 'mov') and 'r7, sp' in t.replace('#0', ''):
            fp_setup = True
        _ops = [x.strip() for x in i.op_str.split(',')] if i.op_str else []
        # `str r0, [r7, #0xc]` ⇒ ops[0]='r0' 是**源**，[r7,...] 是目标
        if i.mnemonic.startswith('str') and len(_ops) >= 2 and _ops[0] in ('r0', 'r1', 'r2', 'r3') \
                and _ops[1].startswith('[r7'):
            arg_spills += 1
        cnt += 1
        if cnt >= 8:
            break
    return 'O0_STYLE' if (fp_setup and arg_spills >= 2) else 'OTHER'


def family(n):
    for p in ('mxml', 'unz', 'TUnzip', 'luf', 'stbtt', 'xmp3', 'MP3', 'cns11643',
              'big5', 'hkscs', 'cp1', 'iso2022', 'euc_', 'utf', 'ucs', 'ascii', 'koi8',
              'gbk', 'gb2312', 'iconv', 'localcharset', 'aliases'):
        if n.startswith(p) or p in n:
            return 'libiconv' if p in ('cns11643', 'big5', 'hkscs', 'cp1', 'iso2022', 'euc_',
                                       'utf', 'ucs', 'ascii', 'koi8', 'gbk', 'gb2312',
                                       'iconv', 'localcharset', 'aliases') else p
    return 'other'


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'golden/factory.rkgame.bin'
    e = ELFFile(open(path, 'rb'))
    st = e.get_section_by_name('.symtab')
    fam = collections.defaultdict(lambda: collections.Counter())
    tot = collections.Counter()
    examples = collections.defaultdict(list)
    for s in st.iter_symbols():
        if not s.name or s['st_info']['type'] != 'STT_FUNC' or s['st_size'] == 0:
            continue
        k = classify(e, s)
        if k is None:
            continue
        f = family(s.name)
        fam[f][k] += 1
        tot[k] += 1
        if len(examples[(f, k)]) < 3:
            examples[(f, k)].append('%s @0x%x(%s)' % (s.name, s['st_value'],
                                                      'T' if s['st_value'] & 1 else 'A'))
    print('=== %s ===' % path)
    print('总计: %s' % dict(tot))
    print()
    print('%-14s %-10s %-8s %s' % ('族', 'O0_STYLE', 'OTHER', '样例(O0_STYLE)'))
    for f in sorted(fam):
        c = fam[f]
        print('%-14s %-10d %-8d %s' % (f, c['O0_STYLE'], c['OTHER'],
                                       '; '.join(examples[(f, 'O0_STYLE')])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
