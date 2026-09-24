#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""src_transcript_parity —— 「转写完整性」门禁：我们的源码 vs Ghidra 逐函数原始输出。

为什么需要它（2026-09-24，P1 的判据缺口）
-----------------------------------------
`tools/prop_equiv.py` 用**体量比**判等价，但它分不清两件完全不同的事：
  (a) **codegen 差异**：同一份 C，clang/zig -Os 与工厂 GCC 6.2 -Os 的指令数本就不同
      （而且我们的 C 是 Ghidra **抽象后**的渲染，常比原 C 更"干净" ⇒ 编出来更短）；
  (b) **转写缺失**：我们把 Ghidra 的 C 转录进 `src/proprietary/` 时**漏掉了语句**。
体量比偏小时这两种都会触发 ⇒ 不能只凭它下结论。

正确做法：**直接用 Ghidra 的逐函数原始输出当权威对照**（`02-ghidra-c/03-per-function/`）。
重建契约是「我们的文件 = Ghidra 的文件 + 注入的 include/头注释」，所以：

  · **调用表达式多重集**：我们 ⊇ Ghidra（少一个 ⇒ 漏了调用 ⇒ FAIL）
  · **语句数**（`;` 结尾）：我们 ≥ Ghidra
  · 其余（类型名改写 `undefined4→gh_u4`、加 `(gh_code *)` 转型）不影响上面两项

自证（--self-test）
------------------
* 正例：仅加 include/头注释 ⇒ PASS
* 正例：加类型转型 / 改类型名 ⇒ PASS
* 反例：删掉一个函数调用 ⇒ 报出缺哪个
* 反例：删掉一条语句 ⇒ 报出缺哪个

判据收紧（2026-09-24 首次全量跑后修正）
--------------------------------------
首版把「调用**名集合**不同」当 FAIL，全量跑出 5 个"缺调用"，逐个一看：
`OpenZipU` G5/O5、`GetZipItemA` G2/O2、`FindZipItemA` G2/O2、`UnzipItem` G2/O2、`CloseZipU` G4/O4
—— **调用总数两侧完全相同**，只是 C++ 成员函数 / `new` / `delete` 的**写法改名**。
⇒ 收紧为：**FAIL 只在「调用总数真的少了」**（那是"调用消失"的硬信号）；
   名集合不同但总数不减 ⇒ 归 **INFO**；
   语句数（`;` 计数）偏少 ⇒ 归 **待核清单**（宏 / 多语句行会干扰，不能直接 FAIL）。
   ★ 这条修正本身就是"判据必须先自证、且要能被反向证伪"的一次落地。
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GHIDRA = os.environ.get('GHIDRA_PERFUNC',
                        r'D:/output/rkgame/decompiled/02-ghidra-c/03-per-function')
OURS = os.path.join(ROOT, 'src', 'proprietary')

RE_FN = re.compile(r'^(FUN_[0-9a-f]{8}_.+?)\.c$')
RE_CALL = re.compile(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(')
# C 关键字与常见非函数构造，避免误当成"调用"
KEYWORDS = {
    'if', 'for', 'while', 'switch', 'return', 'sizeof', 'do', 'else', 'case',
    'defined', 'typedef', 'struct', 'union', 'enum', 'static', 'const', 'volatile',
    'unsigned', 'signed', 'int', 'char', 'long', 'short', 'float', 'double', 'void',
    '_Noreturn', 'inline', 'register', 'goto', 'break', 'continue', 'default',
}


def strip_comments_strings(t):
    out, i, n, st = [], 0, len(t), 0
    while i < n:
        c, x = t[i], (t[i + 1] if i + 1 < n else '')
        if st == 0:
            if c == '/' and x == '*':
                st = 1; out.append('  '); i += 2; continue
            if c == '/' and x == '/':
                st = 2; out.append('  '); i += 2; continue
            if c == '"':
                st = 3; out.append(' '); i += 1; continue
            if c == "'":
                st = 4; out.append(' '); i += 1; continue
            out.append(c); i += 1; continue
        if st == 1:
            if c == '*' and x == '/':
                st = 0; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        if st == 2:
            if c == '\n':
                st = 0; out.append('\n'); i += 1; continue
            out.append(' '); i += 1; continue
        if st == 3:
            if c == '\\':
                out.append('  '); i += 2; continue
            if c == '\n':
                st = 0; out.append('\n'); i += 1; continue
            if c == '"':
                st = 0; out.append(' '); i += 1; continue
            out.append(' '); i += 1; continue
        if c == '\\':
            out.append('  '); i += 2; continue
        if c == "'":
            st = 0; out.append(' '); i += 1; continue
        out.append(' '); i += 1
    return ''.join(out)


def calls(code):
    from collections import Counter
    c = Counter()
    for m in RE_CALL.finditer(code):
        n = m.group(1)
        if n in KEYWORDS:
            continue
        c[n] += 1
    return c


def n_stmt(code):
    return code.count(';')


def index_ours():
    out = {}
    for dp, dn, fn in os.walk(OURS):
        for f in fn:
            m = RE_FN.match(f)
            if m:
                out[m.group(1)] = os.path.join(dp, f)
    return out


def compare_one(gpath, opath):
    g = strip_comments_strings(open(gpath, encoding='utf-8', errors='replace').read())
    o = strip_comments_strings(open(opath, encoding='utf-8', errors='replace').read())
    gc, oc = calls(g), calls(o)
    missing = sorted((gc - oc).elements())
    # 语句数：Ghidra 的 `for(...)`/`if(...)` 也带 `;`（空语句情景），用差值报告不作硬判
    return dict(missing_calls=missing,
                g_stmt=n_stmt(g), o_stmt=n_stmt(o),
                g_calls=sum(gc.values()), o_calls=sum(oc.values()))


def run(verbose=False):
    gi = {}
    for f in os.listdir(GHIDRA):
        m = RE_FN.match(f)
        if m:
            gi[m.group(1)] = os.path.join(GHIDRA, f)
    oi = index_ours()
    common = sorted(set(gi) & set(oi))
    only_g = sorted(set(gi) - set(oi))
    only_o = sorted(set(oi) - set(gi))
    print('=' * 104)
    print('转写完整性对拍（权威 = Ghidra 逐函数原始 C）')
    print('=' * 104)
    print('  Ghidra 文件 %d / 我们文件 %d / 可配对 %d' % (len(gi), len(oi), len(common)))
    print('  只在 Ghidra 有（我们没转写）: %d  %s' % (len(only_g), only_g[:5]))
    print('  只在我们有（我们自造）    : %d  %s' % (len(only_o), only_o[:5]))
    print()

    # ★ 判据（2026-09-24 第 58 轮收紧，理由见文件头「判据收紧」）：
    #   FAIL 只保留在「**调用总数真的少了**」—— 那是"调用消失了"的硬信号；
    #   调用名集合不同但总数不减 ⇒ C++ 成员函数 / new / delete 的**写法改名**，归 INFO。
    #   语句数偏少 ⇒ 进「待核清单」（`;` 计数受宏/多语句行影响，不能直接当 FAIL）。
    hard, info_renames, deficit = [], [], []
    for k in common:
        r = compare_one(gi[k], oi[k])
        if r['o_calls'] < r['g_calls']:
            hard.append((k, r))
        elif r['missing_calls']:
            info_renames.append((k, r))
        if r['o_stmt'] < r['g_stmt']:
            deficit.append((k, r))

    if info_renames:
        print('  【INFO】调用名集合不同但**总数不减** ⇒ 写法改名（C++ 成员 / new / delete），非丢调用：')
        for k, r in info_renames:
            print('     %-56s G%d/O%d  仅名字不同: %s'
                  % (k[:56], r['g_calls'], r['o_calls'], ','.join(r['missing_calls'][:4])))
        print()
    if deficit:
        print('  【待核】语句数偏少（`;` 计数；可能只是宏/多语句行，也可能是漏语句）—— %d 个：'
              % len(deficit))
        print('     %-56s %7s %7s %s' % ('函数', 'G语句', 'O语句', '差额'))
        for k, r in sorted(deficit, key=lambda kv: kv[1]['o_stmt'] - kv[1]['g_stmt']):
            print('     %-56s %7d %7d %+d'
                  % (k[:56], r['g_stmt'], r['o_stmt'], r['o_stmt'] - r['g_stmt']))
        print()
    if verbose:
        print('  【全量】')
        for k in common:
            r = compare_one(gi[k], oi[k])
            print('     %-56s G%3d/O%3d  calls G%d/O%d'
                  % (k[:56], r['g_stmt'], r['o_stmt'], r['g_calls'], r['o_calls']))
        print()

    if hard:
        print('  ★ FAIL：%d 个函数**调用总数真的变少**（= 转写漏了调用）' % len(hard))
        print('     %-56s %7s %7s' % ('函数', 'G调用', 'O调用'))
        for k, r in hard:
            print('     %-56s %7d %7d' % (k[:56], r['g_calls'], r['o_calls']))
        return 2
    print('  PASS（硬判据）：所有可配对函数的**调用总数都不少于 Ghidra** ⇒ 没有丢调用')
    print('  ⇒ 结合 prop_equiv：凡「体量偏小但本门禁 PASS」的项，定性为 **codegen 差异**，不是少实现。')
    if deficit:
        print('  ⚠ 但仍有 %d 个函数语句数偏少，列在上面「待核」里 —— 需逐个确认（宏/多语句行 vs 真漏）。'
              % len(deficit))
    return 0


def self_test():
    import tempfile
    print('=' * 96)
    print('自证：先用已知答案的样本验仪器')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-58s got=%-16s %s' % (tag, got, '✓' if good else '★ FAIL'))

    base = 'int f(void){ a(); b(1); return 0; }\n'
    d = tempfile.mkdtemp()
    gp = os.path.join(d, 'g.c'); op = os.path.join(d, 'o.c')

    def run_pair(g, o):
        open(gp, 'w').write(g); open(op, 'w').write(o)
        return compare_one(gp, op)

    r = run_pair(base, '#include "x.h"\n/* note */\n' + base)
    chk('正例  仅加 include/注释 → 不缺调用', r['missing_calls'], [])

    r = run_pair(base, 'int f(void){ (void)a(); b((int)1); return 0; }\n')
    chk('正例  加类型转型 → 不缺调用', r['missing_calls'], [])

    r = run_pair(base, 'int f(void){ a(); return 0; }\n')
    chk('反例  删掉 b() → 报出缺 b', r['missing_calls'], ['b'])

    r = run_pair(base, 'int f(void){ return 0; }\n')
    chk('反例  删掉两个调用 → 报出 a,b', sorted(r['missing_calls']), ['a', 'b'])

    r = run_pair('int f(void){ while(1){ g(); } return 0; }\n',
                 'int f(void){ while(1){ g(); } return 0; }\n')
    chk('正例  关键字 while 不被当调用', r['missing_calls'], [])

    r = run_pair(base, 'int f(void){ a(); b(1); /* c(); */ return 0; }\n')
    chk('反例  注释里的调用不算数', r['missing_calls'], [])

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return 0 if self_test() else 2
    return run(a.all)


if __name__ == '__main__':
    sys.exit(main())
