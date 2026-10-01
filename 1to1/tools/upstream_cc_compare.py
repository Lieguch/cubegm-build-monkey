#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upstream_cc_compare.py —— 「上游库 · 纯编译器」判决的**比对器**。

## 为什么要有这个实验（补第 99 轮 fid 矩阵的盲区）
第 99 轮的 `fidelity_matrix.sh` 把 **213 个「我们重建的 TU」** 混在一起比，样本里同时含
  (a) **编译器**差异（zig cc/clang vs 工厂的 ARM GCC 6.2），
  (b) **我们重建的 C 与工厂原始 C** 的差异（Ghidra 重建固有误差）。
⇒ 结论「换编译器没用」**无法排除**「重建误差把编译器信号淹掉了」。

**上游单头库（stb_truetype）是干净样本**：
  · 我们**没有重建**它 —— `src/upstream/stb/stb_truetype.h` 是原版上游源码；
  · 版本已单独排除（v1.20/v1.21/v1.22/v1.23 四版编译产物**几乎完全相同**，
    实测 `stbtt_FindGlyphIndex`=632 / `stbtt_Rasterize`=6084 四版一致，
    而工厂是 848 / 1244 ⇒ **不是版本差异**）。
⇒ 唯一的变量就是**编译器**。

## 预登记判据（先写下，再跑；判负也是交付物）
  M1 = 体积**完全相同**（st_size 逐字节相等）的共有函数个数      —— 越大越像
  M2 = 体积比中位（候选/工厂）                                  —— 越接近 1.000 越像
  M3 = **工厂独有**函数个数（我方把它们内联/合并掉了）           —— 越小越像
  M4 = **候选独有**函数个数                                     —— 越小越像
判决：某候选 M1 显著高于 clang，**且** M2 更接近 1.000，**且** M3/M4 不劣于 clang
      ⇒ **上游库应改用该编译器**（可隔离杠杆成立；再谈切主构建上游段 CC）
      全部候选与 clang 相当 ⇒ 上游库差异**另有原因**，不是编译器。

## 用法
  python tools/upstream_cc_compare.py --prefix stbtt --factory golden/factory.rkgame.bin \
      clang=build/_upcc/clang.o gcc=build/_upcc/gcc.o [bootlin63=...]
"""
from __future__ import print_function

import argparse
import statistics
import sys

try:
    from elftools.elf.elffile import ELFFile
except ImportError:
    sys.stderr.write('需要 pyelftools（CI 里已装）\n')
    raise


def funcs(path, prefix):
    """→ {符号名: st_size}；只取 STT_FUNC 且名字带前缀、size>0 的。

    ★ `path` 可以是**目录**：把目录下所有 `.o` 的符号表合并（组件由多个 .c 构成时用）。
      未定义符号的 st_size 为 0 ⇒ 已被 `if s['st_size']` 滤掉，不会混入。
    """
    import glob
    import os

    paths = sorted(glob.glob(os.path.join(path, '*.o'))) if os.path.isdir(path) else [path]
    out = {}
    for p in paths:
        try:
            with open(p, 'rb') as fh:
                e = ELFFile(fh)
                st = e.get_section_by_name('.symtab')
                if st is None:
                    continue
                for s in st.iter_symbols():
                    if s['st_info']['type'] != 'STT_FUNC':
                        continue
                    if prefix and not s.name.startswith(prefix):
                        continue
                    if s['st_size']:
                        out[s.name] = s['st_size']
        except Exception:                                            # noqa: BLE001
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--prefix', default='stbtt')
    ap.add_argument('--factory', default='golden/factory.rkgame.bin')
    ap.add_argument('cands', nargs='+', help='name=path.o')
    a = ap.parse_args()

    F = funcs(a.factory, a.prefix)
    if not F:
        sys.stderr.write('★ 工厂里没有前缀 %r 的函数 —— 仪器不成立，拒绝给结论\n' % a.prefix)
        return 12
    print('=' * 100)
    print('上游库 · 纯编译器判决（样本 = %s*，源码未被重建 ⇒ 唯一变量是编译器）' % a.prefix)
    print('=' * 100)
    print('  工厂 %s ：%d 个函数，合计 %d B' % (a.factory, len(F), sum(F.values())))
    print()

    rows = []
    for spec in a.cands:
        if '=' not in spec:
            continue
        name, path = spec.split('=', 1)
        try:
            O = funcs(path, a.prefix)
        except Exception as exc:                                    # noqa: BLE001
            print('  %-12s ★读不到（%s）' % (name, type(exc).__name__))
            continue
        common = set(F) & set(O)
        exact = sum(1 for n in common if F[n] == O[n])
        ratios = [O[n] / float(F[n]) for n in common if F[n]]
        med = statistics.median(ratios) if ratios else float('nan')
        only_o = sorted(set(O) - set(F))
        missing = sorted(set(F) - set(O))
        rows.append((name, len(O), len(common), exact, med, only_o, missing))

    print('  %-12s %-8s %-6s %-9s %-12s %-9s %s'
          % ('候选', '函数数', '共有', 'M1 体积全同', 'M2 体积比中位', 'M3 工厂独有', 'M4 候选独有'))
    print('  ' + '-' * 92)
    for name, no, nc, ex, med, only_o, missing in rows:
        print('  %-12s %-8d %-6d %-9d %-12.3f %-9d %d'
              % (name, no, nc, ex, med, len(missing), len(only_o)))

    if rows:
        base = None
        for r in rows:
            if r[0].startswith('clang'):
                base = r
        print()
        print('  --- 判读（预登记判据）---')
        for r in rows:
            name, no, nc, ex, med, only_o, missing = r
            if base is None:
                print('    %-12s M1=%d  M2=%.3f  M3=%d  （缺 clang 基线，无法相对判读）'
                      % (name, ex, med, len(missing)))
                continue
            better = (ex > base[3]) and (abs(med - 1.0) < abs(base[4] - 1.0)) \
                and len(missing) <= len(base[6])
            print('    %-12s M1=%d(基线 %d)  M2=%.3f(基线 %.3f)  M3=%d(基线 %d)  ⇒ %s'
                  % (name, ex, base[3], med, base[4], len(missing), len(base[6]),
                     '★ 优于 clang' if better else '不优于 clang'))
        print()
        print('    ★ 结论口径：若某真 GCC 候选「★ 优于 clang」⇒ 上游库应改用该编译器（杠杆成立）；')
        print('      若全部「不优于 clang」⇒ 上游库差异**另有原因**，不是编译器（本条与第 99 轮不矛盾：')
        print('      第 99 轮的样本混入了"重建误差"，本实验把那个混淆项去掉了）。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
