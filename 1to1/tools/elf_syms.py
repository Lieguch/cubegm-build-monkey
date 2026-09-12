#!/usr/bin/env python3
"""
elf_syms.py — 极简 ELF32 符号表读取器（零依赖，仅用标准库 struct）。

用途：P3 链接就绪审计。对每个 .o 提取：
  - DEFINED : 本对象提供的符号（FUNC/OBJECT，已定义，非 COMMON）
  - COMMON  : 暂定定义（SHN_COMMON，链接期由链接器合并，不构成重复定义错误）
  - UNDEF   : 未定义引用（需要别人提供）

输出格式（TAB 分隔，便于 shell 聚合）：
  <kind>\t<symname>\t<objfile>

用法:
  python3 tools/elf_syms.py <file.o> [...]
  python3 tools/elf_syms.py --selftest
"""
import struct
import sys

SHT_SYMTAB = 2
SHN_UNDEF = 0
SHN_ABS = 0xFFF1
SHN_COMMON = 0xFFF2

STB_LOCAL, STB_GLOBAL, STB_WEAK = 0, 1, 2
STT_OBJECT, STT_FUNC, STT_SECTION, STT_FILE = 1, 2, 3, 4


def read_syms(path):
    """返回 (defined, common, undef, err)。每项为 (name, bind, type)。"""
    try:
        d = open(path, 'rb').read()
    except OSError as e:
        return [], [], [], 'open: %s' % e
    if len(d) < 52 or d[:4] != b'\x7fELF':
        return [], [], [], 'not ELF'
    if d[4] != 1:
        return [], [], [], 'not ELF32'
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    e_shentsize = struct.unpack_from('<H', d, 46)[0]
    e_shnum = struct.unpack_from('<H', d, 48)[0]
    if not e_shoff or not e_shnum:
        return [], [], [], 'no section headers'

    shs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        if off + 40 > len(d):
            break
        name, stype, flags, addr, sh_off, size, link, info, align, entsize = \
            struct.unpack_from('<10I', d, off)
        shs.append(dict(name=name, type=stype, off=sh_off, size=size,
                        link=link, entsize=entsize))
    if not shs:
        return [], [], [], 'no sections'

    # 段名字符串表
    strtab_off = 0
    # 找 .shstrtab 需要 e_shstrndx；本工具不需要段名，跳过

    symtab = next((s for s in shs if s['type'] == SHT_SYMTAB), None)
    if not symtab:
        # 无符号表（如纯数据或已 strip 的 .o）——不是错误
        return [], [], [], None

    link = symtab['link']
    stroff = shs[link]['off'] if link < len(shs) else 0
    ent = symtab['entsize'] or 16
    n = symtab['size'] // ent

    defined, common, undef = [], [], []
    for i in range(n):
        off = symtab['off'] + i * ent
        if off + 16 > len(d):
            break
        st_name, st_value, st_size, st_info, st_other, st_shndx = \
            struct.unpack_from('<IIIBBH', d, off)
        if st_name == 0:
            continue
        end = d.index(b'\x00', stroff + st_name)
        nm = d[stroff + st_name:end].decode('utf-8', 'replace')
        bind = st_info >> 4
        typ = st_info & 0xF
        if typ in (STT_SECTION, STT_FILE):
            continue
        if st_shndx == SHN_UNDEF:
            undef.append((nm, bind, typ))
        elif st_shndx == SHN_COMMON:
            common.append((nm, bind, typ))
        elif st_shndx == SHN_ABS:
            defined.append((nm, bind, typ))
        else:
            defined.append((nm, bind, typ))
    return defined, common, undef, None


def selftest():
    """用极小样例自检（若可编译）。"""
    import subprocess, tempfile, os
    src = 'extern int foo(int);\nint bar(int x){return foo(x)+1;}\nint gvar=3;\n'
    z = os.environ.get('ZIG', 'zig')
    td = tempfile.mkdtemp()
    c = os.path.join(td, 't.c')
    o = os.path.join(td, 't.o')
    open(c, 'w').write(src)
    r = subprocess.run([z, 'cc', '-c', '-O1', '-target', 'arm-linux-gnueabihf',
                        '-mfloat-abi=hard', '-mfpu=neon', c, '-o', o],
                       capture_output=True)
    if r.returncode != 0:
        print('SELFTEST SKIP (compile failed):', r.stderr.decode()[:200])
        return 0
    de, co, un, err = read_syms(o)
    dn = sorted(x[0] for x in de)
    un_n = sorted(x[0] for x in un)
    ok = ('bar' in dn) and ('gvar' in dn) and ('foo' in un_n)
    print('defined=%s undef=%s -> %s' % (dn, un_n, 'OK' if ok else 'FAIL'))
    return 0 if ok else 1


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 1
    if args[0] == '--selftest':
        return selftest()
    rc = 0
    for p in args:
        de, co, un, err = read_syms(p)
        if err:
            sys.stderr.write('WARN %s: %s\n' % (p, err))
            rc = 1
            continue
        for nm, b, t in de:
            # ★ LOCAL 符号（.L.str / $a / $d ...）是文件作用域，多对象重名合法，
            #   不构成链接期重复定义；单独打 LOCAL 供统计，不参与重复判定。
            kind = 'DEFINED' if b in (STB_GLOBAL, STB_WEAK) else 'LOCAL'
            print('%s\t%s\t%s' % (kind, nm, p))
        for nm, b, t in co:
            print('COMMON\t%s\t%s' % (nm, p))
        for nm, b, t in un:
            print('UNDEF\t%s\t%s' % (nm, p))
    return rc


if __name__ == '__main__':
    sys.exit(main())
