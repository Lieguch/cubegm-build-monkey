#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 batch 的 DIVERGE 按**信号强度**分类：NOISE / REAL / UNDECIDABLE。

## 为什么需要它（第 152 轮补记 2 的结论）
现存 14 个 DIVERGE 里，有 8 个的差异**只在非法输入组**出现：
两侧都在几条~几十条指令内撞未映射内存而死，判决由「死在哪个地址 / 跑了几步」决定
（`strtrim` 是完整取证过的样板 —— 合法输入组两侧 ret 逐项相同）。
把这些和真有语义差异的混在同一个 `DIVERGE` 数字里 ⇒ **头条数字误导**，
还会诱导人去「给噪声改源码」。

## 分类规则（只用 batch 已经产生的字段，不引入新判据）
对某个 DIVERGE 函数，逐组（zero/strs/core/misc）看两侧：
  · 「**跑完组**」= 两侧都 `stop=return`；
  · 「**早死组**」= 两侧都 `stop=UC_ERR_*_UNMAPPED`；
  · 「**单侧死**」= 只有一侧 `return`（一侧早死）⇒ 视野不对齐。
然后：
  · 有跑完组，且**跑完组全部一致**，且**所有发散组都是早死组**        ⇒ **NOISE**
  · 有跑完组，且任一跑完组两侧 ret / calls_ext / final 不同          ⇒ **REAL**
  · 无跑完组（全是早死或单侧死）                                     ⇒ **UNDECIDABLE**
（完全没有发散的函数不进来，不分类。）

## 判别力自证（必须跑且必须过）
`--self-test` 直接调 `diff_exec.classify_signal` 的同一份规则（正反对照见那里）。
**分类规则只有一处实现**（纪律 69）⇒ 本文件只做「取数 + 调用」，不重述规则。

用法:
  python3 tools/diverge_classify.py [--ours <elf>] [--factory <elf>] [--steps N]
  python3 tools/diverge_classify.py --self-test
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE))

import diff_exec                                                        # noqa: E402

FACTORY_D = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
OURS_D = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

GROUPS = ('zero', 'strs', 'core', 'misc')
RE_F = re.compile(r'^\s*\[(%s)\s*\]\s+F:ret=(0x[0-9a-f]+)\s+ins=(\d+)\s+stop=(\S+)' % '|'.join(GROUPS))
RE_O = re.compile(r'^\s+O:ret=(0x[0-9a-f]+)\s+ins=(\d+)\s+stop=(\S+)')
RE_CALLS = re.compile(r'calls_ext F=\[(.*?)\]\s+O=\[(.*?)\]')
RE_FINAL = re.compile(r'data-final\s+不同\s+(\d+)\s+项\s+\[(.*?)\]')

# ★ 规则的唯一真源在 diff_exec.classify_signal；这里只是把「文本解析结果」
#   转成它要的 xr 字段形态。
_KindMap = {'DIVERGE': 'DIVERGE', 'ok': 'ok', 'info': 'info', 'trunc': 'trunc',
            'refdead': 'refdead', 'SKIP': 'SKIP'}


def parse_fn_detail(text):
    """把 `diff_exec.py --fn X` 的输出解析成 xr 字典列表（喂给 classify_signal）。"""
    out = []
    cur = None
    for ln in text.splitlines():
        m = RE_F.match(ln)
        if m:
            cur = {'fn': '', 'grp': m.group(1), 'kind': 'ok',
                   'sf': m.group(4), 'so': None}
            out.append(cur)
            continue
        if cur is not None:
            m = RE_O.match(ln)
            if m:
                cur['so'] = m.group(3)
                continue
            m = RE_CALLS.search(ln)
            if m:
                if m.group(1) != m.group(2):
                    cur['kind'] = 'DIVERGE'
                continue
            m = RE_FINAL.search(ln)
            if m and int(m.group(1)):
                cur['kind'] = 'DIVERGE'
                continue
            if RE_HD_DIFF.match(ln):
                cur['kind'] = 'DIVERGE'
    return out


RE_HD_DIFF = re.compile(r'^\s*\[?\s*(zero|strs|core|misc)\s*\]?\s+.*差异|DIVERGE')


def classify(groups):
    """→ ('REAL'|'NOISE'|'UNDECIDABLE', 说明)。委托给 diff_exec.classify_signal。"""
    return diff_exec.classify_signal(groups)


def batch_diverging(factory, ours, steps):
    """跑一次 batch，取出 DIVERGE 函数名集合。"""
    cmd = [sys.executable, os.path.join(HERE, 'diff_exec.py'), '--batch', '--steps', str(steps)]
    if factory:
        cmd += ['--factory', factory]
    if ours:
        cmd += ['--ours', ours]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=3600)
    names, on = set(), False
    for ln in r.stdout.splitlines():
        if 'DIVERGE 明细' in ln:
            on = True
            continue
        if on:
            if ln.startswith('  ---') or '访存内联等价' in ln:
                break
            m = re.match(r'^  ([A-Za-z_][A-Za-z0-9_$]*)\s+\[', ln)
            if m:
                names.add(m.group(1))
    return sorted(names), r.stdout


def fn_detail(name, factory, ours, steps):
    cmd = [sys.executable, os.path.join(HERE, 'diff_exec.py'), '--fn', name, '--steps', str(steps)]
    if factory:
        cmd += ['--factory', factory]
    if ours:
        cmd += ['--ours', ours]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=900)
    return parse_fn_detail(r.stdout)


def main():
    args = sys.argv[1:]
    if '--self-test' in args:
        return run_self_test()
    factory = OURS = None
    steps = 4000
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--factory':
            factory = args[i + 1]; i += 2
        elif a == '--ours':
            OURS = args[i + 1]; i += 2
        elif a == '--steps':
            steps = int(args[i + 1]); i += 2
        else:
            print('?? 未知参数 %r' % a); return 2
    factory = factory or FACTORY_D
    OURS = OURS or OURS_D
    for p in (factory, OURS):
        if not os.path.exists(p):
            print('!! 缺 %s' % p); return 3

    print('=' * 88)
    print('DIVERGE 信号强度分类（REAL=有真实观测差异 / ABI=ret-only且两侧ret都在沙箱区(非语义) / NOISE=只在早死组发散 / UNDECIDABLE=无跑完组）')
    print('=' * 88)
    names, _ = batch_diverging(factory, OURS, 20000)
    print('  batch DIVERGE 函数 = %d 个\n' % len(names))
    buckets = {'NOISE': [], 'REAL': [], 'ABI': [], 'UNDECIDABLE': []}
    for n in names:
        g = fn_detail(n, factory, OURS, steps)
        if not g:
            buckets['UNDECIDABLE'].append((n, '解析不到分组明细'))
            continue
        tag, why = classify(g)
        buckets[tag].append((n, why))
    for tag in ('REAL', 'ABI', 'NOISE', 'UNDECIDABLE'):
        lst = buckets[tag]
        print('--- %s（%d）---' % (tag, len(lst)))
        for n, why in sorted(lst):
            print('   %-28s %s' % (n[:28], why))
        print()
    print('汇总：REAL=%d  ABI=%d  NOISE=%d  UNDECIDABLE=%d  /  合计 %d'
          % (len(buckets['REAL']), len(buckets['ABI']), len(buckets['NOISE']),
             len(buckets['UNDECIDABLE']), len(names)))
    return 0


def run_self_test():
    """判别力自证 = 直接跑 `diff_exec` 里那份规则的同一组正反对照（规则只有一处）。"""
    print('== diverge_classify 自证（委托 diff_exec.classify_signal，规则同源）==')
    print('    （正反对照的完整清单见 `diff_exec.py --self-test` 的 classify_signal 段）')
    import importlib.util as _ilu
    _sp = _ilu.spec_from_file_location('de', os.path.join(HERE, 'diff_exec.py'))
    _de = _ilu.module_from_spec(_sp)
    _sp.loader.exec_module(_de)

    def g(grp, kind='ok', sf='return', so='return'):
        return {'fn': 't', 'grp': grp, 'kind': kind, 'sf': sf, 'so': so}

    c = lambda cond, name, got=None: print('  %s  %s%s' % ('✓' if cond else '★★ FAIL', name,
                                                           '' if cond else '  got=%r' % (got,)))
    ok = [g('zero', 'ok', 'UC_ERR_READ_UNMAPPED', 'UC_ERR_READ_UNMAPPED'),
          g('strs', 'DIVERGE', 'UC_ERR_READ_UNMAPPED', 'UC_ERR_READ_UNMAPPED'),
          g('core', 'ok'), g('misc', 'info')]
    c(_de.classify_signal(ok)[0] == 'NOISE', '正例  跑完组一致 + 早死组发散 ⇒ NOISE',
      _de.classify_signal(ok)[0])
    _b = list(ok); _b[2] = g('core', 'DIVERGE')
    c(_de.classify_signal(_b)[0] == 'REAL', '反例  跑完组发散 ⇒ 必须 REAL', _de.classify_signal(_b)[0])
    _b2 = list(ok); _b2[1] = g('strs', 'DIVERGE', 'return', 'UC_ERR_READ_UNMAPPED')
    c(_de.classify_signal(_b2)[0] == 'REAL', '反例  单侧死 ⇒ REAL', _de.classify_signal(_b2)[0])
    _nod = [g(_k, 'DIVERGE', 'UC_ERR_READ_UNMAPPED', 'UC_ERR_READ_UNMAPPED') for _k in GROUPS]
    c(_de.classify_signal(_nod)[0] == 'UNDECIDABLE', '反例  无跑完组 ⇒ UNDECIDABLE',
      _de.classify_signal(_nod)[0])
    c(_de.classify_signal([])[0] == 'UNDECIDABLE', '反例  空明细 ⇒ UNDECIDABLE',
      _de.classify_signal([])[0])
    c('没发散' in _de.classify_signal([g('zero'), g('strs')])[1],
      '边界  无发散 ⇒ NOISE 且标注「不该进来」')
    return 0


if __name__ == '__main__':
    sys.exit(main())
