#!/usr/bin/env python3
"""
funcdiff.py — 函数级差分门禁：原厂金标准 vs 重建产物。

分级判定（语义等价标准，允许寄存器分配/布局差异）：
  T1 语义等价  归一化后「助记符 + 操作数（符号化目标）」序列完全一致   <- 最强证据
  T2 结构等价  仅「助记符」序列一致（寄存器分配不同）                  <- 中证据
  T3 长度等价  指令条数一致                                            <- 弱证据，需人工复核
  FAIL         以上皆不满足                                            <- 必须定位

用法:
  funcdiff.py golden.json candidate.json                 # 汇总报告
  funcdiff.py golden.json candidate.json --detail mui_menu
  funcdiff.py golden.json candidate.json --json report/diff.json
"""
import json, sys, difflib


TIERS = ['T1', 'T2', 'T3', 'FAIL']


def load(p):
    return json.load(open(p, encoding='utf-8'))['functions']


def tier(g, c):
    if g['t1'] == c['t1']:
        return 'T1', None
    if g['t2'] == c['t2']:
        return 'T2', None
    if g['n'] == c['n']:
        return 'T3', None
    return 'FAIL', None


def hunk(g, c, ctx=3):
    """生成 T1 差异的可读片段。"""
    out = []
    sm = difflib.SequenceMatcher(a=g['t1'], b=c['t1'], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        out.append('  @@ -%d,%d +%d,%d  %s' % (i1, i2 - i1, j1, j2 - j1, tag.upper()))
        for k in range(max(0, i1 - ctx), min(len(g['t1']), i2 + ctx)):
            mark = '  -' if i1 <= k < i2 else '   '
            out.append('%s %s' % (mark, g['t1'][k]))
        for k in range(max(0, j1 - ctx), min(len(c['t1']), j2 + ctx)):
            mark = '  +' if j1 <= k < j2 else '   '
            out.append('%s %s' % (mark, c['t1'][k]))
    return '\n'.join(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    golden, cand = load(sys.argv[1]), load(sys.argv[2])
    detail = None
    outjson = None
    a = sys.argv[3:]
    for i, v in enumerate(a):
        if v == '--detail' and i + 1 < len(a):
            detail = a[i + 1]
        if v == '--json' and i + 1 < len(a):
            outjson = a[i + 1]

    res = {}
    for name, g in golden.items():
        c = cand.get(name)
        if c is None:
            res[name] = ('MISSING', None)
        else:
            res[name] = tier(g, c)

    counts = {t: 0 for t in TIERS}
    counts['MISSING'] = 0
    for t, _ in res.values():
        counts[t] += 1

    total = len(golden)
    gi = sum(g['n'] for g in golden.values())
    ci = sum(c['n'] for c in cand.values() if c)
    print('=' * 68)
    print('函数级差分报告  (语义等价标准)')
    print('=' * 68)
    print('金标准函数 %d / 指令 %d   候选函数 %d / 指令 %d' % (total, gi, len(cand), ci))
    print('-' * 68)
    for t in TIERS + ['MISSING']:
        pct = 100.0 * counts[t] / total if total else 0
        print('  %-8s %5d  %6.2f%%' % (t, counts[t], pct))
    pass_n = counts['T1'] + counts['T2']
    print('-' * 68)
    print('  门禁通过 (T1+T2) = %d / %d = %.2f%%' % (pass_n, total, 100.0 * pass_n / total if total else 0))
    print('  T1 严格等价      = %d / %d = %.2f%%' % (counts['T1'], total, 100.0 * counts['T1'] / total if total else 0))

    if counts['FAIL']:
        print('\nFAIL 函数（按代码量降序，需优先定位）:')
        bad = [(n, golden[n]['n']) for n, (t, _) in res.items() if t == 'FAIL']
        for n, sz in sorted(bad, key=lambda x: -x[1])[:25]:
            print('  %-34s n=%d' % (n, sz))
    if counts['MISSING']:
        print('\nMISSING 函数（候选缺失）:')
        for n, (t, _) in res.items():
            if t == 'MISSING':
                print('  %-34s n=%d' % (n, golden[n]['n']))

    if detail:
        g = golden.get(detail)
        c = cand.get(detail)
        if not g:
            print('\n[detail] 金标准无此函数:', detail)
        elif not c:
            print('\n[detail] 候选缺失:', detail)
        else:
            t, _ = res[detail]
            print('\n[detail] %s  判定=%s  金标准n=%d 候选n=%d' % (detail, t, g['n'], c['n']))
            if t != 'T1':
                print(hunk(g, c))

    if outjson:
        json.dump({'summary': counts,
                   'gate_pass_T1T2': pass_n,
                   'total': total,
                   'status': {n: res[n][0] for n in res}},
                  open(outjson, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        print('\n报告已写入', outjson)
    return 0


if __name__ == '__main__':
    sys.exit(main())
