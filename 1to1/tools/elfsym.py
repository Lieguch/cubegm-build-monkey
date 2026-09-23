# -*- coding: utf-8 -*-
"""极简 ELF32 符号化器：vaddr -> 段/节/最近符号（只读）"""
import struct, sys, bisect, os

class Elf32:
    def __init__(self, path):
        self.path = path
        self.b = open(path, 'rb').read()
        b = self.b
        assert b[:4] == b'\x7fELF', 'not ELF'
        assert b[4] == 1, 'not ELF32'
        self.type = struct.unpack_from('<H', b, 16)[0]
        self.machine = struct.unpack_from('<H', b, 18)[0]
        self.entry = struct.unpack_from('<I', b, 24)[0]
        e_phoff = struct.unpack_from('<I', b, 28)[0]
        e_shoff = struct.unpack_from('<I', b, 32)[0]
        e_phentsize, e_phnum = struct.unpack_from('<HH', b, 42)
        e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', b, 46)
        self.ph = []
        for i in range(e_phnum):
            o = e_phoff + i * e_phentsize
            p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
                struct.unpack_from('<8I', b, o)
            self.ph.append(dict(type=p_type, off=p_offset, vaddr=p_vaddr, filesz=p_filesz,
                                memsz=p_memsz, flags=p_flags, align=p_align))
        # sections
        shs = []
        for i in range(e_shnum):
            o = e_shoff + i * e_shentsize
            name, typ, flags, addr, off, size, link, info, align, entsize = \
                struct.unpack_from('<10I', b, o)
            shs.append(dict(nameoff=name, type=typ, addr=addr, off=off, size=size,
                            link=link, entsize=entsize))
        shstr = b''
        if e_shstrndx < len(shs):
            s = shs[e_shstrndx]
            shstr = b[s['off']:s['off'] + s['size']]
        def nm(x):
            e = shstr.find(b'\x00', x)
            return shstr[x:e].decode('utf-8', 'replace')
        for s in shs:
            s['name'] = nm(s['nameoff'])
        self.sh = shs
        self.syms = self._syms()

    def _syms(self):
        out = []
        for s in self.sh:
            if s['type'] not in (2, 11):  # SYMTAB, DYNSYM
                continue
            strtab = self.sh[s['link']]
            st = self.b[strtab['off']:strtab['off'] + strtab['size']]
            n = s['size'] // 16
            for i in range(n):
                o = s['off'] + i * 16
                nameoff, value, size, info, other, shndx = struct.unpack_from('<3I2BH', self.b, o)
                if value == 0:
                    continue
                e = st.find(b'\x00', nameoff)
                nmx = st[nameoff:e].decode('utf-8', 'replace')
                if nmx:
                    out.append((value, size, nmx, s['type']))
        out.sort()
        return out

    def addr2sym(self, addr):
        keys = [x[0] for x in self.syms]
        i = bisect.bisect_right(keys, addr) - 1
        if i < 0:
            return None, 0
        v, sz, nmx, t = self.syms[i]
        return nmx, addr - v

    def addr2seg(self, addr):
        for p in self.ph:
            if p['vaddr'] <= addr < p['vaddr'] + p['memsz']:
                return p
        return None

    def addr2file(self, addr):
        p = self.addr2seg(addr)
        if not p:
            return None
        d = addr - p['vaddr']
        if d >= p['filesz']:
            return None
        return p['off'] + d

    def addr2sec(self, addr):
        for s in self.sh:
            if s['type'] != 8 and s['addr'] and s['addr'] <= addr < s['addr'] + s['size']:
                return s['name']
        return None

FLAG = {1: 'X', 2: 'W', 4: 'R'}


def describe(path, addrs=(), verbose=True):
    """打印 ELF32 程序头/节表，并把 addrs 逐个落位到 节/段/文件偏移/符号。"""
    e = Elf32(path)
    if verbose:
        print('=' * 96)
        print('ELF: %s' % path)
        print('  size=%d  e_type=%d(2=EXEC,3=DYN)  machine=%d(40=ARM)  entry=0x%08x' %
              (os.path.getsize(path), e.type, e.machine, e.entry))
        print('  程序头 %d 个:' % len(e.ph))
        for p in e.ph:
            kind = 'LOAD ' if p['type'] == 1 else 'PT_%-4d' % p['type']
            print('    %s vaddr=0x%08x off=0x%08x filesz=0x%08x memsz=0x%08x align=0x%-6x flags=%s' %
                  (kind, p['vaddr'], p['off'], p['filesz'], p['memsz'], p['align'],
                   ''.join(FLAG.get(f, '?') for f in (4, 2, 1) if p['flags'] & f) or '-'))
        print('  符号 %d 个' % len(e.syms))
    for a in addrs:
        nmx, d = e.addr2sym(a)
        seg = e.addr2seg(a)
        print('  --- 地址 0x%08x ---' % a)
        print('     节   = %s' % e.addr2sec(a))
        print('     段   = %s' % ('vaddr=0x%08x/%s off=0x%08x' % (
            seg['vaddr'], ''.join(FLAG.get(f, '?') for f in (4, 2, 1) if seg['flags'] & f), seg['off'])
            if seg else '★ 不在任何 PT_LOAD 内'))
        fo = e.addr2file(a)
        print('     文件偏移 = %s' % ('0x%08x' % fo if fo is not None else '★ 超出 filesz'))
        print('     符号 = %s + 0x%x' % (nmx, d) if nmx else '     符号 = (无)')
    return e


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('用法: python tools/elfsym.py <elf> [addr ...]')
        sys.exit(2)
    addrs = [int(x, 16) for x in sys.argv[2:]]
    describe(sys.argv[1], addrs)
