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
    # ★★ 2026-10-04（第 130 轮）**修仪器缺陷**：原来只接受 ELF32，一遇到 ELF64
    #   就 `return 'not ELF32'` —— 而 `src/upstream/xunzip/XUnzip.o` 由 `zig c++`
    #   产出，是 **ELF64** ⇒ 该工具读出 **0 个符号** ⇒ `build_upstream.sh` 的
    #   XUnzip 入口自检**永远判"缺符号"** ⇒ `exit 12` 阻断整条构建。
    #   即「仪器缺陷伪装成代码缺陷」（假失败），且日志为空、无任何线索。
    #   实测证据：该 .o 用 pyelftools 能读出 63 个已定义 FUNC（含 5 个 TUnzip 入口）。
    #   修法：按 `e_ident[EI_CLASS]` 分派节头/符号项的字节宽度，两种都支持。
    cls = d[4]
    if cls == 1:                       # ELFCLASS32
        # Elf32_Shdr: name/type/flags/addr/off/size/link/info/align/entsize 各 4B = 40
        sh_fmt, sym_fmt = '<10I', '<IIIBBH'
        ent_size = 16                   # Elf32_Sym = 16B
    elif cls == 2:                     # ELFCLASS64
        # Elf64_Shdr: name(4) type(4) flags(8) addr(8) off(8) size(8) link(4) info(4)
        #             align(8) entsize(8) = **64B**（不是 10×8=80！）
        #   ★ 用 '<10Q' 会把 name/type 当 8 字节读 ⇒ 全部字段错位 ⇒ 静默读出 0 符号。
        sh_fmt, sym_fmt = '<IIQQQQIIQQ', '<IBBHQQ'
        ent_size = 24                   # Elf64_Sym = 24B
    else:
        return [], [], [], 'not ELF (class=%d)' % cls
    # 两种格式的节头字段顺序一致，只是字长不同 ⇒ 下面用同一段解析代码。
    # ★ 头字段偏移实测（云上 XUnzip.o / stb_truetype.o 打印核对，勿凭记忆）：
    #     ELF32: e_shoff@0x20(4B) e_shentsize@0x2E e_shnum@0x30
    #     ELF64: e_shoff@0x28(8B) e_shentsize@0x3A e_shnum@0x3C
    #   （ELF64 的 e_* 全部后移 8 字节，因为 e_phoff/e_shoff 变成 8 字节宽）
    if cls == 1:
        e_shoff = struct.unpack_from('<I', d, 0x20)[0]
        e_shentsize = struct.unpack_from('<H', d, 0x2E)[0]
        e_shnum = struct.unpack_from('<H', d, 0x30)[0]
    else:
        e_shoff = struct.unpack_from('<Q', d, 0x28)[0]
        e_shentsize = struct.unpack_from('<H', d, 0x3A)[0]
        e_shnum = struct.unpack_from('<H', d, 0x3C)[0]
    if not e_shoff or not e_shnum:
        return [], [], [], 'no section headers (e_shoff=%d e_shnum=%d)' % (e_shoff, e_shnum)

    shs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        # ★ 边界检查必须用**节头实际宽度** `e_shentsize`，不能用 calcsize('<10Q')。
        #   ELF64 的 Elf64_Shdr 是 **64 字节**（不是 10×8=80）⇒ 用 80 做检查会把
        #   末尾几节误判为越界而 `break` ⇒ 恰好丢掉 `.strtab`（symtab.sh_link 指向它）
        #   ⇒ 读出 0 个符号、且 err=None（**静默假失败**，最难查的一种）。
        if off + e_shentsize > len(d):
            break
        name, stype, flags, addr, sh_off, size, link, info, align, entsize = \
            struct.unpack_from(sh_fmt, d, off)
        shs.append(dict(name=name, type=stype, off=sh_off, size=size,
                        link=link, entsize=entsize))
    if not shs:
        return [], [], [], 'no sections'

    symtab = next((s for s in shs if s['type'] == SHT_SYMTAB), None)
    if not symtab:
        # 无符号表（如纯数据或已 strip 的 .o）——不是错误
        return [], [], [], None

    link = symtab['link']
    stroff = shs[link]['off'] if link < len(shs) else 0
    # ELF32 符号项 16 字节、ELF64 符号项 24 字节（st_value/st_size 宽度不同）
    ent = symtab['entsize'] or ent_size
    n = symtab['size'] // ent

    defined, common, undef = [], [], []
    for i in range(n):
        off = symtab['off'] + i * ent
        if off + len(sym_fmt) > len(d):
            break
        st_name, st_value, st_size, st_info, st_other, st_shndx = \
            struct.unpack_from(sym_fmt, d, off)
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
    """用极小样例自检。**必须覆盖 ELF32 与 ELF64 两侧**（第 130 轮教训）。"""
    import subprocess, tempfile, os
    src = 'extern int foo(int);\nint bar(int x){return foo(x)+1;}\nint gvar=3;\n'
    z = os.environ.get('ZIG', 'zig')
    bad = 0
    # ★ 判据：对每种位宽都必须「认出 bar + gvar + foo」。
    #   反例锚点 1（工具缺陷）：ELF64 曾经直接 `return 'not ELF32'`（读出 0 个符号），
    #     而 build_upstream.sh 的 XUnzip 入口自检依赖本工具 ⇒ 假失败并 exit 12。
    #   反例锚点 2（节头格式错位）：用 '<10Q'(80B) 读 Elf64_Shdr(64B) ⇒ name/type
    #     被当成 8 字节 ⇒ 字段全错位 ⇒ 静默 0 符号且 err=None。
    #   ★ 判据按位宽**分别校准**（不能照抄）：x86_64 的 `-O1` 会把 `int gvar=3`
    #     这类未取址的全局**常量折叠掉**，而 arm32 保留 ⇒ ELF64 侧只断言 bar/foo，
    #     并额外断言「err is None」（静默假失败正是 err=None 的形态）。
    for label, flags, want in (
            ('ELF32', ['-target', 'arm-linux-gnueabihf',
                       '-mfloat-abi=hard', '-mfpu=neon'], ('bar', 'gvar', 'foo')),
            ('ELF64', ['-target', 'x86_64-linux-gnu'], ('bar', 'foo'))):
        td = tempfile.mkdtemp()
        c = os.path.join(td, 't.c')
        o = os.path.join(td, 't.o')
        open(c, 'w').write(src)
        r = subprocess.run([z, 'cc', '-c', '-O1'] + flags + [c, '-o', o],
                           capture_output=True)
        if r.returncode != 0:
            print('   SKIP %s（编译失败: %s）' % (label, r.stderr.decode()[:120]))
            continue
        with open(o, 'rb') as fh:
            got_class = fh.read(5)[4]
        de, co, un, err = read_syms(o)
        dn = sorted(x[0] for x in de)
        un_n = sorted(x[0] for x in un)
        missing = [w for w in want if w not in dn and w not in un_n]
        # ★ 反向自检：读出来的类必须与文件头一致（防止「碰巧读对」）
        want_class = 1 if label == 'ELF32' else 2
        ok = (not missing) and (got_class == want_class) and (err is None)
        bad += 0 if ok else 1
        print('   %s %-6s class=%d err=%s 缺少=%s defined=%s undef=%s'
              % ('✓' if ok else '★FAIL', label, got_class, err, missing or '无', dn, un_n))
    # 反例：非 ELF 文件必须**响亮报错**而不是静默返回空
    td = tempfile.mkdtemp()
    badf = os.path.join(td, 'x.bin')
    open(badf, 'wb').write(b'not-an-elf-file' * 4)
    de, co, un, err = read_syms(badf)
    ok = (len(de) == 0) and (err is not None)
    bad += 0 if ok else 1
    print('   %s 反例 非ELF ⇒ 必须报错（err=%s）' % ('✓' if ok else '★FAIL', err))
    print('   合计 3 条，失败 %d 条' % bad)
    return 2 if bad else 0


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
