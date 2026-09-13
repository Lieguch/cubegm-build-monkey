#!/usr/bin/env python3
"""
gen_data_module.py — P3 数据段供应：生成「工厂镜像 + 符号别名」汇编与链接脚本。

原理（为什么必须这样做）：
  1) 反编译代码里**烧死了绝对地址**（如 `DrawSelectBar((int *)0x3afc44)`），所以段必须
     落在工厂相同 VMA：.rodata/.data/.bss 的地址由链接脚本固定。
  2) Ghidra 的 `DAT_xxxxxxxx` **不是工厂符号**——工厂真符号是大对象（`m_ui` size 1508 等），
     Ghidra 给其内部每个访问点另起了名字。若把它们各自独立定义，链接后各占空间 ⇒
     破坏原厂布局。
     ⇒ 做法：**每个段只放一份工厂原始镜像**，所有符号（含 `DAT_x`）一律用
        `.set NAME, <段基址符号> + <偏移>` 定义为**别名**，不额外分配空间。

输入：
  --elf       工厂 ELF
  --layout    ledger/factory_layout.tsv
  --globals   ledger/factory_globals.tsv（940 个权威数据对象）
  --missing   report/_link_missing.txt（MISSING 名单）
输出（默认）：
  src/data/factory_image.S           段镜像 + 全部符号别名
  src/data/factory_rodata.bin        工厂 .rodata 原始字节
  src/data/factory_data.bin          工厂 .data  原始字节
  linker/factory.ld                  复刻工厂 VMA 的链接脚本
"""
import argparse
import os
import re
import sys

# 只镜像这三段。.init_array/.fini_array 交给链接器（crtbegin 会填正确构造子），
# 否则会把工厂的构造函数地址搬过来 → 指向错的代码；但符号仍要 PROVIDE 到段首。
# SKIP_HEAD[section] = 跳过头部字节数（交由 CRT 提供，避免与 crt1.o 重复定义）
SKIP_HEAD = {'.rodata': 4}
SEC_DEF = [('.rodata', 'a', 'progbits', None),
           ('.data.rel.ro.local', 'aw', 'progbits', None),
           ('.data', 'aw', 'progbits', None),
           ('.bss', 'aw', 'nobits', None)]
# 由链接器生成（不占独立空间）
LINKER_DEFINED = {'__frame_dummy_init_array_entry': '.init_array',
                  '__do_global_dtors_aux_fini_array_entry': '.fini_array'}
RE_DAT = re.compile(r'^DAT_([0-9a-fA-F]{6,8})$')


def load_layout(p):
    out = {}
    for i, line in enumerate(open(p, encoding='utf-8')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 8 or f[0] != 'SH':
            continue
        out[f[1]] = dict(addr=int(f[2], 16), size=int(f[3], 16),
                         flags=int(f[5], 16), offset=int(f[6], 16))
    return out


def load_globals(p):
    rows = []
    for i, line in enumerate(open(p, encoding='utf-8')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 7:
            continue
        rows.append(dict(name=f[0], addr=int(f[1], 16), size=int(f[2], 16),
                         section=f[3]))
    return rows


def load_missing(p):
    out = []
    for line in open(p, encoding='utf-8', errors='replace'):
        f = line.rstrip('\n').split('\t')
        if len(f) >= 2 and f[0] == 'MISSING':
            out.append(f[1])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--elf', required=True)
    ap.add_argument('--layout', required=True)
    ap.add_argument('--globals', required=True)
    ap.add_argument('--missing', required=True)
    ap.add_argument('--outdir', default=None)
    a = ap.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = a.outdir or root
    datadir = os.path.join(outdir, 'src', 'data')
    linkdir = os.path.join(outdir, 'linker')
    os.makedirs(datadir, exist_ok=True)
    os.makedirs(linkdir, exist_ok=True)

    lay = load_layout(a.layout)
    globs = load_globals(a.globals)
    missing = load_missing(a.missing)

    elf = open(a.elf, 'rb').read()

    # ---- 段范围 ----
    secs = {}
    for nm, fl, ty, _ in SEC_DEF:
        if nm not in lay:
            raise SystemExit('layout 缺段 %s' % nm)
        secs[nm] = lay[nm]

    def which_sec(addr, size=1):
        for nm, _, _, _ in SEC_DEF:
            s = secs[nm]
            if s['addr'] <= addr < s['addr'] + s['size']:
                return nm
        return None

    # ---- 提取镜像 ----
    for nm, _, ty, _ in SEC_DEF:
        s = secs[nm]
        if ty == 'nobits':
            continue
        skip = SKIP_HEAD.get(nm, 0)
        blob = elf[s['offset'] + skip:s['offset'] + s['size']]
        if len(blob) != s['size'] - skip:
            raise SystemExit('段 %s 数据不足' % nm)
        open(os.path.join(datadir, 'factory_%s.bin' % nm.strip('.').replace('.', '_')), 'wb').write(blob)
        print('  提取 %-9s %d 字节' % (nm, len(blob)))

    # ---- 收集符号（去重；同名以工厂账本为准）----
    syms = {}
    skipped_crt = []
    for g in globs:
        if g['name'] in LINKER_DEFINED:
            skipped_crt.append(g['name'])
            continue
        syms.setdefault(g['name'], (g['addr'], g['section']))
    unplaced = []
    for m in missing:
        if m in syms:
            continue
        md = RE_DAT.match(m)
        if not md:
            unplaced.append(m)
            continue
        addr = int(md.group(1), 16)
        s = which_sec(addr)
        if not s:
            unplaced.append(m)
            continue
        syms[m] = (addr, s)

    # ---- 生成汇编 ----
    lines = []
    A = lines.append
    A('/* 自动生成 —— 请勿手改；见 tools/gen_data_module.py')
    A(' * 每个段只放一份工厂原始镜像，全部符号（含 Ghidra DAT_x）以 .set 别名指向段内偏移。')
    A(' * 依据：段 VMA 必须与工厂一致（代码里烧死绝对地址）；DAT_x 不是工厂符号。 */')
    A('')
    for nm, fl, ty, _ in SEC_DEF:
        s = secs[nm]
        A('\t.section %s,"%s",%%%s' % (nm, fl, ty))
        A('\t.globl __f%s_base' % nm.replace('.', '_'))
        A('\t.type __f%s_base, %%object' % nm.replace('.', '_'))
        A('__f%s_base:' % nm.replace('.', '_'))
        s['_skip'] = SKIP_HEAD.get(nm, 0)
        bl = nm.strip('.').replace('.', '_')
        if ty == 'nobits':
            A('\t.space 0x%x' % s['size'])
        else:
            if nm in SKIP_HEAD:
                # ★ bin 文件本身已跳过 SKIP_HEAD 字节（gen 时 blob=elf[off+skip:off+size]），
                #   此处不能再 skip —— 否则 GNU as 报错、clang 静默截断尾部 4 字节
                A('\t.incbin "factory_%s.bin"' % bl)
            else:
                A('\t.incbin "factory_%s.bin"' % bl)
        A('\t.size __f%s_base, 0x%x' % (nm.replace('.', '_'), s['size'] - s.get('_skip', 0)))
        A('')
    A('/* ---- 符号别名 ---- */')
    per_sec = {nm: [] for nm, _, _, _ in SEC_DEF}
    for name, (addr, sec) in sorted(syms.items(), key=lambda kv: (kv[1][1], kv[1][0])):
        per_sec[sec].append((addr, name))
    total = 0
    for nm, _, _, _ in SEC_DEF:
        A('/* %s：%d 个符号 */' % (nm, len(per_sec[nm])))
        skip = SKIP_HEAD.get(nm, 0)
        for addr, name in per_sec[nm]:
            off = addr - secs[nm]['addr'] - skip
            if off < 0:
                continue      # 位于被跳过的 CRT 头部内（_IO_stdin_used）
            A('\t.globl %s' % name)
            A('\t.set %s, __f%s_base + 0x%x' % (name, nm.replace('.', '_'), off))
            total += 1
        A('')
    open(os.path.join(datadir, 'factory_image.S'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

    # ---- 链接脚本 ----
    L = []
    B = L.append
    B('/* 自动生成 —— 复刻工厂 rkgame 的内存映射（tools/gen_data_module.py）')
    B(' * 依据：反编译代码含烧死的绝对地址，段 VMA 必须与工厂逐位一致。 */')
    B('ENTRY(_start)')
    B('')
    B('SECTIONS')
    B('{')
    B('  . = 0x00008000;')
    order = [('.plt', 0x9608), ('.text', 0x9b10), ('.rodata', 0x2dbca0),
             ('.ARM.exidx', 0x3ad008), ('.data.rel.ro.local', 0x3ae5c4),
             ('.init_array', 0x3aeed8), ('.fini_array', 0x3aeedc),
             ('.data', 0x3af000), ('.got', 0x3b1cfc), ('.bss', 0x3b2178)]
    for nm, vma in order:
        B('  %s 0x%08x : { *(%s) *(%s.*) }' % (nm, vma, nm, nm))
    B('  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) }')
    B('}')
    B('')
    B('/* CRT 符号：指向真实段首（构造子由 crtbegin 填入，语义正确） */')
    for sym, sec in sorted(LINKER_DEFINED.items()):
        B('PROVIDE(%s = ADDR(%s));' % (sym, sec))
    open(os.path.join(linkdir, 'factory.ld'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    print('数据镜像符号总数 : %d' % total)
    print('CRT 符号(链接器定义): %s' % ', '.join(sorted(skipped_crt)))
    print('未落段的 MISSING : %d  %s' % (len(unplaced), ', '.join(unplaced[:10])))
    print('产出: src/data/factory_image.S, src/data/factory_*.bin, linker/factory.ld')
    return 0


if __name__ == '__main__':
    sys.exit(main())
