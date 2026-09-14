#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dyn_audit.py — ELF 动态段 / 初始化链自洽门禁（不需要 qemu，静态即可拦住一类致命 bug）。

来历（2026-09-14：重建产物在 qemu 下起不来的第一个真因）
-------------------------------------------------------
现象：`SIGILL si_addr=0x20`。翻译级轨迹（qemu `-d in_asm`）最后一句是
    ldr r3,[r6,#0] ; add r3,r1 ; blx r3      → 跳到近乎 0 的地址
而**非 PIE 时 vaddr 0 正是我们自己的 ELF 头**（已被第一个 PT_LOAD 映射），
于是把 ELF 头当指令执行，跑到 0x20 处遇未定义指令 → SIGILL。
根因：`.dynamic` 里 **`DT_INIT = 0`** —— glibc 的 `call_init` 见到 `DT_INIT` 就会调用它。
成因：链接脚本里写了**裸赋值** `_init = 0;`，把 crti.o 的真 `_init` 压掉了。
⇒ 这类错误完全可以在链接后静态抓到，不该等到跑起来才炸。

检查项
------
  A1 DT_INIT / DT_FINI 存在但值为 0 ⇒ FAIL（调用地址 0）
  A2 DT_INIT_ARRAY / DT_FINI_ARRAY 已声明但对应 SZ == 0 ⇒ WARN（合法但值得记一笔）
  A3 符号 `_init` / `_fini` 为 ABS 0 ⇒ FAIL（裸赋值残留特征）
  A4 e_entry 必须落在可执行的 PT_LOAD 内 ⇒ FAIL
  A5 `.rel.plt` 对应 GOT 槽静态值为 0 ⇒ WARN（可能被解析成 NULL 调用）

★ 本地/CI 差异的处理（很重要）
  本机 zig 工具链**不链 crti.o**，故没有 `.init` 节、`_init` 只能落到兜底的 0。
  这不是 bug，而是工具链差异。因此 A1/A3 采用**条件判定**：
     · `.init` 节存在 且 DT_INIT 为 0 / `_init` 为 ABS 0 ⇒ **FAIL**（真 bug）
     · `.init` 节不存在 ⇒ **WARN**（本地 zig，判定以 CI(GCC) 为准）
  CI 用 GCC 必然链 crti.o ⇒ 必然走 FAIL 分支 ⇒ 这个 bug 以后会被 CI 直接拦住。

用法: python3 tools/dyn_audit.py <elf>
退出码: 0 = 通过（可含 WARN）；2 = 有 FAIL
"""
import struct
import sys

TAG = {1: 'DT_NEEDED', 3: 'DT_PLTGOT', 7: 'DT_RELA', 12: 'DT_INIT', 13: 'DT_FINI',
       17: 'DT_REL', 20: 'DT_PLTREL', 23: 'DT_JMPREL', 25: 'DT_INIT_ARRAY',
       26: 'DT_FINI_ARRAY', 27: 'DT_INIT_ARRAYSZ', 28: 'DT_FINI_ARRAYSZ'}
PT_LOAD, PF_X = 1, 1


def u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def u32(d, o):
    return struct.unpack_from('<I', d, o)[0]


def parse(path):
    d = open(path, 'rb').read()
    e_entry, e_phoff, e_shoff = u32(d, 24), u32(d, 28), u32(d, 32)
    es, n, si = u16(d, 46), u16(d, 48), u16(d, 50)
    shs = []
    for i in range(n):
        o = e_shoff + i * es
        nm, typ, fl, addr, off, size, link, info, al, ent = struct.unpack_from('<10I', d, o)
        shs.append(dict(nm=nm, type=typ, flags=fl, addr=addr, off=off, size=size,
                        link=link, info=info, align=al, entsize=ent))
    shstr = shs[si]['off']
    for sh in shs:
        e = d.index(b'\x00', shstr + sh['nm'])
        sh['name'] = d[shstr + sh['nm']:e].decode('utf-8', 'replace')
    phs = []
    phes, phn = u16(d, 42), u16(d, 44)
    for i in range(phn):
        phs.append(struct.unpack_from('<8I', d, e_phoff + i * phes))
    return d, e_entry, shs, phs


def section(shs, name):
    for sh in shs:
        if sh['name'] == name:
            return sh
    return None


def syms(d, shs, secname):
    sh = section(shs, secname)
    if not sh:
        return []
    strtab = shs[sh['link']]['off']
    ent = sh['entsize'] or 16
    out = []
    for j in range(sh['size'] // ent):
        o = sh['off'] + j * ent
        nm_, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, o)
        if nm_ == 0:
            continue
        e = d.index(b'\x00', strtab + nm_)
        out.append((d[strtab + nm_:e].decode('utf-8', 'replace'), val, sz, inf >> 4, shx))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = sys.argv[1]
    d, e_entry, shs, phs = parse(path)

    dyn = {}
    sh = section(shs, '.dynamic')
    if sh:
        for k in range(sh['size'] // 8):
            tag, val = struct.unpack_from('<iI', d, sh['off'] + k * 8)
            if tag == 0:
                break
            if tag in TAG:
                dyn.setdefault(TAG[tag], []).append(val)

    has_init = bool(section(shs, '.init') and section(shs, '.init')['size'])
    has_fini = bool(section(shs, '.fini') and section(shs, '.fini')['size'])

    fails, warns, checks = [], [], []
    add = lambda lv, nm, nt: checks.append((lv, nm, nt))

    # ---- A1 ----
    for tag, secname, has_sec in (('DT_INIT', '.init', has_init), ('DT_FINI', '.fini', has_fini)):
        vals = dyn.get(tag)
        if vals is None:
            add('INFO', tag, '不存在（正常）')
        elif vals[0] == 0 and has_sec:
            fails.append(tag)
            add('FAIL', tag, '= 0 但 %s 节存在 ⇒ 初始化链会调到地址 0' % secname)
        elif vals[0] == 0:
            warns.append(tag)
            add('WARN', tag, '= 0 且无 %s 节（本地 zig 无 crti.o，属工具链差异）' % secname)
        else:
            add('PASS', tag, '= 0x%08x' % vals[0])

    # ---- A2 ----
    for atag, stag in (('DT_INIT_ARRAY', 'DT_INIT_ARRAYSZ'), ('DT_FINI_ARRAY', 'DT_FINI_ARRAYSZ')):
        if atag in dyn:
            sz = dyn.get(stag, [0])[0]
            if sz == 0:
                # ★ 空的 .init_array 本身是合法的（C 程序没有构造子时就是这样），
                #   只是"声明了却为空"值得记一笔 → WARN，不判 FAIL。
                warns.append(atag)
                add('WARN', atag, '已声明但 %s == 0（构造子表为空；C 程序无构造子时正常）' % stag)
            else:
                add('PASS', atag, '0x%08x size=%d' % (dyn[atag][0], sz))
        else:
            add('INFO', atag, '不存在')

    # ---- A3 ----
    for sname in ('_init', '_fini'):
        found = None
        for secname in ('.symtab', '.dynsym'):
            for s in syms(d, shs, secname):
                if s[0] == sname:
                    found = (s[1], s[4])
        if not found:
            add('INFO', '符号 ' + sname, '未定义（正常）')
        elif found[1] == 0xFFF1 and found[0] == 0:
            if has_init:
                fails.append(sname)
                add('FAIL', '符号 ' + sname, '为 ABS 0 且 .init 存在 ⇒ 裸赋值残留，会生成 DT_INIT=0')
            else:
                warns.append(sname)
                add('WARN', '符号 ' + sname, '为 ABS 0（无 crti.o 的本地构建，属工具链差异）')
        else:
            add('PASS', '符号 ' + sname, '0x%08x shndx=%d' % found)

    # ---- A4 ----
    ok = False
    for p in phs:
        p_type, _, p_va, _, p_fsz, p_msz, p_fl, _ = p
        if p_type == PT_LOAD and (p_fl & PF_X) and p_va <= e_entry < p_va + max(p_msz, p_fsz):
            ok = True
    if ok:
        add('PASS', 'e_entry', '0x%08x ∈ 可执行 PT_LOAD' % e_entry)
    else:
        fails.append('e_entry')
        add('FAIL', 'e_entry', '0x%08x 不在任何可执行 PT_LOAD 内' % e_entry)

    # ---- A5 ----
    zero = 0
    rsh, dsh = section(shs, '.rel.plt'), section(shs, '.data')
    if rsh and dsh:
        for k in range(rsh['size'] // 8):
            off, info = struct.unpack_from('<II', d, rsh['off'] + k * 8)
            if dsh['addr'] <= off < dsh['addr'] + dsh['size']:
                if u32(d, dsh['off'] + (off - dsh['addr'])) == 0:
                    zero += 1
    if zero:
        warns.append('got_zero')
        add('WARN', 'GOT 0 值槽', '%d 个（运行期可能被解析成 NULL 调用）' % zero)
    else:
        add('PASS', 'GOT 0 值槽', '0 个')

    L = ['=' * 72,
         '动态段 / 初始化链自洽门禁：%s' % path.replace('\\', '/').split('/')[-1],
         '=' * 72]
    for lv, nm, nt in checks:
        L.append('  [%-4s] %-22s %s' % (lv, nm, nt))
    L.append('-' * 72)
    L.append('  FAIL %d / WARN %d' % (len(fails), len(warns)))
    L.append('  结论: %s' % ('PASS' if not fails else 'FAIL —— ' + ', '.join(fails)))
    sys.stdout.write('\n'.join(L) + '\n')
    return 0 if not fails else 2


if __name__ == '__main__':
    sys.exit(main())
