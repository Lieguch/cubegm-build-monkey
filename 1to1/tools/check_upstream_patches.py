#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_upstream_patches.py —— 上游本地补丁在场检查（源级，构建前即可判）

登记表：ledger/upstream_patches.tsv
判据：每条 `文件 <TAB> 锚点 <TAB> 类型 <TAB> 理由 <TAB> 门禁`，锚点必须在文件里
**恰好命中 1 次**（0 次 = 补丁丢了；≥2 次 = 锚点不唯一，检查不可信）。

为什么源级还要再做一遍（ELF 级已有 L3）：
  换上游版本时，符号可能因为**别的原因**仍然存在（例如新版本自己就不内联），
  于是 ELF 级门禁是绿的、但补丁其实丢了。源级检查把"补丁在场"与"符号在场"解耦。

自证：--self-test 用临时目录构造正例/反例（不依赖项目文件）。
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER = os.path.join(ROOT, 'ledger', 'upstream_patches.tsv')


def parse(path=LEDGER):
    rows = []
    if not os.path.exists(path):
        return rows
    for i, line in enumerate(open(path, encoding='utf-8'), 1):
        s = line.rstrip('\n')
        if not s.strip() or s.lstrip().startswith('#'):
            continue
        parts = s.split('\t')
        if len(parts) < 2:
            raise SystemExit('ledger 第 %d 行列数不足（需 TAB 分隔）' % i)
        rows.append((parts[0].strip(), parts[1], i))
    return rows


def check(rows, root=ROOT):
    """返回 (ok, 问题列表)。纯函数，可被自证直接调用。"""
    bad = []
    cache = {}
    for rel, anchor, lineno in rows:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            bad.append((lineno, rel, '文件不存在（上游被删/改名？）'))
            continue
        if p not in cache:
            cache[p] = open(p, encoding='utf-8', errors='replace').read()
        n = cache[p].count(anchor)
        if n == 0:
            bad.append((lineno, rel, '锚点缺失 ⇒ 补丁丢了（换版本后必须复打）'))
        elif n > 1:
            bad.append((lineno, rel, '锚点命中 %d 次（不唯一，检查不可信）' % n))
    return (not bad), bad


def self_test():
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'x.h')
        open(f, 'w', encoding='utf-8').write('static __attribute__((noinline)) void f(void)\n{\n}\n')
        rows = [('x.h', 'static __attribute__((noinline)) void f(', 1)]
        ok, bad = check(rows, td)
        case1 = ok and not bad
        rows_bad = [('x.h', 'static __attribute__((noinline)) void g(', 2)]
        ok2, bad2 = check(rows_bad, td)
        case2 = (not ok2) and bad2
        ok3, _ = check([('nope.h', 'x', 3)], td)
        case3 = not ok3
    print('  正例 锚点在场 ⇒ PASS                 %s' % ('OK' if case1 else '**MISMATCH**'))
    print('  反例 锚点缺失 ⇒ FAIL                 %s' % ('OK' if case2 else '**MISMATCH**'))
    print('  反例 文件不存在 ⇒ FAIL               %s' % ('OK' if case3 else '**MISMATCH**'))
    print('  self-test: 3 条，失败 %d 条' % (0 if (case1 and case2 and case3) else 1))
    return case1 and case2 and case3


def main():
    if '--self-test' in sys.argv:
        sys.exit(0 if self_test() else 1)
    rows = parse()
    ok, bad = check(rows)
    print('== 上游本地补丁在场检查（%d 条登记）==' % len(rows))
    if ok:
        print('  结论：PASS —— 全部锚点唯一命中')
    else:
        for lineno, rel, why in bad:
            print('  [FAIL] %s:%d  %s' % (rel, lineno, why))
        print('  结论：FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
