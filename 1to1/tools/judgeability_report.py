#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""judgeability_report.py —— 从 `--dump-rows` 明细产出**可判性全表**（G3）

## 目的（纪律 180 的推广）
"从未被比较"和"比较了但判不了"都会让报告看起来完整，实际覆盖有洞。
本工具把**每个函数**归到一个可判性等级，并把"缺席原因"写成可执行的下一步：

| 等级 | 含义 | 下一步 |
|---|---|---|
| PASS | 至少一组跑完且全一致 | — |
| DIVERGE | 至少一组跑完且存在差异 | 逐条定性（REAL 才追源码） |
| TRUNC | 全部组触步数上限 | 提高预算或改输入（先测斜率） |
| REFDEAD | 参照侧（工厂）在沙箱里内存未映射早死 | 补沙箱映射（不是我们的缺陷） |
| DEADEQ | 两侧同类早死且死亡现场一致 | 语义等价，但**未覆盖有效路径** ⇒ G1 快照的候选 |
| SKIP | 未执行 | 查为何跳过 |

用法：
  python tools/judgeability_report.py report/_rows.json [--tsv report/_judgeability.tsv] [--top 20]
"""
import json
import sys
from collections import Counter

RANK = {'DIVERGE': 5, 'TRUNC': 4, 'REFDEAD': 3, 'SKIP': 3, 'DEADEQ': 2, 'info': 1, 'ok': 0, 'PASS': 0}


def verdict_of(kinds):
    """组级 kind 列表 → 函数级等级（取最坏）。"""
    best = 'PASS'
    for k in kinds:
        k2 = k.upper() if k.lower() in ('diverge', 'trunc', 'refdead', 'skip', 'deadeq') else k
        if k2 == 'SKIP':
            k2 = 'SKIP'
        if RANK.get(k2, 0) > RANK.get(best, 0):
            best = k2
    return best


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    src = argv[0]
    tsv = None
    top = 20
    for i, a in enumerate(argv):
        if a == '--tsv' and i + 1 < len(argv):
            tsv = argv[i + 1]
        if a == '--top' and i + 1 < len(argv):
            top = int(argv[i + 1])
    d = json.load(open(src, encoding='utf-8'))
    rows = d.get('rows') or []
    meta = d.get('meta') or {}
    # ★ 优先用 meta.verdicts（**全量**、每函数一条，由 batch 直接给出最终等级）；
    #   rows 只覆盖"有明细的组"，按它聚合会漏掉大量 PASS 函数（曾实测只出 193/799）。
    vmap = meta.get('verdicts') or {}
    per = {}
    if vmap:
        for fn, v in vmap.items():
            per[fn] = [v]
    else:
        for r in rows:
            per.setdefault(r.get('fn'), []).append(r.get('kind'))
    table = sorted(((fn, verdict_of(ks), len(ks)) for fn, ks in per.items()),
                   key=lambda t: (-RANK.get(t[1], 0), t[0]))
    cnt = Counter(v for _f, v, _n in table)
    print('== 可判性全表（来源 %s；样本 steps=%s）==' % (src, meta.get('steps')))
    print('  函数 %d 个' % len(table))
    for k in ('PASS', 'DIVERGE', 'TRUNC', 'DEADEQ', 'REFDEAD', 'SKIP'):
        if cnt.get(k):
            print('    %-8s %d' % (k, cnt[k]))
    print()
    for k in ('DIVERGE', 'TRUNC', 'REFDEAD', 'SKIP', 'DEADEQ'):
        names = [f for f, v, _n in table if v == k]
        if not names:
            continue
        print('  --- %s（%d）---' % (k, len(names)))
        for n in names[:top]:
            print('    %s' % n)
        if len(names) > top:
            print('    … 其余 %d 个' % (len(names) - top))
        print()
    if tsv:
        with open(tsv, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# 函数\t可判性\t组数\n')
            for fn, v, n in table:
                f.write('%s\t%s\t%d\n' % (fn, v, n))
        print('  ★ 全表已写出：%s（%d 行）' % (tsv, len(table)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
