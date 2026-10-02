#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ssh_literal_guard —— 「远端脚本字面量」静态门禁。

为什么需要它（2026-10-02，第 114 轮，同类事故再犯）
--------------------------------------------------
`tools/cnb_ladder.sh` 把一整段远端脚本写成**本地双引号字面量**传给 `ssh`。于是：

  · 字面量里的 **反引号** 会被**本地** shell 先做命令替换。
    实测：注释里写了 反引号包起来的 `场景 C4` ⇒
    `tools/cnb_ladder.sh: line 110: 场景: command not found`，**整轮静默死掉**；
  · 字面量里的 **未转义 `$(`** 同理，本地先执行；
  · 字面量里的 **未转义 `$VAR`** 本地先展开 —— 有时"碰巧能用"（`"$REBUILD"` 拿到的是本地值），
    可读性与可移植性都差，至少必须**可见**。

而"检查它"的那句临时 grep **自己也错过一次**：定位"字面量结束行"时用了
`next(l for l in lines if 'REMOTE-DONE' in l)`，结果先匹配到**注释里的** REMOTE-DONE
⇒ 区间为空 ⇒ 报"反引号 0 行"的**假绿**。所以本工具刻意做成：

  · 用**成对锚点**定位字面量（开 = 以 `"set -u` 开头的那行；闭 = 含
    `_stdout.bin" 2> "$OUTDIR/_stderr.txt` 的那行），锚点找不到就**报错退出**，绝不静默通过；
  · 逐字符扫描并**打印判据覆盖的行数/字符数**（"0 命中"必须能被复核）；
  · `--selftest` 用合成样本自证：反引号必抓、`$(` 必抓、干净样本必过、锚点缺失必报 11。

用法
    python tools/ssh_literal_guard.py <script.sh>
    python tools/ssh_literal_guard.py --selftest
退出: 0=通过；2=有 FAIL；11=锚点找不到（仪器不可用）
"""
import argparse
import re
import sys

BEGIN_ANCHOR = 'set -u'
END_ANCHOR = '_stdout.bin" 2> "$OUTDIR/_stderr.txt'


def locate(lines):
    """返回 (start, end)，1-based 闭区间；找不到返回 (None, None)。"""
    b = None
    for i, l in enumerate(lines, 1):
        if l.lstrip().startswith('"' + BEGIN_ANCHOR):
            b = i
            break
    e = None
    if b is not None:
        for i in range(b, len(lines) + 1):
            if END_ANCHOR in lines[i - 1]:
                e = i
                break
    return b, e


def scan(lines, b, e):
    """返回 (fails, infos, stats)。只统计**未转义**的出现。"""
    fails, infos = [], []
    n_back = n_cmdsub = n_var = 0
    for i in range(b, e + 1):
        s = lines[i - 1]
        j = 0
        while j < len(s):
            c = s[j]
            if c == '\\' and j + 1 < len(s):
                j += 2
                continue
            if c == '`':
                n_back += 1
                fails.append('line %d  unescaped backtick (local command substitution!): %s'
                             % (i, s.strip()[:110]))
                j += 1
                continue
            if c == '$' and j + 1 < len(s) and s[j + 1] == '(':
                n_cmdsub += 1
                fails.append('line %d  unescaped $( (local command substitution!): %s'
                             % (i, s.strip()[:110]))
                j += 2
                continue
            m = re.match(r'\$([A-Za-z_][A-Za-z0-9_]*)', s[j:j + 40])
            if m:
                n_var += 1
                infos.append('line %d  unescaped $%s (expanded locally; keep if intentional, '
                             'else write \\$%s)' % (i, m.group(1), m.group(1)))
                j += len(m.group(0))
                continue
            j += 1
    stats = dict(lines=e - b + 1,
                 chars=sum(len(lines[i - 1]) for i in range(b, e + 1)),
                 backtick=n_back, cmdsub=n_cmdsub, var=n_var)
    return fails, infos, stats


def run(path):
    raw = open(path, 'rb').read()
    lines = raw.decode('utf-8', 'replace').splitlines()
    b, e = locate(lines)
    print('=' * 96)
    print('ssh remote-script literal guard: %s' % path)
    print('=' * 96)
    if b is None or e is None:
        print('  ANCHOR-MISS: begin=%r -> %s ; end=%r -> %s'
              % (BEGIN_ANCHOR, b, END_ANCHOR[:40], e))
        print('  VERDICT: instrument unusable (refusing to report PASS)')
        return 11
    fails, infos, st = scan(lines, b, e)
    print('  covered: lines %d..%d  (%d lines / %d chars)' % (b, e, st['lines'], st['chars']))
    print('  counts: backtick=%d  $(=%d  $VAR=%d   '
          '(all-zero may mean the CRITERION is wrong, see docstring)'
          % (st['backtick'], st['cmdsub'], st['var']))
    for x in infos:
        print('  [info] %s' % x)
    for x in fails:
        print('  [FAIL] %s' % x)
    print('-' * 96)
    if fails:
        print('  VERDICT: FAIL (%d) - local shell consumes these before ssh sees them' % len(fails))
        return 2
    print('  VERDICT: PASS (no backtick, no unescaped $()')
    return 0


GOOD = [
    '"set -u',
    "       echo '=== C4 ===' >> \\$L",
    '       if [ \\"$REBUILD\\" = \\"2\\" ]; then :; fi',
    '       echo REMOTE-DONE >> \\$L',
    '       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"',
]
BAD_BACKTICK = [
    '"set -u',
    '       # comment with `C4` inside',
    "       echo '=== X ===' >> \\$L",
    '       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"',
]
BAD_CMDSUB = [
    '"set -u',
    '       echo "x=$(date)" >> \\$L',
    '       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"',
]


def selftest():
    print('=' * 96)
    print('selftest: verify the instrument BEFORE trusting its verdict')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        g = (got == want)
        ok = ok and g
        print('   %-58s got=%-4s %s' % (tag, got, 'OK' if g else '*** FAIL'))

    for tag, lines, want in (
            ('good sample -> PASS', GOOD, 0),
            ('bad: backtick -> MUST fail', BAD_BACKTICK, 2),
            ('bad: unescaped $( -> MUST fail', BAD_CMDSUB, 2)):
        b, e = locate(lines)
        if b is None or e is None:
            chk(tag, 11, want)
            continue
        f, _, _ = scan(lines, b, e)
        chk(tag, 2 if f else 0, want)

    b, e = locate(['nope', 'nothing'])
    chk('bad: anchors missing -> MUST report 11', 11 if (b is None or e is None) else 0, 11)

    print()
    print('   selftest verdict: %s' % ('ALL OK - instrument usable' if ok else '*** FAIL - not trustworthy'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('script', nargs='?')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        if not selftest():
            return 2
        print()
    if not a.script:
        return 0
    return run(a.script)


if __name__ == '__main__':
    sys.exit(main())
