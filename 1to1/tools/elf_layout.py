#!/usr/bin/env python3
"""
elf_layout.py — 导出 ELF32 的段（Program Header）+ 节（Section Header）布局。

用途（P3 链接）：重建产物必须复刻工厂二进制的**内存映射**，因为反编译代码里
烧死了绝对地址（如 `DrawSelectBar((int *)0x3afc44)`）——段地址一偏，这些地址全失效。

输出：
  1) 人读报告（stdout / ledger/factory_layout_report.txt）
  2) 机读 TSV（ledger/factory_layout.tsv：kind  name  vaddr  filesz  memsz  flags  offset  align）

用法:
  python3 tools/elf_layout.py <elf> [out.tsv]
"""
import os
import struct
import sys

PT = {0: 'NULL', 1: 'LOAD', 2: 'DYNAMIC', 3: 'INTERP', 4: 'NOTE', 6: 'PHDR',
      7: 'TLS', 0x6474e550: 'GNU_EH_FRAME', 0x6474e551: 'GNU_STACK',
      0x6474e552: 'GNU_RELRO', 0x70000001: 'ARM_EXIDX'}
PF = {1: 'X', 2: 'W', 4: 'R'}


def parse(path):
    d = open(path, 'rb').read()
    if d[:4] != b'\x7fELF' or d[4] != 1:
        raise SystemExit('not ELF32: %s' % path)
    (e_type, e_machine) = struct.unpack_from('<HH', d, 16)
    (e_entry, e_phoff, e_shoff, e_flags) = struct.unpack_from('<IIII', d, 24)
    (e_ehsize, e_phentsize, e_phnum) = struct.unpack_from('<HHH', d, 40)
    (e_shentsize, e_shnum, e_shstrndx) = struct.unpack_from('<HHH', d, 46)

    phs = []
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
            struct.unpack_from('<8I', d, o)
        phs.append(dict(type=p_type, offset=p_offset, vaddr=p_vaddr, paddr=p_paddr,
                        filesz=p_filesz, memsz=p_memsz, flags=p_flags, align=p_align))

    shs = []
    if e_shoff and e_shnum:
        # 先取 shstrtab
        o = e_shoff + e_shstrndx * e_shentsize
        _, _, _, _, str_off, str_sz = struct.unpack_from('<6I', d, o)
        for i in range(e_shnum):
            o = e_shoff + i * e_shentsize
            (sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link,
             sh_info, sh_addralign, sh_entsize) = struct.unpack_from('<10I', d, o)
            end = d.index(b'\x00', str_off + sh_name)
            nm = d[str_off + sh_name:end].decode('utf-8', 'replace')
            shs.append(dict(name=nm, type=sh_type, flags=sh_flags, addr=sh_addr,
                            offset=sh_offset, size=sh_size, align=sh_addralign,
                            entsize=sh_entsize))
    return dict(e_type=e_type, e_machine=e_machine, e_entry=e_entry, e_flags=e_flags,
                phoff=e_phoff, shoff=e_shoff, phs=phs, shs=shs, size=len(d), data=d)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    p = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'ledger', 'factory_layout.tsv')
    E = parse(p)

    L = []
    A = L.append
    A('=' * 74)
    A('ELF 布局：%s' % os.path.basename(p))
    A('=' * 74)
    A('e_type=0x%x  e_machine=0x%x  e_flags=0x%x  entry=0x%08x  size=%d' %
      (E['e_type'], E['e_machine'], E['e_flags'], E['e_entry'], E['size']))
    A('')
    A('--- Program Headers（内存映射）---')
    A('%-16s %10s %10s %10s %10s %6s %8s' %
      ('type', 'offset', 'vaddr', 'filesz', 'memsz', 'flags', 'align'))
    for ph in E['phs']:
        fl = ''.join(v for k, v in PF.items() if ph['flags'] & k)
        A('%-16s 0x%08x 0x%08x 0x%08x 0x%08x %6s 0x%08x' %
          (PT.get(ph['type'], hex(ph['type'])), ph['offset'], ph['vaddr'],
           ph['filesz'], ph['memsz'], fl, ph['align']))
    A('')
    A('--- Section Headers（节）---')
    A('%-18s %10s %10s %10s %10s' % ('name', 'addr', 'offset', 'size', 'align'))
    for sh in E['shs']:
        if sh['name'] in ('.text', '.rodata', '.data', '.bss', '.data.rel.ro',
                          '.init_array', '.fini_array', '.got', '.plt', '.dynamic',
                          '.interp', '.ARM.exidx', '.rel.dyn', '.rel.plt', '.dynsym',
                          '.dynstr', '.gnu.version', '.gnu.hash', '.hash', '.comment',
                          '.shstrtab', '.symtab', '.strtab'):
            A('%-18s 0x%08x 0x%08x 0x%08x 0x%08x' %
              (sh['name'], sh['addr'], sh['offset'], sh['size'], sh['align']))

    txt = '\n'.join(L) + '\n'
    sys.stdout.write(txt)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out.replace('.tsv', '_report.txt'), 'w', encoding='utf-8').write(txt)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('kind\tname\tvaddr\tfilesz\tmemsz\tflags\toffset\talign\n')
        for ph in E['phs']:
            f.write('PH\t%s\t%08x\t%08x\t%08x\t%x\t%08x\t%08x\n' %
                    (PT.get(ph['type'], hex(ph['type'])), ph['vaddr'], ph['filesz'],
                     ph['memsz'], ph['flags'], ph['offset'], ph['align']))
        for sh in E['shs']:
            f.write('SH\t%s\t%08x\t%08x\t%08x\t%x\t%08x\t%08x\n' %
                    (sh['name'], sh['addr'], sh['size'], sh['size'], sh['flags'],
                     sh['offset'], sh['align']))
    sys.stderr.write('report -> %s\n' % out.replace('.tsv', '_report.txt'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
