#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compat_vs_glibc.py —— 「我们的 compat 头」× 「真实 glibc sysroot」的**同名声明对拍**。

存在的理由（第 66 轮）：
  我们一直用 `-target arm-linux-gnueabihf.2.7` 编译（编译头 = glibc 2.7），而工厂的
  编译头是 **glibc 2.24**（DWARF + `.rodata` 双重证据）。切到真实 2.24 工具链时，
  凡"我们声明了、glibc 也声明了"的名字都可能撞车——`__timezone_ptr_t` 就是这么撞的
  （我们缺 `__restrict` ⇒ `error: conflicting type qualifiers`），而**一次 CI 只暴露一个**。

  本工具把这一类**在推之前一次列全**：
    · 输入 A：`src/compat/ghidra_compat.h` 里我们声明的名字 + 声明原文；
    · 输入 B：真实 sysroot 的 `usr/include/**` 里同名声明原文；
    · 输出：两边都有 ⇒ **逐字对拍**，不一致的按风险分级列出。

★ 为什么必须"逐字对拍"而不是"看起来像"：C11 允许 typedef 重声明**为同一类型**，
  限定符差一个 `__restrict` 就是 `conflicting type qualifiers` —— 肉眼看不出来。

自证（--selftest）不依赖本项目数据：用合成的两份文本验证归类逻辑，
含**缺陷态**（不同限定符必须报 MISMATCH）与**正例**（逐字相同必须报 MATCH）。

用法：
  python tools/compat_vs_glibc.py                    # 自动找 cache_tc/bootlin*/…/sysroot
  SYSROOT=… python tools/compat_vs_glibc.py
  python tools/compat_vs_glibc.py --selftest
exit: 0 = 无高危不一致 / 1 = 有高危（必须处理）/ 2 = 无 sysroot 可测（不可判）
"""
import argparse
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HDR = os.path.join(ROOT, 'src', 'compat', 'ghidra_compat.h')

# ---------------------------------------------------------------- 声明抽取 --
# 只抽"引入一个名字"的形态：typedef / #define / extern 变量 / 函数原型。
RE_TYPEDEF = re.compile(r'^\s*typedef\s+(?P<rest>.+?)\s*;\s*$')
RE_DEFINE = re.compile(r'^\s*#\s*define\s+(?P<name>[A-Za-z_]\w*)(?P<rest>[^(].*)?$')
RE_EXTERN = re.compile(r'^\s*extern\s+(?P<rest>.+?)\s*;\s*$')
RE_FUNC = re.compile(r'^\s*(?:[\w\s\*]+?)\s+(?P<name>[A-Za-z_]\w*)\s*\((?P<args>[^;]*)\)\s*;\s*$')
RE_IDENT_TAIL = re.compile(r'([A-Za-z_]\w*)\s*(\[[^\]]*\])?\s*$')


def strip_comments(txt):
    txt = re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    txt = re.sub(r'//[^\n]*', ' ', txt)
    return txt


def join_continuations(txt):
    return txt.replace('\\\n', ' ')


def decl_name(rest):
    """从声明体里取"被声明的名字"。

    四种形态都要覆盖（第 66 轮自证抓到我第一版漏了第三种）：
      ① typedef struct timezone *__restrict __timezone_ptr_t;   → 尾部标识符
      ② typedef int (*__cmp)(const struct dirent *, …);         → 括号内 *NAME
      ③ typedef int __selector (const struct dirent *);         → NAME(  （**函数 typedef**）
      ④ char *foo[8];                                           → 尾部标识符（含数组）
    ★ 漏掉任何一类 = 审计覆盖不足，而"没抽到"与"没冲突"在输出上一样（静默漏）。
    """
    rest = rest.strip()
    m = re.search(r'\(\s*\*\s*([A-Za-z_]\w*)\s*\)', rest)          # ②
    if m:
        return m.group(1)
    head = re.sub(r'\([^()]*\)', '', rest).strip()                  # 去掉参数表（可多层）
    head = re.sub(r'\([^()]*\)', '', head).strip()
    if rest.endswith(')') and head != rest:
        name = decl_name(head)                                     # ③ 参数表已剥离
        if name:
            return name
    m = RE_IDENT_TAIL.search(rest)                                 # ①④
    return m.group(1) if m else None


def func_name(stmt):
    r"""函数原型里**被声明的名字** = 第一个"未被 `*` 前缀"的 `IDENT (` 的那个 IDENT。

    ★ 不能复用 `decl_name`：它优先匹配"括号内 `*NAME`"（为函数指针 typedef 而设），
      用在函数原型上会抽出**参数名**（实测 glibc `scandir` 原型里的 `__selector` 假阳性）。
    ★ 也不能靠"剥掉尾部属性"来简化：`__\w+\s*\(` 会把**合法名字**（`__selector` 本身
      就匹配 `__\w+`）连名字一起吃掉 —— 上一版就是这么坏的（自证当场抓到）。
      改用"取第一个非 `*` 前缀的 `IDENT (`"，属性与参数自然被跳过。
    """
    t = stmt.strip().rstrip(';').strip()
    m = re.search(r'(?<!\*)\b([A-Za-z_]\w*)\s*\(', t)
    return m.group(1) if m else None


def normalize(s):
    """归一化用于逐字对拍：压缩空白、去掉数组大小以外的装饰差异**不做**语义改写。

    ★ 只压缩空白与指针间距，**不**删限定符 —— 删了就看不出 `__restrict` 的缺失，
      而那正是本工具要抓的东西。
    """
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'\s*\*\s*', ' *', s)
    s = re.sub(r'\s*\(\s*', ' (', s)
    return s


def statements(text):
    """→ 顶层语句列表（`;` 收尾、花括号深度感知；`#` 指令各自成句）。

    ★ 为什么不能按行：`typedef struct { … } NAME;` 这类**跨行**声明里，
      名字在后面的行上 ⇒ 按行解析时整条声明落在审计之外（实测 3 条）。
    """
    out, buf, depth = [], [], 0
    for raw in join_continuations(strip_comments(text)).split('\n'):
        line = raw.strip()
        if not line:
            continue
        if not buf and line.startswith('#'):
            out.append(line)
            continue
        buf.append(line)
        depth += line.count('{') - line.count('}')
        if line.endswith(';') and depth <= 0:
            out.append(' '.join(buf))
            buf, depth = [], 0
    if buf:
        out.append(' '.join(buf))
    return out


def parse_decls(text, missed=None, tried=None):
    """→ {名字: [声明原文, ...]}（同名可多次声明，保留全部）。

    ★ `missed` 不为 None 时收集"看似引入名字、却没抽出名字"的行 —— 这是**覆盖门禁**：
      审计的漏是静默的（"没抽到"与"没冲突"在输出上一样）。
    """
    out = {}
    for line in statements(text):
        m = RE_DEFINE.match(line)
        if m and not line.startswith('#if') and not line.startswith('#define _'):
            out.setdefault(m.group('name'), []).append(normalize(line))
            continue
        m = RE_TYPEDEF.match(line)
        if m:
            nm = decl_name(m.group('rest'))
            if nm:
                out.setdefault(nm, []).append(normalize(line))
            elif missed is not None:
                missed.append(line)
            continue
        m = RE_EXTERN.match(line)
        if m:
            rest = m.group('rest')
            # ★ 先按"函数原型"取名字（第一个非 `*` 前缀的 `IDENT (`）——否则会抽出
            #   参数表里的**参数名**（实测 glibc `scandir` 原型里的 `(*__selector)`）。
            #   不是函数原型（如 `extern gh_undef * foo;`）才退回变量取法。
            nm = func_name(rest) if '(' in rest else None
            if not nm:
                mf = RE_FUNC.match('x ' + rest)
                nm = mf.group('name') if mf else decl_name(rest)
            if nm:
                out.setdefault(nm, []).append(normalize('extern ' + rest))
            elif missed is not None:
                missed.append(line)
            continue
        # 无 extern 前缀的函数原型（`int foo(int);`）同样"引入了一个名字"
        if line.endswith(';') and '(' in line and ')' in line and not line.startswith('#'):
            nm = func_name(line)
            if nm:
                out.setdefault(nm, []).append(normalize(line))
    return out


def reconcile(text, names, missed):
    """→ (原始行数, 未解释行列表)。

    ★ 覆盖门禁的正确口径：**从原始行出发**，而不是从"我尝试过的行"出发。
      未解释行必须为 0，否则本审计对那部分**没有观测力**（"没抽到"≠"没冲突"）。
    """
    raw, unacc = [], []
    for t in statements(text):
        is_decl = (t.startswith('typedef') or t.startswith('extern')
                   or bool(re.match(r'#\s*define\s+[A-Za-z_]\w*', t)))
        if not is_decl:
            continue
        raw.append(t)
        if t in missed:
            continue
        m = RE_DEFINE.match(t)
        if m:
            continue                                   # 已按宏登记
        mm = RE_TYPEDEF.match(t)
        if mm:
            if decl_name(mm.group('rest')):
                continue
        else:
            # extern：函数原型取函数名；否则是**变量**（如 `extern gh_undef * foo;`）取变量名。
            me = RE_EXTERN.match(t)
            if me:
                rest = me.group('rest')
                if ('(' in rest and func_name(rest)) or decl_name(rest):
                    continue
            elif '(' in t and t.endswith(';') and func_name(t):
                continue
        unacc.append(t)
    return len(raw), unacc


# ------------------------------------------------------------ glibc 侧索引 --
def index_sysroot(sr):
    """→ {名字: [(头文件相对路径, 声明原文)]}，只索引 usr/include 下的 .h。"""
    inc = os.path.join(sr, 'usr', 'include')
    idx = {}
    for dirpath, _dirs, files in os.walk(inc):
        for fn in files:
            if not fn.endswith('.h'):
                continue
            p = os.path.join(dirpath, fn)
            try:
                txt = io.open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            rel = os.path.relpath(p, sr)
            for nm, ds in parse_decls(txt).items():
                for d in ds:
                    idx.setdefault(nm, []).append((rel, d))
    return idx


# ------------------------------------------------------------------ 分类 ----
def classify(ours, theirs):
    """→ ('MATCH'|'WEAK'|'MISMATCH', 说明)

    MATCH    : 声明体（去掉前导 typedef/extern 后）逐字相同
    WEAK     : 不同但**在 C 里共存是无害的**（例如我们是 #define 常量）
    MISMATCH : 其余 —— 需要人工看，且**很可能**就是下一个 conflicting 报错
    """
    a = strip_kw(ours)
    for t in theirs:
        if a == strip_kw(t):
            return 'MATCH', '与 glibc 逐字相同'
    return 'MISMATCH', '与 glibc 的声明不同'


def strip_kw(s):
    s = s.strip()
    for k in ('typedef ', 'extern '):
        if s.startswith(k):
            s = s[len(k):]
    return s.rstrip(';').strip()


def compare(our, idx, limit_detail=40):
    rows = []
    for nm, ours_list in sorted(our.items()):
        if nm not in idx:
            continue
        ours = ours_list[0]
        theirs = [t for _f, t in idx[nm]]
        verdict, why = classify(ours, theirs)
        # glibc 侧的文件清单（可审计）
        files = sorted({f for f, _t in idx[nm]})[:3]
        rows.append((nm, verdict, ours, theirs[0], files))
    return rows


# ---------------------------------------------------------------- 自证 ------
def selftest():
    chk = []

    def c(label, got, want):
        chk.append((label, got, want))

    a = parse_decls('typedef struct timezone *__restrict __timezone_ptr_t;')
    c('typedef 能抽到名字', list(a), ['__timezone_ptr_t'])
    afp = parse_decls('typedef int (*__selector) (const struct dirent *);')
    c('函数指针 typedef 能抽到名字', list(afp), ['__selector'])
    ad = parse_decls('#define NEED_ALIGN 1')
    c('#define 能抽到名字', list(ad), ['NEED_ALIGN'])

    ours_ok = 'typedef struct timezone *__restrict __timezone_ptr_t;'
    ours_bad = 'typedef struct timezone *__timezone_ptr_t;'
    glibc = ['typedef struct timezone *__restrict __timezone_ptr_t;']
    c('正例 逐字相同 ⇒ MATCH', classify(ours_ok, glibc)[0], 'MATCH')
    # ★ 缺陷态：只差一个 __restrict —— 肉眼几乎看不出，编译器报 conflicting type qualifiers
    c('缺陷态 缺 __restrict ⇒ MISMATCH', classify(ours_bad, glibc)[0], 'MISMATCH')
    c('缺陷态 void* vs struct* ⇒ MISMATCH',
      classify('typedef void *__timezone_ptr_t;', glibc)[0], 'MISMATCH')
    c('归一化不吞掉限定符',
      normalize('typedef struct timezone *__restrict T;') !=
      normalize('typedef struct timezone *T;'), True)

    # 覆盖门禁锚点：能抽到名字的行不得落进 missed；抽出名字才算覆盖
    miss = []
    got2 = parse_decls('typedef int __selector (const struct dirent *);', missed=miss)
    c('函数 typedef 抽到名字且不落 missed', (sorted(got2), miss), (['__selector'], []))
    c('匿名 struct 的 typedef 仍抽到别名',
      'Anonymous' in parse_decls('typedef struct { int a; } Anonymous;'), True)

    # ★ 假阳性锚点：glibc scandir 的**参数名** __selector 不得被登记成声明名
    gl = ('extern int scandir (const char *__restrict d, struct dirent ***n, '
          'int (*__selector) (const struct dirent *), int (*__cmp) (const struct dirent **, '
          'const struct dirent **)) __nonnull ((1, 2));')
    got_g = parse_decls(gl)
    c('函数原型取到的是 scandir 而不是参数名', sorted(got_g), ['scandir'])
    c('反例 参数名 __selector 不得出现', '__selector' in got_g, False)
    c('func_name 对 typedef 风格原型也正确',
      func_name('typedef int __selector (const struct dirent *)'), '__selector')

    # 跨行 typedef 锚点（第一版按行解析时整体漏掉，实测 3 条）
    multi = 'typedef struct {\n  unsigned int a;\n  unsigned int b;\n} u64_pair_blob_t;'
    c('跨行 typedef 抽到别名 u64_pair_blob_t',
      'u64_pair_blob_t' in parse_decls(multi), True)
    nraw_m, un_m = reconcile(multi, parse_decls(multi), [])
    c('跨行 typedef 不落未解释', (nraw_m, un_m), (1, []))

    # 对账锚点：必须为零未解释；且**故意**给一段无法解释的行时必须报出来
    nraw, un = reconcile('typedef struct timezone *__restrict T;\nextern int g;', {}, [])
    c('对账 规范声明 ⇒ 未解释 0', (nraw, un), (2, []))
    nraw2, un2 = reconcile('typedef ;', {}, [])
    c('对账 畸形声明 ⇒ 未解释 1（不得静默）', len(un2), 1)

    # 端到端：仓库里必须真的能抽到 __selector/__cmp（这两个是真用了的类型）
    try:
        txt = io.open(HDR, encoding='utf-8').read()
        d = parse_decls(txt)
        c('端到端 我们头里抽到 __selector', '__selector' in d, True)
        c('端到端 我们头里抽到 __cmp', '__cmp' in d, True)
    except OSError:
        pass
    return chk


def find_sysroot():
    if os.environ.get('SYSROOT') and os.path.isdir(os.path.join(os.environ['SYSROOT'], 'usr', 'include')):
        return os.environ['SYSROOT']
    import glob
    # ★ 优先 bootlin63（= A/B 的对照腿），bootlin54 仅作后备。
    for pat in ('cache_tc/bootlin63/arm-*/sysroot', 'cache_tc/bootlin*/arm-*/sysroot',
                'cache_tc/bootlin*/sysroot'):
        hits = sorted(glob.glob(os.path.join(ROOT, pat)))
        for h in hits:
            if os.path.isdir(os.path.join(h, 'usr', 'include')):
                return h
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', '--self-test', dest='self_test', action='store_true')
    ap.add_argument('--out')
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

    sr = find_sysroot()
    if not sr:
        print('无真实 sysroot ⇒ 不可判（不得当作通过）。获取：sh build/_dl_tc.sh')
        return 2
    htxt = io.open(HDR, encoding='utf-8').read()
    missed = []
    our = parse_decls(htxt, missed=missed)
    nraw, unacc = reconcile(htxt, our, missed)
    idx = index_sysroot(sr)
    rows = compare(our, idx)
    L = []
    L.append('=' * 96)
    L.append('compat_vs_glibc：我们的声明 vs 真实 glibc sysroot')
    L.append('=' * 96)
    L.append('  sysroot      = %s' % os.path.relpath(sr, ROOT))
    L.append('  我们声明数   = %d' % len(our))
    L.append('  ★ 覆盖门禁   = 原始 typedef/extern/#define 行 %d 条；未解释 %d 条%s'
             % (nraw, len(unacc),
                '' if not unacc else '（**必须为 0**，否则那部分本审计没有观测力）'))
    for m in unacc[:10]:
        L.append('       未解释: %s' % m[:100])
    L.append('                 其中主动登记为 missed 的 %d 条' % len(missed))
    L.append('  glibc 名字数 = %d' % len(idx))
    L.append('  ★ 同名（可能撞车）= %d' % len(rows))
    bad = [r for r in rows if r[1] == 'MISMATCH']
    L.append('  其中 MISMATCH = %d' % len(bad))
    L.append('')
    L.append('  ---- MISMATCH（逐条：我们 / glibc / 出处）----')
    for nm, v, o, t, files in bad[:60]:
        L.append('  [%s]' % nm)
        L.append('      我们 : %s' % o)
        L.append('      glibc: %s' % t)
        L.append('      出处 : %s' % ', '.join(files))
    L.append('')
    L.append('  ---- MATCH（同名且逐字相同，安全）----')
    L.append('    %s' % ', '.join(r[0] for r in rows if r[1] == 'MATCH') or '（无）')
    txt = '\n'.join(L)
    print(txt)
    if a.out:
        io.open(a.out, 'w', encoding='utf-8', newline='\n').write(txt + '\n')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
