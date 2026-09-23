# -*- coding: utf-8 -*-
"""elfdiff.py —— 符号级 ELF 差分：定位「改前 → 改后」到底动了哪个函数。

为什么需要它（本项目的教训）
---------------------------------------------------------------
一次 MMIO 修复之后，直接 diff 某个函数（如 `sfc_init`）会得到"完全一样"，
于是很容易得出"修复没生效"的错误结论。**真因是：被改的是它前面的另一个函数，
改动让下游整体平移，而 `sfc_init` 自身的字节确实没变。**

正确刻度是**整体符号级差分**：
    ① 对齐两版符号表 → 统计地址位移的分布（位移=0 / +N 各自多少个函数）
    ② 位移边界处那个"长度变了"的函数 = 唯一被改动的函数
    ③ 再对该函数做逐字节 diff，给出改动区间

实测（2026-09-23，MMIO 宽度修复）：
    位移分布: +0 = 1349 个, +28 = 301 个, +32 = 1077 个
    边界函数: `sfc_request` 676 → 704 B (+28)   ← 唯一改动
    `sfc_init` 逐字节相同，仅被平移 +0x1C

用法
    python tools/elfdiff.py <改前.elf> <改后.elf> [--bytes N]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elfsym import Elf32            # noqa: E402


def symmap(path):
    e = Elf32(path)
    d = {}
    for va, sz, nm, t in e.syms:
        if not nm.startswith('$'):          # 跳过 ARM 映射符号（$a/$d/$t）
            d.setdefault(nm, []).append((va, sz))
    return e, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('old')
    ap.add_argument('new')
    ap.add_argument('--bytes', type=int, default=48,
                    help='每个"尺寸变化函数"最多打印多少字节（默认 48）')
    a = ap.parse_args()

    ea, sa = symmap(a.old)
    eb, sb = symmap(a.new)
    print('  符号数：old=%d  new=%d' % (len(sa), len(sb)))
    common = sorted(set(sa) & set(sb))

    shifts = {}
    for nm in common:
        shifts.setdefault(sb[nm][0][0] - sa[nm][0][0], []).append(nm)
    print('  地址位移分布（位移 -> 函数个数）：')
    for d, lst in sorted(shifts.items(), key=lambda kv: -len(kv[1])):
        print('    %+8d (0x%+x) : %4d 个' % (d, d, len(lst)))

    unchanged = sorted((sa[n][0][0], n) for n in common if sb[n][0][0] == sa[n][0][0])
    changed = sorted((sa[n][0][0], n) for n in common if sb[n][0][0] != sa[n][0][0])
    print()
    if unchanged:
        print('  地址不变的最大函数： 0x%08x  %s' % (unchanged[-1][0], unchanged[-1][1]))
    if changed:
        nm = changed[0][1]
        print('  地址偏移的最小函数： 0x%08x  %s  (位移 %+d)'
              % (changed[0][0], nm, sb[nm][0][0] - sa[nm][0][0]))

    print()
    print('  === 长度变化的函数（真正的改动候选）===')
    n_show = 0
    for nm in common:
        za = sa[nm][0][1]
        zb = sb[nm][0][1]
        if za == zb:
            continue
        n_show += 1
        va = sa[nm][0][0]
        print('   * %-30s old size=%-6d new size=%-6d delta=%+d' % (nm, za, zb, zb - za))
        fa = ea.addr2file(va)
        fb = eb.addr2file(va)
        if fa is None or fb is None:
            print('       (无法定位文件偏移，跳过字节 diff)')
            continue
        ba = ea.b[fa:fa + min(za, zb)]
        bb = eb.b[fb:fb + min(za, zb)]
        diff = [i for i in range(min(len(ba), len(bb))) if ba[i] != bb[i]]
        print('       共同前缀内差异字节数 = %d' % len(diff))
        if diff:
            lo = max(0, diff[0] - 4)
            hi = min(min(len(ba), len(bb)), diff[-1] + 5)
            lo = max(lo, hi - a.bytes)
            print('       差异区间 [+0x%x, +0x%x)（相对函数首）:' % (lo, hi))
            print('         old @+0x%x: %s' % (lo, ' '.join('%02x' % x for x in ba[lo:hi])))
            print('         new @+0x%x: %s' % (lo, ' '.join('%02x' % x for x in bb[lo:hi])))
    if not n_show:
        print('   (无长度变化 —— 两版可能只有数据/对齐差异，或改动未进产物)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
