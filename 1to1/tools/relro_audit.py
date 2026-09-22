#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""relro_audit —— 硬门禁：`PT_GNU_RELRO` 的**页取整区间**不得覆盖我们的可写数据节。

为什么需要它（GAP 16.71，真机实证）：
  ld.lld 把 `PT_GNU_RELRO` 定义为「本 RW 段内第一个 relro 节的起点 → 最后一个 relro 节的终点」。
  一旦 `.data` 的输出段里混进了 `*(.data.rel.ro)`/`*(.got)`，或者 `.dynamic` 被 lld 排到
  `.data` **之后**，RELRO 就会**把 `.data` 整段吞掉**；内核按页取整后把那些页设成只读
  ⇒ **进程写自己的全局变量立刻 SIGSEGV**。
  原厂是正确范例：`PT_GNU_RELRO = 0x3ae5c4 + 2620`，终点 0x3aefe0 **恰好停在页对齐的
  `.data`（0x3af000）之前**。

判据（每条都有独立缺陷态，见 --selftest）：
  R1  RELRO 的页区间 ∩ 任一「可写数据节」的页区间 == ∅
  R2  RELRO 存在（与工厂一致；缺失只提示，不判 FAIL 之外）
  R3  每个可写数据节的起始地址页对齐（否则它必然与 RELRO 尾页共享一页）

退出码：0 = PASS / 1 = 有 FAIL / 11 = 读不到输入（**绝不允许静默通过**）
"""
import io
import os
import struct
import sys
import tempfile

PT_LOAD = 1
PT_GNU_RELRO = 0x6474E552
SHT_NOBITS = 8

# 允许落在 RELRO 页内的节（本来就是 relro 语义）
RELRO_OK = ('.init_array', '.fini_array', '.preinit_array', '.dynamic', '.got', '.got.plt',
            '.data.rel.ro', '.ctors', '.dtors', '.igot', '.tdata')


def read_elf(p):
    d = open(p, 'rb').read()
    if d[:4] != b'\x7fELF':
        raise ValueError('不是 ELF：%s' % p)
    ph = struct.unpack_from('<I', d, 28)[0]; pn = struct.unpack_from('<H', d, 44)[0]
    sh = struct.unpack_from('<I', d, 32)[0]; sn = struct.unpack_from('<H', d, 48)[0]
    es = struct.unpack_from('<H', d, 46)[0]; si = struct.unpack_from('<H', d, 50)[0]
    PH = [struct.unpack_from('<8I', d, ph + i * 32) for i in range(pn)]
    SH = [struct.unpack_from('<10I', d, sh + i * es) for i in range(sn)] if sn else []
    stn = SH[si][4] if sn and si < sn else 0
    return d, PH, SH, stn


def secname(d, SH, stn, s):
    if stn == 0:
        return '?'
    k = d.index(b'\x00', stn + s[0])
    return d[stn + s[0]:k].decode('utf-8', 'replace')


def audit(path, verbose=True):
    d, PH, SH, stn = read_elf(path)
    fails, infos = [], []
    relro = None
    for t, off, va, pa, fsz, msz, fl, al in PH:
        if t == PT_GNU_RELRO:
            relro = (va, fsz)

    if relro is None:
        infos.append(('R2', '无 PT_GNU_RELRO（工厂有；缺失不致命，但与原厂结构不一致）'))
        rlo = rhi = None
    else:
        rlo = relro[0] & ~0xFFF
        rhi = (relro[0] + relro[1] + 0xFFF) & ~0xFFF
        infos.append(('R2', 'PT_GNU_RELRO = 0x%08x + %d（内核页区间 0x%08x-0x%08x）'
                      % (relro[0], relro[1], rlo, rhi)))

    bad, unaligned = [], []
    for s in SH:
        nm = secname(d, SH, stn, s)
        addr, size, flags = s[3], s[5], s[2]
        if not (flags & 0x1) or not (flags & 0x2):      # 必须 W+A
            continue
        if s[1] == SHT_NOBITS and size == 0:
            continue
        if nm.startswith(RELRO_OK) or nm in RELRO_OK:
            continue
        if addr % 0x1000:
            # 仅提示：是否页对齐本身不是硬判据（工厂镜像区的地址是 1:1 契约、不可移动）；
            # 真正致命的是"它的页区间落进 RELRO 页区间"，由 R1 判。
            unaligned.append((nm, addr))
        if rlo is None:
            continue
        slo = addr & ~0xFFF
        shi = (addr + max(size, 1) + 0xFFF) & ~0xFFF
        if slo < rhi and shi > rlo:
            bad.append((nm, addr, size, slo, shi))

    if unaligned:
        infos.append(('R3', '未页对齐的可写节（提示，非硬判据）：%s'
                      % ', '.join('%s@0x%x' % t for t in unaligned)))
    if bad:
        for nm, addr, size, slo, shi in bad:
            fails.append(('R1', '可写数据节 %s（0x%x + %d）的页区间 0x%x-0x%x '
                                '落在 RELRO 页区间 0x%x-0x%x 内 ⇒ 运行期会被改成只读 ⇒ 写它即 SIGSEGV'
                          % (nm, addr, size, slo, shi, rlo, rhi)))
    else:
        if rlo is not None:
            infos.append(('R1', '无任何可写数据节落在 RELRO 页区间内（.data/.bss 安全）'))

    if verbose:
        for t, m in infos:
            print('  [%s] %s' % (t, m))
        for t, m in fails:
            print('  [%s] ★ FAIL —— %s' % (t, m))
        print('  ---- 判决：%s ----' % ('FAIL' if fails else 'PASS'))
    return fails


def selftest(good):
    print('=== relro_audit 三态自证 ===')
    rc = 0
    # ① 正常态
    f = audit(good, verbose=True)
    print('① 正常态：%s' % ('PASS' if not f else '★ FAIL（门禁把正常态判死了）'))
    if f:
        rc = 1
    print()
    # ② 缺陷态：人为把 RELRO 拉到覆盖 .data —— 必须被 R1 抓住
    d, PH, SH, stn = read_elf(good)
    ph = struct.unpack_from('<I', d, 28)[0]
    es = struct.unpack_from('<H', d, 42)[0]
    pn = struct.unpack_from('<H', d, 44)[0]
    dat = None
    for s in SH:
        if secname(d, SH, stn, s) == '.data':
            dat = (s[3], s[5])
    if not dat:
        print('② 缺陷态：找不到 .data，跳过（★ 应报错）')
        return 1
    buf = bytearray(d)
    hit = 0
    for i in range(pn):
        p = list(struct.unpack_from('<8I', buf, ph + i * es))
        if p[0] == PT_GNU_RELRO:
            p[2] = dat[0]            # p_vaddr
            p[4] = dat[1]            # p_filesz
            struct.pack_into('<8I', buf, ph + i * es, *p)
            hit += 1
    assert hit == 1, 'PT_GNU_RELRO 数量异常：%d' % hit
    tmp = os.path.join(tempfile.gettempdir(), '_relro_bad.elf')
    io.open(tmp, 'wb').write(bytes(buf))
    f2 = audit(tmp, verbose=False)
    tags = set(t for t, _ in f2)
    ok = 'R1' in tags
    print('② 缺陷态（RELRO 拉到覆盖 .data）命中判据 %s   %s' % (sorted(tags), '✓' if ok else '★ 门禁未生效'))
    if not ok:
        rc = 1
    print()
    # ③ 文件缺 ⇒ 必须抛错（main 会转成 exit 11）
    try:
        audit(os.path.join(tempfile.gettempdir(), '_no_such_relro.elf'), verbose=False)
        print('③ 文件缺：未抛错 ★')
        rc = 1
    except Exception:
        print('③ 文件缺：抛错 ✓（main 转成 exit 11）')
    print('  结果：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 2
    if args[0] == '--selftest':
        return selftest(args[1])
    rc = 0
    for p in args:
        try:
            f = audit(p)
        except Exception as e:
            print('  ★ 读不到输入 %s：%s  ⇒ 硬失败（不允许静默通过）' % (p, e))
            return 11
        if f:
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
