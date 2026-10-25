#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""state_range_for.py —— 计算「状态快照安全范围」= 两侧数据段可映射区间的交集（页对齐）

## 为什么需要（R297 真实事故）
shim 的状态快照按 `CGM_STATE_RANGE=lo,hi` 一次性 `write()` 整块。
实测：默认 `0x3ae000..0x3f3000` 对工厂侧可读（其数据段 + brk 连续），
但**我方数据段止于 0x3f2000** ⇒ 最后一页未映射 ⇒ write 返回 EFAULT
⇒ 整个块**一个字节都没写出去**（`state_rebuild.bin` 只有 16 B 头，body=0），
而 CI 里表现为"快照 BAD"，容易被误读成"快照功能坏了"。

## 判据
取两侧 **PT_LOAD(RW) 且 p_vaddr 落在低地址数据区（< 0x600000）** 的区间，
求交集，再向页内取整（lo 向下、hi 向上都会引入未映射风险，故 **hi 向下取整**）。

用法：
  python tools/state_range_for.py <factory.elf> <ours.elf>     # 打印 lo,hi（十六进制）
  python tools/state_range_for.py ... --range                  # 打印 lo,hi 供 env 使用
"""
import sys

from elftools.elf.elffile import ELFFile

PAGE = 0x1000
LOW_LIMIT = 0x600000


def rw_span(path):
    """→ (lo, hi)：该 ELF 在低地址区的可写 PT_LOAD 区间（页对齐内缩）。"""
    e = ELFFile(open(path, 'rb'))
    spans = []
    for s in e.iter_segments():
        if s['p_type'] != 'PT_LOAD':
            continue
        if not (s['p_flags'] & 0x2):          # 必须可写（PF_W）
            continue
        va, sz = s['p_vaddr'], s['p_memsz']
        if va >= LOW_LIMIT:
            continue
        spans.append((va, va + sz))
    if not spans:
        raise SystemExit('找不到低地址可写段：%s' % path)
    lo = min(a for a, _b in spans)
    hi = max(b for _a, b in spans)
    lo = (lo + PAGE - 1) // PAGE * PAGE                  # 向上对齐（避免半页）
    hi = hi // PAGE * PAGE                               # **向下对齐**（避免跨界未映射页）
    return lo, hi


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    fa, oa = argv[0], argv[1]
    flo, fhi = rw_span(fa)
    olo, ohi = rw_span(oa)
    lo = max(flo, olo)
    hi = min(fhi, ohi)
    print('  工厂 [0x%08x,0x%08x) ｜ 我方 [0x%08x,0x%08x) ⇒ 交集 [0x%08x,0x%08x) = %d B'
          % (flo, fhi, olo, ohi, lo, hi, max(0, hi - lo)), file=sys.stderr)
    if hi <= lo:
        print('★★ 交集为空：两侧数据段不重叠，状态快照不可用', file=sys.stderr)
        return 3
    print('%x,%x' % (lo, hi))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
