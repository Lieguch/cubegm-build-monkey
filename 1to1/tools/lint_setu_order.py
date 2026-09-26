#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lint_setu_order.py —— `set -u` 脚本里"变量在被赋值/取默认值之前就被引用"的机械门禁。

为什么需要（本项目两次同型事故，各白跑一次 CI）：
  · `ZIGBIN` 被"探针"块提前引用，而它的解析写在**后面**的编译段 ⇒
    `tools/fidelity_matrix.sh: 147: ZIGBIN: parameter not set` ⇒ exit 2；
  · `AB_ONLY` 被新插入的"预检块"提前引用，而默认值写在**后面**的腿 A 段 ⇒
    `tools/toolchain_ab.sh: 102: AB_ONLY: parameter not set` ⇒ exit 2。
⇒ 规律：**插入新代码段时，最容易把"后面才定义的变量"用到前面**。
   本门禁把这件事变成机器检查，而不是靠人记得看。

规则（保守，只报高置信项）：
  1. 只检查含 `set -u`（或 `set -eu` 等含 `u`）的 .sh；
  2. 取所有 `${VAR}` / `$VAR` 的**首次出现行号**；
  3. 取每个 VAR 的**首次获得值**的行号：
       · 形如 `VAR=…`（含 `VAR="${VAR:-…}"`）的赋值；
       · 形如 `VAR:-` 出现在 `${VAR:-…}` 中（取默认值，等价于获得值）；
       · `for VAR in …` 的循环变量；
       · `case`/`read`/`printf -v` 等罕见形态不处理（漏报可接受，误报不可接受）。
  4. 若"首次引用行 < 首次获值行" ⇒ 报 ORDER。
  5. 位置参数 `$1`/`$@`、`$?`、`$$`、`$0`、`$#` 与来源为**环境约定**的名字
     （`PATH`/`HOME` 等）一律跳过。

★ 误报比漏报更坏（会让人关掉门禁）⇒ 只报能说清的形态，其余计入"未处理"统计。

exit: 0 = 无问题 / 1 = 有问题 / 2 = 用法错误
"""
import argparse
import glob
import io
import os
import re
import sys

SKIP = {
    'PATH', 'HOME', 'PWD', 'IFS', 'TMPDIR', 'USER', 'SHELL', 'LANG', 'LC_ALL',
    'GITHUB_ENV', 'GITHUB_STEP_SUMMARY', 'GITHUB_OUTPUT', 'RUNNER_TEMP',
    'GITHUB_WORKSPACE', 'PIPESTATUS', 'RANDOM', 'SECONDS', 'OPTIND', 'LINENO',
}

RE_REF = re.compile(r'\$\{([A-Za-z_]\w*)[^}]*\}|\$([A-Za-z_]\w*)')
RE_ASSIGN = re.compile(r'^\s*(?:export\s+)?([A-Za-z_]\w*)=')
RE_FOR = re.compile(r'\bfor\s+([A-Za-z_]\w*)\s+in\b')
RE_LOCAL = re.compile(r'^\s*(?:local|declare|typeset)\s+([A-Za-z_]\w*)')
# `VAR:-` 形态即"取默认值" ⇒ 等价于获得值
RE_DEFAULT_REF = re.compile(r'\$\{([A-Za-z_]\w*):-')
# 行内赋值（如 `CC=x cmd`、`A=1 B=2 cmd`）也算获得值
RE_INLINE_ASSIGN = re.compile(r'(?:^|[\s(])([A-Za-z_]\w*)=[^=]')


def scan(text):
    """→ (problems, stats)。problems: [(var, ref_line, def_line)]"""
    lines = text.split('\n')
    if not re.search(r'^\s*set\s+-[a-z]*u', text, re.M):
        return [], {'skipped': 'no set -u'}
    first_ref, first_def = {}, {}
    for i, ln in enumerate(lines, 1):
        stripped = ln.strip()
        if stripped.startswith('#'):
            continue
        for m in RE_REF.finditer(ln):
            v = m.group(1) or m.group(2)
            if v and v not in SKIP and not v.isdigit():
                first_ref.setdefault(v, i)
        for m in RE_DEFAULT_REF.finditer(ln):
            first_def.setdefault(m.group(1), i)
        for rx in (RE_ASSIGN, RE_FOR, RE_LOCAL):
            m = rx.search(ln)
            if m:
                first_def.setdefault(m.group(1), i)
        for m in RE_INLINE_ASSIGN.finditer(ln):
            first_def.setdefault(m.group(1), i)
    probs = []
    for v, rl in sorted(first_ref.items(), key=lambda kv: kv[1]):
        dl = first_def.get(v)
        if dl is None:
            continue                      # 完全没赋值 ⇒ 可能是外部环境，保守不报
        if rl < dl:
            probs.append((v, rl, dl))
    return probs, {'vars': len(first_ref), 'defined': len(first_def)}


def selftest():
    chk = []

    def c(label, got, want):
        chk.append((label, got, want))

    good = 'set -u\nA="${A:-1}"\necho "$A"\n'
    c('正例 先默认后使用 ⇒ 无问题', scan(good)[0], [])
    bad = 'set -u\necho "$A"\nA="${A:-1}"\n'
    c('缺陷态 先使用后默认 ⇒ 报 ORDER', [p[0] for p in scan(bad)[0]], ['A'])
    q = 'set -u\necho "$A"\nA=1\n'
    c('缺陷态 先使用后赋值 ⇒ 报 ORDER', [p[0] for p in scan(q)[0]], ['A'])
    c('无 set -u ⇒ 跳过（不报）', scan('echo "$A"\nA=1\n')[0], [])
    f = 'set -u\nfor n in a b; do echo "$n"; done\n'
    c('for 循环变量不算未定义', scan(f)[0], [])
    pos = 'set -u\necho "$1" "$@" "$?"\n'
    c('位置参数/特殊参数不报', scan(pos)[0], [])
    env = 'set -u\n' + 'echo "$PATH"\n'
    c('环境变量白名单不报', scan(env)[0], [])
    inline = 'set -u\nCC=x sh y.sh\n'
    c('行内赋值 $CC 之前使用仍报（构造）', [p[0] for p in scan('set -u\necho "$CC"\nCC=x sh y.sh\n')[0]], ['CC'])
    return chk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--selftest', '--self-test', dest='self_test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        chk = selftest()
        bad = 0
        for label, got, want in chk:
            ok = got == want
            print('  %s %s' % ('✓' if ok else '✗', label))
            if not ok:
                print('      got=%r want=%r' % (got, want))
                bad += 1
        print('=== 合计 %d 条，失败 %d 条 ===' % (len(chk), bad))
        return 2 if bad else 0

    files = sorted(glob.glob(os.path.join(a.root, 'tools', '*.sh')))
    nbad = 0
    for f in files:
        try:
            txt = io.open(f, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        probs, stats = scan(txt)
        if probs:
            nbad += len(probs)
            print('  %s' % os.path.relpath(f, a.root))
            for v, rl, dl in probs:
                print('      ★ %s：第 %d 行使用，第 %d 行才获得值（set -u 下会 `parameter not set`）'
                      % (v, rl, dl))
    if nbad:
        print('★ FAIL：%d 处 `set -u` 次序问题。'
              '修法：把 `VAR="${VAR:-默认}"` 统一放到脚本**头部默认值区**。' % nbad)
        return 1
    print('  PASS：%d 个脚本，未发现"先使用后定义"' % len(files))
    return 0


if __name__ == '__main__':
    sys.exit(main())
