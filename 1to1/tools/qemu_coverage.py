#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
qemu_coverage.py —— P5「执行覆盖率」度量（把 CI 的 -d exec 原始轨迹变成进度数字）

为什么需要它
============
`1to1-qemu-behav` 报 `PASS` 只证明：**在观测窗口内**，重建与工厂的可观测行为一致。
窗口有多深、覆盖了多少重构代码，此前**无从得知**（exec 探针只留尾部 800 行，
而那 800 行几乎全是 ld/libc 的 TB，rkgame 自身只剩最后 1 个）。⇒ 「进度」无法量化。

做法
====
`-d exec` 原始日志每行 = **一个被执行的翻译块**，格式：
    Trace 0: 0x7f... [<cs_base>/<pc>/<flags>/<cflags>] <symbol?>
其中**第 2 个字段 = guest pc**（已用两侧已知崩点交叉验证：
`[00000480/05015c44/...] mui_setting` 与重建 crash pc 0x05015c44 一致；
`[00000480/0002b3c8/...] mui_setting` 与工厂 crash pc 0x0002b3c8 一致）。

把每个 pc 归到「所属函数」（ELF symtab 的 STT_FUNC 区间），即可得到：
  · 覆盖函数数 / 全函数数（%）
  · 覆盖 .text 字节 / .text 总字节（%）
  · 对照 ledger/functions.csv（工厂 223 个专有函数 / 122,922 B）：
    **本场景实际进入了多少个重构函数、覆盖率多少** ← 这就是「进度」的硬数字
  · 未覆盖的重量级函数清单（按字节倒序）← 直接驱动下一轮该测什么

用法
====
  python3 tools/qemu_coverage.py --exec-log exec_rebuild.log \
      --elf build/rkgame.rebuilt.elf --ledger ledger/functions.csv \
      --label rebuild --out report/qemu/coverage_rebuild.txt [--baseline tools/coverage_baseline.txt]

退出码：0 = 正常；2 = 覆盖率**低于基线**（回归）；1 = 参数/文件错误。
  ★ 覆盖率**不是**门禁的充分条件，而是「窗口有多深」的度量；真实行为判定仍以 behav_diff 为准。
"""
import argparse
import os
import re
import struct
import sys

FX = struct  # 简写


# ---------------------------------------------------------------- ELF 符号表
def read_symtab(path):
    """返回 [(addr, size, name)]，只取已定义且 size>0 的 STT_FUNC。"""
    d = open(path, 'rb').read()
    if d[:4] != b'\x7fELF':
        raise ValueError('%s 不是 ELF' % path)
    e_shoff = FX.unpack_from('<I', d, 32)[0]
    es = FX.unpack_from('<H', d, 46)[0]
    n = FX.unpack_from('<H', d, 48)[0]
    out = []
    for i in range(n):
        o = e_shoff + i * es
        sh = FX.unpack_from('<10I', d, o)
        if sh[1] != 2:            # SHT_SYMTAB
            continue
        st = FX.unpack_from('<10I', d, e_shoff + sh[6] * es)
        strd = d[st[4]:st[4] + st[5]]
        ent = sh[9] or 16
        for j in range(sh[5] // ent):
            oo = sh[4] + j * ent
            nmn, val, sz, inf, oth, shx = FX.unpack_from('<IIIBBH', d, oo)
            if nmn == 0 or shx == 0 or (inf & 0xF) != 2 or sz == 0:
                continue
            k = strd.index(b'\x00', nmn)
            out.append((val, sz, strd[nmn:k].decode('utf-8', 'replace')))
    out.sort()
    if not out:
        raise ValueError('%s 无可用符号表（被 strip？）' % path)
    return out


def text_range(path):
    """.text 的 (vaddr, size)。"""
    d = open(path, 'rb').read()
    e_shoff = FX.unpack_from('<I', d, 32)[0]
    es = FX.unpack_from('<H', d, 46)[0]
    n = FX.unpack_from('<H', d, 48)[0]
    si = FX.unpack_from('<H', d, 50)[0]
    stroff = FX.unpack_from('<I', d, e_shoff + si * es + 16)[0]
    for i in range(n):
        o = e_shoff + i * es
        sh = FX.unpack_from('<10I', d, o)
        k = d.index(b'\x00', stroff + sh[0])
        if d[stroff + sh[0]:k].decode() == '.text':
            return sh[3], sh[5]
    return 0, 0


# ---------------------------------------------------------------- 轨迹解析
def parse_pcs(log, limit_bytes=None):
    """从 -d exec 日志里取「唯一 pc 集合」+ 行数。用字符串切分而非 re（大日志快 3~5 倍）。"""
    pcs = set()
    lines = 0
    with open(log, 'r', encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            lines += 1
            i = ln.find('[')
            if i < 0:
                continue
            j = ln.find('/')
            if j < 0:
                continue
            k = ln.find('/', j + 1)
            if k < 0:
                continue
            try:
                pcs.add(int(ln[j + 1:k], 16))
            except ValueError:
                continue
    return pcs, lines


def owner(pc, starts, syms):
    """pc 落在哪个函数里（返回索引或 None）。"""
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= pc:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return None
    va, sz, _ = syms[lo - 1]
    return lo - 1 if va <= pc < va + sz else None


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exec-log', required=True)
    ap.add_argument('--elf', required=True)
    ap.add_argument('--ledger', default='')
    ap.add_argument('--label', default='')
    ap.add_argument('--out', default='')
    ap.add_argument('--baseline', default='')
    ap.add_argument('--top', type=int, default=20)
    a = ap.parse_args()

    if not os.path.exists(a.exec_log):
        print('  ✗ 轨迹日志不存在：%s' % a.exec_log)
        return 1
    syms = read_symtab(a.elf)
    starts = [s[0] for s in syms]
    ta, ts = text_range(a.elf)

    pcs, lines = parse_pcs(a.exec_log)
    hit = set()
    for pc in pcs:
        i = owner(pc, starts, syms)
        if i is not None:
            hit.add(i)

    # 只在 .text 内统计（排除 libc / ld，它们不在本 ELF 符号表里）
    in_text = [i for i in hit if ta <= syms[i][0] < ta + ts]
    cov_bytes = sum(syms[i][1] for i in in_text)
    all_text_fn = [i for i, s in enumerate(syms) if ta <= s[0] < ta + ts]
    text_bytes = sum(syms[i][1] for i in all_text_fn)

    L = []
    L.append('== P5 执行覆盖率（label=%s）==' % (a.label or '?'))
    L.append('   ELF      : %s' % a.elf)
    L.append('   轨迹日志 : %s（%d 行；唯一 pc %d 个）' % (a.exec_log, lines, len(pcs)))
    L.append('   覆盖函数 : %d / %d = %.2f%%' % (len(in_text), len(all_text_fn),
                                              100.0 * len(in_text) / max(1, len(all_text_fn))))
    L.append('   覆盖字节 : %d / %d = %.2f%%（.text）' % (cov_bytes, text_bytes,
                                                      100.0 * cov_bytes / max(1, text_bytes)))

    # ---- 专有函数维度（ledger/functions.csv = 工厂 223 个重构目标）----
    prov_cov = prov_tot = 0
    prov_cov_bytes = prov_tot_bytes = 0
    missing = []
    if a.ledger and os.path.exists(a.ledger):
        import csv
        rows = list(csv.DictReader(open(a.ledger, encoding='utf-8')))
        name2idx = {}
        for i, (va, sz, nm) in enumerate(syms):
            name2idx.setdefault(nm, i)
        for r in rows:
            sz = int(r['size'])
            prov_tot += 1
            prov_tot_bytes += sz
            i = name2idx.get(r['name'])
            if i is not None and i in hit:
                prov_cov += 1
                prov_cov_bytes += sz
            else:
                missing.append((sz, r['name'], r.get('module', '')))
        L.append('   —— 专有函数（重构量）维度 ——')
        L.append('   已执行   : %d / %d = %.2f%%；字节 %d / %d = %.2f%%'
                 % (prov_cov, prov_tot, 100.0 * prov_cov / max(1, prov_tot),
                    prov_cov_bytes, prov_tot_bytes,
                    100.0 * prov_cov_bytes / max(1, prov_tot_bytes)))
        entered = sorted(((int(r['size']), r['name'], r.get('module', '')) for r in rows
                          if name2idx.get(r['name']) in hit), reverse=True)
        L.append('   已执行函数明细（%d 个）：' % len(entered))
        for sz, nm, mod in entered:
            L.append('      %-42s %7d B  %s' % (nm[:42], sz, mod))
        L.append('   未执行·重量级 Top %d（下一轮该打这里）：' % a.top)
        for sz, nm, mod in sorted(missing, reverse=True)[:a.top]:
            L.append('      %-42s %7d B  %s' % (nm[:42], sz, mod))

    # ---- 基线对比（回归护栏）----
    rc = 0
    if a.baseline and os.path.exists(a.baseline):
        try:
            b = {}
            for ln in open(a.baseline, encoding='utf-8'):
                ln = ln.strip()
                if not ln or ln.startswith('#'):
                    continue
                k, v = ln.split('=', 1)
                b[k.strip()] = int(v.strip())
            prev = b.get(a.label or '')
            if prev is not None:
                delta = len(in_text) - prev
                L.append('   覆盖率基线：%d 个函数 → 现在 %d 个（%+d）%s'
                         % (prev, len(in_text), delta, '✓' if delta >= 0 else '  ✗ 覆盖率回退'))
                if delta < 0:
                    rc = 2
        except Exception as ex:                       # 基线只做提示，不因格式问题失败
            L.append('   （基线解析失败：%s）' % ex)

    report = '\n'.join(L)
    print(report)
    if a.out:
        os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(report + '\n')
        print('   → 已写入 %s' % a.out)
    return rc


if __name__ == '__main__':
    sys.exit(main())
