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
  A1 DT_INIT / DT_FINI 存在但值为 0 ⇒ FAIL（glibc call_init 会跳到地址 0；可用 --allow-no-crti 降级）
  A2 DT_INIT_ARRAY / DT_FINI_ARRAY 已声明但对应 SZ == 0 ⇒ WARN（合法但值得记一笔）
  A3 符号 `_init` / `_fini` 为 ABS 0 ⇒ FAIL（裸赋值残留特征）
  A4 e_entry 必须落在可执行的 PT_LOAD 内 ⇒ FAIL
  A5 `.rel.plt` 对应 GOT 槽静态值为 0 ⇒ WARN（可能被解析成 NULL 调用）
  A6 ABS 0 的 FUNC/OBJECT 符号（"链接期占位"残留，调用即跳地址 0）⇒ FAIL
  A7 GLIBC 版本上限 > 工厂 ⇒ FAIL（设备上 version not found）；NEEDED 结构差异 ⇒ WARN

★ 本地/CI 差异的处理（很重要）
  本机 zig 工具链**不链 crti.o**，故没有 `.init` 节、`_init` 只能落到兜底的 0。
  这不是 bug，而是工具链差异。因此 A1/A3 采用**条件判定**：
     · `.init` 节存在 且 DT_INIT 为 0 / `_init` 为 ABS 0 ⇒ **FAIL**（真 bug）
     · `.init` 节不存在 ⇒ **WARN**（本地 zig，判定以 CI(GCC) 为准）
  CI 用 GCC 必然链 crti.o ⇒ 必然走 FAIL 分支 ⇒ 这个 bug 以后会被 CI 直接拦住。

用法: python3 tools/dyn_audit.py <elf>
退出码: 0 = 通过（可含 WARN）；2 = 有 FAIL
"""
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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

    # 2026-09-14 起 zig 是**交付工具链**（本地与 CI 同一套），故 DT_INIT=0 一律 FAIL。
    # 仅在实验性构建里可用 --allow-no-crti 降级为 WARN。
    allow_no_crti = '--allow-no-crti' in sys.argv
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
            # ★★ 2026-09-14 实测回归：把 CI 切到 zig 后 cri.o 缺失 ⇒ DT_INIT=0 ⇒
            #    glibc call_init 跳地址 0 ⇒ **重建产物 0 行输出即 SIGSEGV**。
            #    不再当"工具链差异"放行 —— zig 现在就是交付工具链，必须 FAIL。
            if allow_no_crti:
                warns.append(tag)
                add('WARN', tag, '= 0（--allow-no-crti 放行；运行期会在 call_init 跳地址 0）')
            else:
                fails.append(tag)
                add('FAIL', tag, '= 0 ⇒ glibc call_init 会跳到地址 0（需由 src/compat/crt_init.S 提供真实 .init/.fini）')
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
            if allow_no_crti:
                warns.append(sname)
                add('WARN', '符号 ' + sname, '为 ABS 0（--allow-no-crti 放行）')
            else:
                fails.append(sname)
                add('FAIL', '符号 ' + sname, '为 ABS 0 ⇒ 初始化链会被调到地址 0（链接期"置 0 占位"的残留特征）')
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

    # ---- A6 ABS 0 的代码/数据符号（★★ 真实地雷：compress/uncompress 曾被绑成 ABS 0）----
    #   ABS 0 的 FUNC/OBJECT 符号 = "链接期占位"的残留。调用它们即跳地址 0；而非 PIE 下
    #   vaddr 0 往往已被首个 PT_LOAD 覆盖 ⇒ 表现为 SIGILL/SIGSEGV 而不是明确报错（极难查）。
    #   实测：`compress`/`uncompress` 被 `retro_save_state`/`retro_load_state` 调用，
    #   绑成 0 ⇒ 存档/读档必崩。修法 = 真实链接 libz.so.1（NEEDED libz.so.1，与工厂一致）。
    #   排除 STT_FILE(4)（编译单元名，正常也是 ABS 0）与 _init/_fini（由 A3 单独判定）。
    abs0 = []
    for secname in ('.symtab', '.dynsym'):
        sh2 = section(shs, secname)
        if not sh2:
            continue
        strtab = shs[sh2['link']]['off']
        ent = sh2['entsize'] or 16
        for j in range(sh2['size'] // ent):
            o = sh2['off'] + j * ent
            nm_, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, o)
            if nm_ == 0 or shx != 0xFFF1 or val != 0:
                continue
            if (inf & 0xF) not in (1, 2):        # STT_OBJECT / STT_FUNC
                continue
            e = d.index(b'\x00', strtab + nm_)
            nmx = d[strtab + nm_:e].decode('utf-8', 'replace')
            if nmx in ('_init', '_fini'):
                continue
            abs0.append(nmx)
    if abs0:
        fails.append('abs0_placeholder')
        add('FAIL', 'ABS 0 占位符号', '%d 个：%s（调用即跳地址 0）'
            % (len(abs0), ', '.join(sorted(set(abs0))[:8])))
    else:
        add('PASS', 'ABS 0 占位符号', '0 个')

    # ---- A7 设备兼容性：GLIBC 版本上限 + NEEDED 结构（基准 = 工厂二进制）----
    #   ★★ 实测铁证：CI 的 Ubuntu 22.04 GCC 链接出的产物要求 GLIBC_2.29/2.33/2.34，
    #      而工厂 rkgame 只要求 **GLIBC_2.7**（设备 SD 上原厂 ARM 运行库最高只用 2.16，
    #      且 rkgame 编译于 GCC 6.2 时代）⇒ 产物拿到真机上会
    #      `version GLIBC_2.34 not found` 直接起不来。这是 P6 真机验收的硬阻断。
    #      修法：用 zig 的 `-target arm-linux-gnueabihf.2.7` 链接（见 tools/link_full.sh）。
    fpath = None
    if '--factory' in sys.argv:
        i = sys.argv.index('--factory')
        if i + 1 < len(sys.argv):
            fpath = sys.argv[i + 1]
    if fpath is None:
        cand = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
        if os.path.exists(cand):
            fpath = cand
    if fpath and os.path.exists(fpath):
        fd, _, fshs, _ = parse(fpath)

        def dyninfo(dd, shss):
            need, gl = [], set()
            dynsh, strsh = section(shss, '.dynamic'), section(shss, '.dynstr')
            if dynsh and strsh:
                for k in range(dynsh['size'] // 8):
                    tag, val = struct.unpack_from('<iI', dd, dynsh['off'] + k * 8)
                    if tag == 0:
                        break
                    if tag == 1:
                        e = dd.index(b'\x00', strsh['off'] + val)
                        need.append(dd[strsh['off'] + val:e].decode('utf-8', 'replace'))
                blob = dd[strsh['off']:strsh['off'] + strsh['size']]
                gl = {m.decode() for m in re.findall(rb'GLIBC_2\.\d+', blob)}
            return need, gl

        need_f, gl_f = dyninfo(fd, fshs)
        need_o, gl_o = dyninfo(d, shs)
        vkey = lambda s: tuple(int(x) for x in s.split('_')[1].split('.'))
        maxf = max(gl_f, key=vkey) if gl_f else None
        maxo = max(gl_o, key=vkey) if gl_o else None
        if maxf and maxo and vkey(maxo) > vkey(maxf):
            fails.append('glibc_floor')
            add('FAIL', 'GLIBC 版本上限',
                '本产物 %s > 工厂 %s ⇒ 设备上会 "version %s not found" 直接起不来'
                % (maxo, maxf, maxo))
        else:
            add('PASS', 'GLIBC 版本上限', '本产物 %s ≤ 工厂 %s（可用）' % (maxo, maxf))

        KNOWN_MISS = {
            'libstdc++.so.6': 'operator new/delete 用自备 C shim（malloc 语义等价）',
            'libgcc_s.so.1': '纯 C 构建无异常/栈展开需求',
        }
        miss = [x for x in need_f if x not in need_o]
        extra = [x for x in need_o if x not in need_f]
        unexplained = [x for x in miss if x not in KNOWN_MISS]
        if unexplained or extra:
            warns.append('needed_diff')
            add('WARN', 'NEEDED 结构', '缺 %s；多 %s' % (miss, extra))
        else:
            add('PASS', 'NEEDED 结构',
                '仅已知可接受差异（%s）' % (', '.join(sorted(miss)) or '无'))
    else:
        add('INFO', 'GLIBC/NEEDED 对比', '跳过（未找到工厂二进制；可用 --factory=路径 指定）')

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
