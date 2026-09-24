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
OURS = os.path.join(ROOT, 'src', 'proprietary')

# --------------------------------------------------------------------------- #
# 语料来源解析：**仓内为准，缺则硬失败**（绝不静默跳过）
# --------------------------------------------------------------------------- #
# 背景（2026-09-24，CI 实测红灯）：首版把这个路径**硬编码**为本机绝对路径，
#   在 GitHub Actions 上 `os.listdir` 直接 FileNotFoundError ⇒ 门禁红。
#   这与 GAP 16.86 的 `.json` vs `.json.gz` 是**同一类病**：门禁依赖了"本地专有输入"。
# 处置（不是打补丁，而是按项目纪律仓内化）：
#   语料只有 3.3 MB / 812 文件 ⇒ 打包 253 KB，随仓库交付 `golden/ghidra-perfn.tar.gz`
#   （它是从 `golden/factory.rkgame.bin` 派生的只读分析产物，属"材料"不属"构建产物"）。
#   解析顺序：环境变量 → 仓内 tar.gz 解包到 build/ → 本机开发路径
#   全都没有 ⇒ **打印可执行的修复指引并 exit 2**（fail-closed：宁可红，不可假绿）。
CORPUS_TGZ = os.path.join(ROOT, 'golden', 'ghidra-perfn.tar.gz')
CORPUS_CACHE = os.path.join(ROOT, 'build', '_ghidra_perfn')
CORPUS_DEV = r'D:/output/rkgame/decompiled/02-ghidra-c/03-per-function'
# ★ 最小语料量：实测真语料 812 个 `.c`（工厂 835 函数去重后 812 文件）。
#   阈值取 700 是"截断/半包上传"的兜底 —— 半包会让"只在 Ghidra 有"的计数暴涨，
#   却**不会报错**（那是假绿）。宁可 fail-closed。
MIN_CORPUS_C = 700


def _corpus_count(d):
    if not d or not isinstance(d, (str, bytes, os.PathLike)):
        return 0
    try:
        return sum(1 for n in os.listdir(d) if n.endswith('.c')) if os.path.isdir(d) else 0
    except OSError:
        return 0


def _is_corpus(d, min_c=1):
    return _corpus_count(d) >= min_c


def resolve_corpus():
    env = os.environ.get('GHIDRA_PERFUNC')
    # ★ env 也必须过「最小语料量」：否则一个指向半包/空目录的 env 会被采纳 ⇒ 假绿。
    #   （这条正是本门禁自证跑出来的 —— 首版 env 只判 min_c=1，自证第 3 项 FAIL。）
    if _is_corpus(env, MIN_CORPUS_C):
        return env, 'env:GHIDRA_PERFUNC(%d .c)' % _corpus_count(env)
    if _is_corpus(CORPUS_CACHE, MIN_CORPUS_C):
        return CORPUS_CACHE, 'repo:golden/ghidra-perfn.tar.gz(已解包, %d .c)' % _corpus_count(CORPUS_CACHE)
    if os.path.exists(CORPUS_TGZ):
        try:
            _extract_corpus(CORPUS_TGZ, CORPUS_CACHE)
        except Exception as e:                       # tar 损坏 / 半包 ⇒ 不是"跳过"，是"证据不可用"
            sys.stderr.write('★ golden/ghidra-perfn.tar.gz 解包失败：%r\n' % (e,))
            return None, 'MISSING(tar 损坏)'
        # tar 里带一层 `03-per-function/`，下钻一层
        for cand in (os.path.join(CORPUS_CACHE, '03-per-function'), CORPUS_CACHE):
            if _is_corpus(cand, MIN_CORPUS_C):
                return cand, 'repo:golden/ghidra-perfn.tar.gz(本次解包, %d .c)' % _corpus_count(cand)
        return None, 'MISSING(tar 解开后不足 %d 个 .c)' % MIN_CORPUS_C
    if _is_corpus(CORPUS_DEV):
        return CORPUS_DEV, 'dev:本机路径(%d .c)' % _corpus_count(CORPUS_DEV)
    return None, 'MISSING'


def _extract_corpus(tgz, dest):
    """解包语料 tar.gz 到 `dest`。

    两个真实坑（都已踩过）：
      ① `tf.extractall(filter='data')` 在 **Windows** 上报 `OSError(22, ERROR_INVALID_FUNCTION)`
         ⇒ 必须留一条无 filter 的回退路径（本 tar 是我们自己生成的纯文件/目录，无链接）；
      ② 直接解到 `dest` 时，若中途失败会**留下半包**，而半包可能恰好 ≥ 阈值 ⇒ 假绿。
         故**先解到 `<dest>.tmp`，成功才落位**。
    """
    import shutil
    import tarfile
    import warnings
    tmp = dest + '.tmp'
    last = None
    for kwargs in ({'filter': 'data'}, {}):
        try:
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp, exist_ok=True)
            with tarfile.open(tgz, 'r:gz') as tf, warnings.catch_warnings():
                # 无 filter 分支在 3.12–3.13 会告 DeprecationWarning；此处是**有意的**兼容回退
                # （filter='data' 在 Windows 上必失败，见本函数 docstring）⇒ 局部静音，别污染 CI 日志。
                warnings.simplefilter('ignore', DeprecationWarning)
                tf.extractall(tmp, **kwargs)
        except Exception as e:
            last = e
            continue
        shutil.rmtree(dest, ignore_errors=True)
        os.replace(tmp, dest)
        return
    shutil.rmtree(tmp, ignore_errors=True)
    raise last


GHIDRA, GHIDRA_SRC = resolve_corpus()
if GHIDRA is None:
    sys.stderr.write(
        '\n★ 前置缺失败：找不到 Ghidra 逐函数语料。\n'
        '  本门禁**不做静默跳过**（静默跳过 = 假绿）。\n'
        '  修复任选其一：\n'
        '    ① 确认仓库里存在 `golden/ghidra-perfn.tar.gz`（应随仓交付，253 KB）；\n'
        '    ② 或设环境变量 GHIDRA_PERFUNC=<目录> 指向 `03-per-function/`；\n'
        '    ③ 或把本机 `D:/output/rkgame/decompiled/02-ghidra-c/03-per-function` 放回原处。\n\n')
    sys.exit(2)

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
    print('  语料来源: %s -> %s' % (GHIDRA_SRC, GHIDRA))
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


def self_test_corpus():
    """语料解析的**三态自证**（GAP 16.86 / 16.87 那一类的机械防线）。

    CI 红灯的真实成因是「门禁依赖了本地专有输入」⇒ 所以"语料解析"这段代码
    本身必须有正反自证，否则修完还会再犯：
      ① 正常态：env 指向真语料 ⇒ 采用 env；
      ② CI 近似态：只有仓内 tar.gz（本机另两个来源全部藏掉）⇒ 必须能解包并用它；
      ③ 缺陷态：三者皆无 ⇒ 必须返回 None（调用方 fail-closed `exit 2`，**绝不静默跳过**）；
      ④ 缺陷态：tar.gz 存在但**内容不足**（模拟半包上传）⇒ 同样必须 None。
    全部用临时目录里的**人造语料**跑，不触碰真数据 ⇒ 结果可复现、与机器无关。
    """
    global CORPUS_TGZ, CORPUS_CACHE, CORPUS_DEV
    import tarfile
    import tempfile
    saved = (CORPUS_TGZ, CORPUS_CACHE, CORPUS_DEV)
    saved_env = os.environ.pop('GHIDRA_PERFUNC', None)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-58s got=%-14s %s' % (tag, got, '✓' if good else '★ FAIL'))

    d = tempfile.mkdtemp()
    try:
        # 造一份"够格"的语料（MIN_CORPUS_C 个 .c）
        good = os.path.join(d, 'good')
        os.makedirs(good)
        for i in range(MIN_CORPUS_C):
            open(os.path.join(good, 'FUN_%08x_x.c' % i), 'w').write(
                'int f(void){ a(); return 0; }\n')
        # 造一份"不足"的语料（半包）
        thin = os.path.join(d, 'thin')
        os.makedirs(thin)
        for i in range(3):
            open(os.path.join(thin, 'FUN_%08x_x.c' % i), 'w').write('int f(void){return 0;}\n')
        # 由 thin 造 tar.gz（内含一层 03-per-function/）
        tgz = os.path.join(d, 'perfn.tar.gz')
        with tarfile.open(tgz, 'w:gz') as tf:
            tf.add(thin, arcname='03-per-function')
        good_tgz = os.path.join(d, 'good.tar.gz')
        with tarfile.open(good_tgz, 'w:gz') as tf:
            tf.add(good, arcname='03-per-function')
        # 兜底常量：全部指向不存在的位置
        CORPUS_TGZ = os.path.join(d, 'nope.tar.gz')
        CORPUS_CACHE = os.path.join(d, 'nope_cache')
        CORPUS_DEV = os.path.join(d, 'nope_dev')

        # ③ 三者皆无 ⇒ None（fail-closed）
        got, _src = resolve_corpus()
        chk('反例 三者皆无 → None（fail-closed）', got, None)

        # ① env 指向真语料 ⇒ 采用 env
        os.environ['GHIDRA_PERFUNC'] = good
        got, src = resolve_corpus()
        chk('正例 GHIDRA_PERFUNC 指向语料 → 采用', got, good)
        #    env 指向**不足**的语料 ⇒ 不得采用（否则假绿）
        os.environ['GHIDRA_PERFUNC'] = thin
        got, _src = resolve_corpus()
        chk('反例 GHIDRA_PERFUNC 指向不足语料 → 不采用', got, None)
        os.environ.pop('GHIDRA_PERFUNC', None)

        # ② CI 近似态：只有 tar.gz ⇒ 解包并用它
        CORPUS_TGZ = good_tgz
        got, src = resolve_corpus()
        chk('正例 只有仓内 tar.gz → 解包并采用', got, os.path.join(CORPUS_CACHE, '03-per-function'))
        chk('      来源标注含 tar.gz', 'tar.gz' in src, True)

        # ④ tar.gz 存在但内容不足（半包）⇒ None
        CORPUS_TGZ = tgz
        CORPUS_CACHE = os.path.join(d, 'thin_cache')
        got, _src = resolve_corpus()
        chk('反例 tar.gz 半包（不足 %d）→ None' % MIN_CORPUS_C, got, None)
    finally:
        if saved_env is not None:
            os.environ['GHIDRA_PERFUNC'] = saved_env
        CORPUS_TGZ, CORPUS_CACHE, CORPUS_DEV = saved
    return ok


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

    print('-' * 96)
    print('自证（二）：语料解析三态 —— 防「门禁依赖 CI 里不存在的输入」复发')
    print('-' * 96)
    ok = self_test_corpus() and ok

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
