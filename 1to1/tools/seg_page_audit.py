#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seg_page_audit —— 「段页共享」门禁：一个页被多个权限不同的 PT_LOAD 覆盖。

为什么需要它（2026-10-02 实测到的第五类"exec 层"杀手）
------------------------------------------------------
设备/加载器**按 PT_LOAD 逐段 mmap**，mmap 的粒度是**页**。若两个 PT_LOAD 的
[vaddr, vaddr+memsz) 落在**同一个页**上，后映射的段的权限会**覆盖**先前的映射 ⇒
若先前那段是**可执行**的（.text），该页就**丢掉 X** ⇒ 跳到该页里的任何函数
= 取指故障（`SIGSEGV si_code=2 SEGV_ACCERR`，且 **si_addr == PC**）。

实测（云上 qemu-user + 设备真 sysroot + guest shim + 三桩，2026-10-02）：
  · 我方 `build/rkgame.rebuilt.elf`：
      PT_LOAD va=0x004e1000 fl=5 (RX) filesz=0x5ffc8  ⇒ 末端 0x540fc8 **未页对齐**
      PT_LOAD va=0x00540fc8 fl=4 (R)  filesz=0x1840   ⇒ 紧随其后
      ⇒ 页 0x540000 被两者共享，**后映射的 R 段覆盖 ⇒ 该页无 X**
      ⇒ 页内 **24 个 FUNC 符号**（`TUnzip::Open/Get/Find/Unzip/Close`、`unztell`、
        `FormatZipMessageU` … 全 XUnzip/Zip 一族）**全部不可达**
      ⇒ 实测崩点：`pc = si_addr = 0x005401d8` = `_ZN6TUnzip4OpenEPvjj` 入口，
         `[pc-4] = 0xe12fff1e`（`bx lr`）⇒ **是取指故障，不是写只读页**
      ⇒ 直接后果：`ui_cn.zip` 从未被打开（工厂侧 `openat("//ui_cn.zip")` ×3，我方 0 次）
  · 原厂 `golden/factory.rkgame.bin`：**共享页 0 个**（只有 2 个 PT_LOAD，
    0x00008000 与 0x003ae000——**两个都是页对齐的**，末端也页对齐）

根因是**链接脚本没保证段边界页对齐**（`.text` 末端 0x540fc8 直接接 `.ARM.exidx`）。
修法见 `linker/factory.ld`（由 `tools/gen_data_module.py` 生成）里 `.ARM.exidx` 的 `ALIGN`。

判据（这是一个**不变量**，不是补丁）
------------------------------------
对每一个被 >1 个 PT_LOAD 覆盖的页：
    最终权限 = **PHDR 表中最后一个**覆盖该页的段的权限（加载器按表序映射，后者覆盖前者）
    需要权限 = 覆盖该页的**所有**段权限的**并集**
    若 `需要权限 & ~最终权限` 非 0 ⇒ **FAIL**
（`PT_GNU_RELRO` 的运行期 mprotect 是**设计行为**，另由 `relro_audit.py` 判，本工具不重复管。）

自证（`--selftest <命中样本> <合规样本>`，双向）
-----------------------------------------------
正例必须过、反例必须被抓 —— 「先验仪器，再看它的结论」。
"""
import argparse
import os
import struct
import sys

PT_LOAD = 1
PAGE = 0x1000
PERM = ((4, 'R'), (2, 'W'), (1, 'X'))


def perm_str(f):
    return ''.join(n for b, n in PERM if f & b) or '-'


def parse(path):
    d = open(path, 'rb').read()
    if d[:4] != b'\x7fELF':
        raise ValueError('not ELF: %s' % path)
    if d[4] != 1 or d[5] != 1:
        raise ValueError('only ELF32 little-endian supported')
    e_phoff = struct.unpack_from('<I', d, 28)[0]
    e_phentsize = struct.unpack_from('<H', d, 42)[0]
    e_phnum = struct.unpack_from('<H', d, 44)[0]
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    e_shentsize = struct.unpack_from('<H', d, 46)[0]
    e_shnum = struct.unpack_from('<H', d, 48)[0]
    e_shstrndx = struct.unpack_from('<H', d, 50)[0]

    phs, relro = [], None
    for i in range(e_phnum):
        o = e_phoff + i * e_phentsize
        t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', d, o)
        if t == PT_LOAD:
            phs.append(dict(idx=len(phs), type=t, off=off, va=va, fsz=fsz,
                            msz=msz, fl=fl, al=al))
        elif t == 0x6474e552:                      # PT_GNU_RELRO
            relro = (va, msz)

    # 节表（用于把违规页归属到节）
    secs = []
    if 0 < e_shoff and e_shnum and e_shstrndx < e_shnum:
        shstr = struct.unpack_from('<I', d, e_shoff + e_shstrndx * e_shentsize + 16)[0]
        for i in range(e_shnum):
            o = e_shoff + i * e_shentsize
            nm, typ, fl, addr, off, size, link, info, al, ent = struct.unpack_from(
                '<10I', d, o)
            e = d.find(b'\x00', shstr + nm)
            name = d[shstr + nm:e].decode('latin-1')
            if size and (fl & 0x2):                # SHF_ALLOC
                secs.append(dict(name=name, addr=addr, size=size, flags=fl))

    # 函数符号（STT_FUNC 且 size>0，跳过 ARM 映射符号 `$a`/`$t`）
    funcs = []
    for i in range(e_shnum):
        o = e_shoff + i * e_shentsize
        nm, typ, fl, addr, off, size, link, info, al, ent = struct.unpack_from(
            '<10I', d, o)
        e = d.find(b'\x00', shstr + nm)
        name = d[shstr + nm:e].decode('latin-1')
        if name != '.symtab' or not size:
            continue
        stro = struct.unpack_from('<I', d, e_shoff + link * e_shentsize + 16)[0]
        for k in range(size // 16):
            q = off + k * 16
            nme, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, q)
            e2 = d.find(b'\x00', stro + nme)
            sn = d[stro + nme:e2].decode('latin-1')
            if val and sz and (inf & 0xf) == 2 and not sn.startswith('$'):
                funcs.append((val, sz, sn))
    return dict(data=d, phs=phs, secs=secs, funcs=funcs, relro=relro, size=len(d))


def audit(info):
    """返回 (violations, shared, page_owner)。纯函数，便于自证。"""
    pages = {}
    for p in info['phs']:
        s = p['va'] & ~(PAGE - 1)
        e = (p['va'] + p['msz'] + PAGE - 1) & ~(PAGE - 1)
        for pg in range(s, e, PAGE):
            pages.setdefault(pg, []).append(p)
    shared = {pg: v for pg, v in pages.items() if len(v) > 1}
    viol = []
    for pg, lst in sorted(pages.items()):
        if len(lst) < 2:
            continue
        final = lst[-1]['fl']                   # 表序最后一个 = 最后一次映射 = 生效权限
        need = 0
        for p in lst:
            need |= p['fl']
        miss = (need & ~final) & 0x7
        if miss:
            viol.append(dict(pg=pg, segs=lst, final=final, need=need, miss=miss))
    return viol, shared, pages


def report(path, verbose=True):
    info = parse(path)
    viol, shared, pages = audit(info)
    print('=' * 96)
    print('段页共享门禁：%s' % path)
    print('=' * 96)
    print('  目标 %d B ／ PT_LOAD %d 个 ／ 被 >1 段覆盖的页 %d 个'
          % (info['size'], len(info['phs']), len(shared)))
    if verbose:
        for p in info['phs']:
            s = p['va'] & ~(PAGE - 1)
            e = (p['va'] + p['msz'] + PAGE - 1) & ~(PAGE - 1)
            print('    [%d] va=0x%08x filesz=0x%-6x memsz=0x%-6x fl=%d(%-3s) 页[0x%x,0x%x)%s'
                  % (p['idx'], p['va'], p['fsz'], p['msz'], p['fl'], perm_str(p['fl']),
                     s, e, '' if p['va'] % PAGE == 0 else '  ← 起始未页对齐'))
    total_fn = 0
    for v in viol:
        pg = v['pg']
        segs = ' + '.join('va=0x%08x(fl=%d %s)' % (p['va'], p['fl'], perm_str(p['fl']))
                          for p in v['segs'])
        miss = ''.join(n for b, n in PERM if v['miss'] & b)
        print('  ★ 页 0x%05x 共享：%s' % (pg, segs))
        print('      最终权限 = %s（表序最后一段生效）  需要 = %s  ⇒ **缺 %s**'
              % (perm_str(v['final']), perm_str(v['need']), miss))
        own = [s['name'] for s in info['secs'] if s['addr'] < pg + PAGE and s['addr'] + s['size'] > pg]
        print('      该页上的节：%s' % (', '.join(own) or '(无)'))
        fs = sorted([f for f in info['funcs'] if pg <= f[0] < pg + PAGE])
        total_fn += len(fs)
        print('      ★ 该页内 FUNC 符号 %d 个（跳到其中任何一个都会崩）' % len(fs))
        for va, sz, sn in fs[:8]:
            print('         0x%08x size=%-5d %s' % (va, sz, sn))
        if len(fs) > 8:
            print('         … 其余 %d 个' % (len(fs) - 8))
    print('-' * 96)
    if viol:
        print('  结论：FAIL —— %d 个页的权限被覆盖后**不满足覆盖它的全部段**；'
              '受影响 FUNC 符号 %d 个' % (len(viol), total_fn))
        print('        实测后果：跳到该类页内函数 ⇒ 取指故障'
              '（SIGSEGV si_code=2 SEGV_ACCERR，si_addr == PC）。')
        print('        修法：让相邻的、权限不同的 PT_LOAD **不共享页**（链接脚本里给段边界加 ALIGN(0x1000)）。')
    else:
        print('  结论：PASS —— 任意被共享的页，其最终权限 ⊆ 覆盖它的所有段的权限并集')
    return 0 if not viol else 2, viol, info


def selftest(bad_path, good_path):
    print('=' * 96)
    print('自证：先验仪器，再看它的结论（双向）')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-56s got=%-4s %s' % (tag, got, '✓' if good else '★ FAIL'))

    rc_bad, viol_bad, _ = report(bad_path, verbose=False)
    chk('反例（已知会崩的产物）→ 必须被抓', rc_bad, 2)
    rc_good, viol_good, _ = report(good_path, verbose=False)
    chk('正例（原厂工厂二进制）→ 必须通过', rc_good, 0)

    # 合成样本：只改一处 —— 可执行段末端**多占一页**，与紧随的可写段共享该页
    # （这正是本项目实测到的形态：`.text` 尾页被后续 R 段覆盖）
    info = parse(good_path)
    ph = [dict(p) for p in info['phs']]
    hit = False
    for p in ph:
        if (p['fl'] & 1) and not hit:         # 第一个可执行段
            p['fsz'] += PAGE
            p['msz'] += PAGE
            hit = True
    v_s, _, _ = audit(dict(info, phs=ph))
    chk('合成反例（可执行段末端多占一页）→ 必须被抓', len(v_s), 1)

    # 合成正例：还原 ⇒ 必须消失
    v_g, _, _ = audit(info)
    chk('合成正例（还原）→ 必须通过', len(v_g), 0)

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('elf', nargs='?')
    ap.add_argument('--selftest', nargs=2, metavar=('KNOWN_BAD', 'KNOWN_GOOD'))
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        if not selftest(a.selftest[0], a.selftest[1]):
            return 2
        print()
    if not a.elf:
        return 0
    rc, _, _ = report(a.elf, verbose=not a.quiet)
    return rc


if __name__ == '__main__':
    sys.exit(main())
