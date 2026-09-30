#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inline_move_audit.py —— 用 `inline_move` 判据对 `--dump-rows` 明细做**离线**审计。

## 为什么要有它（纪律 61：新判据先给预期降级数）
"给尺子加一条对称的访存判据"是**口径变更**。不许先改结果再看数字 ——
必须先在**现有数据**上算出"应当降级几个、DIVERGE 应变成几"，把它写死，再改尺子。

本工具的**判据逻辑全部来自 `tools/inline_move.py`**（唯一真源，纪律 69），
自己只负责：解明细 → 逐函数判决 → 打印账目与预登记数。

用法:
    python tools/inline_move_audit.py report/_r93_rows.json            # 逐函数账目
    python tools/inline_move_audit.py report/_r93_rows.json --expect    # 只打印预登记数
退出码：0 = 正常；11 = 缺输入
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import inline_move as IM  # noqa: E402


def audit(rows):
    """→ (per_fn, counts)。per_fn[fn] = (verdict, uf, uo, nkf, nko)"""
    side_f, side_o = IM.build_index(rows)
    byfn = {}
    for r in rows:
        if r.get('kind') == 'DIVERGE':
            byfn.setdefault(r['fn'], []).append(r)
    per = {}
    for fn, rs in byfn.items():
        v, (uf, uo) = IM.function_verdict(fn, rs, side_f, side_o)
        kf, ko = set(), set()
        for r in rs:
            a, b = IM.one_sided(r)
            kf |= a
            ko |= b
        per[fn] = (v, uf, uo, len(kf), len(ko))
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rows')
    ap.add_argument('--expect', action='store_true')
    ap.add_argument('--verify-meta', action='store_true',
                    help='★ 交叉核对：明细 meta 里尺子自己记下的「访存内联等价」名单，'
                         '必须与**本工具**用判据算出的 FULL 集合**逐元素相同**。')
    ap.add_argument('--artifact', default='build/rkgame.rebuilt.elf')
    a = ap.parse_args()
    if not os.path.exists(a.rows):
        sys.stderr.write('★ 缺明细 %s —— fail-closed\n' % a.rows)
        return 11
    d = json.load(open(a.rows, encoding='utf-8'))
    meta, rows = d['meta'], d['rows']

    # ★ 明细必须自带"它读的是哪一版产物"，且与当前产物一致 —— 否则预登记数无意义
    if os.path.exists(a.artifact):
        import hashlib
        cur = hashlib.sha256(open(a.artifact, 'rb').read()).hexdigest()[:16]
        if cur != meta['ours']['sha256'][:16]:
            sys.stderr.write('★ 明细 sha %s ≠ 当前产物 sha %s ⇒ 结果不可用\n'
                             % (meta['ours']['sha256'][:16], cur))
            return 11

    per = audit(rows)

    # ---- ★ 交叉核对（防"同一分母两个值"）----
    if a.verify_meta:
        full_set = {f for f, v in per.items() if v[0] == 'FULL'}
        if meta.get('inline_move_off'):
            want = set()
        else:
            if 'inline_move_equiv' not in meta:
                sys.stderr.write('★ 明细 meta 缺 `inline_move_equiv` ⇒ 说明它不是由'
                                 '**接入了该判据**的尺子产出的 ⇒ 无法核对 ⇒ fail-closed\n')
                return 3
            want = set(meta['inline_move_equiv'])
        if full_set != want:
            sys.stderr.write('★★ 口径不一致（同一分母两个值）：尺子记 %s，离线判据算 %s\n'
                             % (sorted(want), sorted(full_set)))
            sys.stderr.write('   仅尺子有：%s\n   仅离线有：%s\n'
                             % (sorted(want - full_set), sorted(full_set - want)))
            return 3
        print('✔ 交叉核对通过：尺子与离线判据的「访存内联等价」集合逐元素相同（%d 个）'
              % len(full_set))

    total = len(per)
    full = sorted([f for f, v in per.items() if v[0] == 'FULL'])
    part = sorted([f for f, v in per.items() if v[0] == 'PARTIAL'])
    other = sorted([f for f, v in per.items() if v[0] == 'OTHER'])
    empty = sorted([f for f, v in per.items() if v[0] == 'EMPTY'])

    if not a.expect:
        print('=' * 92)
        print('访存内联等价审计（判据真源 = tools/inline_move.py）')
        print('=' * 92)
        print('  被测产物 %s sha256 %s' % (meta['ours']['path'], meta['ours']['sha256'][:16]))
        print('  发散函数 %d  ⇒  FULL %d ／ PARTIAL %d ／ OTHER(含别的维度) %d ／ EMPTY %d'
              % (total, len(full), len(part), len(other), len(empty)))
        for tag, lst in (('✔ FULL（真·搬家，可对称降级）', full),
                         ('★ PARTIAL（有未解释的键 ⇒ 不得洗白）', part),
                         ('- OTHER（差异里含 calls/ret/stop/final ⇒ 不属本判据）', other),
                         ('- EMPTY（没有任何一侧访存键）', empty)):
            print()
            print('  %s：%d 个' % (tag, len(lst)))
            for f in lst:
                v, uf, uo, nkf, nko = per[f]
                if v == 'PARTIAL':
                    print('      %-30s 仅F=%2d(未解释 %2d)  仅O=%2d(未解释 %2d)'
                          % (f, nkf, len(uf), nko, len(uo)))
                elif v == 'FULL':
                    print('      %-30s 仅F=%2d  仅O=%2d' % (f, nkf, nko))
                else:
                    print('      %s' % f)
        # 前几个 PARTIAL 的未解释键（取证用）
        print()
        print('  --- PARTIAL 未解释键样本（各前 3 条）---')
        for f in part[:6]:
            v, uf, uo, _, _ = per[f]
            for (dim, k) in uf[:3]:
                print('      %-26s ★未解释 F-only %s/%s' % (f, dim, k))
            for (dim, k) in uo[:3]:
                print('      %-26s ★未解释 O-only %s/%s' % (f, dim, k))

    # ---- 预登记 ----
    stats = meta.get('stats') or {}
    print()
    print('=' * 92)
    print('预登记（纪律 61：改尺子前先写死）')
    print('=' * 92)
    applied = (not meta.get('inline_move_off')) and ('inline_move_equiv' in meta)
    print('  当前汇总      ：%s' % (stats or '（见报告）'))
    print('  真·搬家（FULL）：%d 个 → %s' % (len(full), ', '.join(full)))
    if applied:
        # ★ 明细已来自"接入判据"的尺子 ⇒ 降级**已经发生**，不许再报一个"应变成几"
        #   （那会让人以为还能再降一次 —— 正是"报数字不看口径"的老毛病）。
        print('  ★ 本明细来自**已接入该判据**的尺子 ⇒ 降级已生效，DIVERGE = %d 已含此效果。'
              % stats.get('DIVERGE', -1))
    else:
        print('  **DIVERGE 应  ：%d → %d**（本明细来自**未**接入判据的尺子）'
              % (stats.get('DIVERGE', -1), stats.get('DIVERGE', 0) - len(full)))
    print('  其余（PARTIAL %d + OTHER %d + EMPTY %d）**一个都不许变**。'
          % (len(part), len(other), len(empty)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
