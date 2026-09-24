#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""equiv_group_sum —— 按**归一化函数组**求和再比体量（修 prop_equiv 的单代表口径）。

为什么要它（2026-09-23/24 P1 的口径缺陷）
----------------------------------------
`tools/prop_equiv.py` 的配对逻辑是「**单代表**」：
* 工厂侧 `fac_idx[nk]` 只保留**指令数最多**的那个克隆；
* 我们侧 `re_syms.get(nm) or re_idx.get(nk)` 先按**原名**取，取到一个小块就停。
  而 clang/zig **同样会**产出 `foo.part.0` / `foo.isra.7` / `foo.constprop.3` / `foo.cold`
  / `foo.llvm.*` 这类拆分符号。

⇒ 当 GCC 把工厂的 `popwindows` 拆成 `popwindows` + `popwindows.part.0`、而我们也拆成两块时，
  两侧各取一块随机比较，**"我们偏小"这个结论可能纯属口径伪影**。
  工具自带的注释也写着「疑编译器分段（查紧随地址）或真的少实现」——本工具就是把"查紧随地址"
  机械化：**归一化组内求和后再比**。

判据
----
对每个归一化名：
    Σ工厂 = 该组所有克隆的 **纯指令字节**（= (n − #.word) × 4，与 prop_equiv 同一修正）
    Σ我们 = 该组所有克隆的符号 size 之和
    ratio = Σ我们 / Σ工厂     skew = max(ratio, 1/ratio)
* skew < 1.6 ⇒ OK（等价性可接受）
* 1.6 ≤ skew < 2.5 ⇒ WARN
* skew ≥ 2.5 ⇒ FAIL
★ 与 prop_equiv 的**关键差别**：这里两侧都**求和**，且**逐克隆列出明细**，
  所以"编译器分段"与"真少实现"可以**当场区分**（前者两侧组和接近，后者仍显著偏小）。

自证（--self-test）
------------------
* 正例：工厂 {foo:100} / 我们 {foo:60, foo.part.0:40} ⇒ 组和相等 ⇒ OK
* 反例：工厂 {foo:100} / 我们 {foo:60}          ⇒ 仍偏小 ⇒ FAIL（真少实现）
* 正例：后缀剥离覆盖 `.constprop.N/.isra.N/.part.N/.cold/.clone.N/.lto_priv.N/.llvm.N`
* 反例：`.word` 必须从工厂指令数里扣除（池不是代码）

用法
----
    python tools/equiv_group_sum.py                 # 只报 skew >= 1.6 的组
    python tools/equiv_group_sum.py --all           # 全量
    python tools/equiv_group_sum.py --names popwindows,ReadUSBJoy
    python tools/equiv_group_sum.py --self-test
"""
import argparse
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAC_JSON = os.path.join(ROOT, 'golden', 'factory.funcs.json')
FAC_GZ = FAC_JSON + '.gz'
OURS = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

CLONE_SUFFIX = ('.constprop.', '.isra.', '.part.', '.cold', '.clone.', '.lto_priv.', '.llvm.')
WARN, FAIL = 1.6, 2.5


def norm_name(n):
    for s in CLONE_SUFFIX:
        i = n.find(s)
        if i > 0:
            return n[:i]
    return n


def factory_group_sums(path=None):
    """{归一化名: {'sum': 纯指令字节, 'clones': [(原名, 字节)]}}"""
    p = path or (FAC_JSON if os.path.exists(FAC_JSON) else FAC_GZ)
    if p.endswith('.gz'):
        import gzip
        d = json.load(gzip.open(p, 'rt', encoding='utf-8'))
    else:
        d = json.load(open(p, encoding='utf-8'))
    funcs = d['functions'] if isinstance(d, dict) and 'functions' in d else d
    out = {}
    for name, v in funcs.items():
        n = v.get('n') or len(v.get('t2') or []) or len(v.get('t1') or []) or 0
        t1 = v.get('t1') or []
        n_pool = sum(1 for x in t1 if isinstance(x, str) and x.startswith('.word'))
        code = (n - n_pool) if t1 else n
        g = out.setdefault(norm_name(name), {'sum': 0, 'clones': []})
        g['sum'] += code * 4
        g['clones'].append((name, code * 4))
    return out


# ---------------------------------------------------------------- 我方 ELF
def ours_group_sums(path=None):
    """{归一化名: {'sum': 符号 size 之和, 'clones': [(原名, size)]}} —— 只取 type=FUNC。"""
    p = path or OURS
    b = open(p, 'rb').read()
    e_shoff, = struct.unpack_from('<I', b, 0x20)
    ents, shn, shx = struct.unpack_from('<HHH', b, 0x2e)
    sh = [struct.unpack_from('<10I', b, e_shoff + i * ents) for i in range(shn)]
    st = sh[shx]
    names = []
    for s in sh:
        t = b[st[4] + s[0]:]
        names.append(t[:t.index(b'\x00')].decode('ascii', 'replace'))
    if '.symtab' not in names or '.strtab' not in names:
        return {}
    S, T = names.index('.symtab'), names.index('.strtab')
    tb = b[sh[T][4]:sh[T][4] + sh[T][5]]
    out = {}
    for i in range(sh[S][5] // 16):
        o = sh[S][4] + i * 16
        no, va, sz, info, oth, shnd = struct.unpack_from('<IIIBBH', b, o)
        if not no or shnd == 0:
            continue
        if (info & 0xF) != 2:               # 只要 FUNC
            continue
        nm = tb[no:tb.index(b'\x00', no)].decode('ascii', 'replace')
        if not sz:
            continue
        g = out.setdefault(norm_name(nm), {'sum': 0, 'clones': []})
        g['sum'] += sz
        g['clones'].append((nm, sz))
    return out


def compare(fac, ours, names=None, show_all=False):
    rows = []
    keys = sorted(set(fac) | set(ours))
    for k in keys:
        if names and k not in names:
            continue
        f = fac.get(k)
        r = ours.get(k)
        if not f or not r:
            rows.append((k, 'MISSING', (f or {}).get('sum'), (r or {}).get('sum'),
                         'factory' if not f else 'rebuilt', f, r))
            continue
        ratio = r['sum'] / float(f['sum']) if f['sum'] else 1e9
        skew = max(ratio, 1.0 / ratio) if ratio > 0 else 1e9
        st = 'FAIL' if skew >= FAIL else ('WARN' if skew >= WARN else 'OK')
        if show_all or st != 'OK':
            rows.append((k, st, f['sum'], r['sum'], '%.3f' % ratio, f, r))
    return rows


def report(rows):
    print('=' * 104)
    print('归一化函数组「求和后」体量对拍（修 prop_equiv 的单代表口径）')
    print('=' * 104)
    print('  %-38s %-7s %9s %9s %8s' % ('组', '判定', 'Σ工厂', 'Σ我们', 'ratio'))
    for k, st, fs, rs, ratio, f, r in rows:
        print('  %-38s %-7s %9s %9s %8s' % (k, st, fs, rs, ratio))
        for nm, sz in (f or {}).get('clones', []):
            print('        F %-34s %7d' % (nm, sz))
        for nm, sz in (r or {}).get('clones', []):
            print('        R %-34s %7d' % (nm, sz))
    print()
    print('  共 %d 个组偏离 ≥%.1f' % (len(rows), WARN))
    print('  ★ 读法：「两侧组和接近」= 编译器分段（口径伪影，非缺陷）；')
    print('     「我们组和仍显著偏小」= 真的少实现，必须补代码。')
    return rows


def self_test():
    print('=' * 96)
    print('自证：先用已知答案的样本验仪器')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-58s got=%-14s %s' % (tag, got, '✓' if good else '★ FAIL'))

    # 后缀剥离
    for raw, want in [('foo.constprop.22', 'foo'), ('foo.isra.19', 'foo'),
                      ('foo.part.0', 'foo'), ('foo.cold', 'foo'),
                      ('foo.clone.3', 'foo'), ('foo.lto_priv.1', 'foo'),
                      ('foo.llvm.123', 'foo'), ('foo', 'foo')]:
        chk('norm_name(%s)' % raw, norm_name(raw), want)

    fac = {'foo': {'sum': 100, 'clones': [('foo', 100)]}}
    # 正例：我们也拆了两块，组和相等
    ours = {'foo': {'sum': 100, 'clones': [('foo', 60), ('foo.part.0', 40)]}}
    rows = compare(fac, ours)
    chk('正例  组和相等 → 无偏离项', len(rows), 0)

    # 反例：我们只实现了一块 ⇒ 仍偏小 ⇒ 必须报 FAIL
    #   ★ 注意选值：仪器阈值 WARN=1.6 / FAIL=2.5，而 skew 是对称的 max(r, 1/r)。
    #     60/100 ⇒ skew=1.667 ⇒ **WARN**（不是 FAIL）；要落 FAIL 必须 ≤ 40/100。
    ours2 = {'foo': {'sum': 40, 'clones': [('foo', 40)]}}
    rows2 = compare(fac, ours2)
    chk('反例  我们组和偏小一半以上 → 报 FAIL', rows2[0][1] if rows2 else None, 'FAIL')

    # 边界：恰好 60/100 必须落 WARN，不能被当成 FAIL（阈值口径自证）
    ours2b = {'foo': {'sum': 60, 'clones': [('foo', 60)]}}
    rows2b = compare(fac, ours2b)
    chk('边界  60/100 → 报 WARN', rows2b[0][1] if rows2b else None, 'WARN')

    # 反例：.word 必须扣除
    fn, t1 = 10, ['a', 'b', '.word x', '.word y']
    n_pool = sum(1 for x in t1 if isinstance(x, str) and x.startswith('.word'))
    chk('反例  .word 从工厂指令数扣除', (fn - n_pool) * 4, 32)

    # 正例：MISSING 分类
    rows3 = compare({'bar': {'sum': 10, 'clones': [('bar', 10)]}}, {})
    chk('正例  我方缺 → MISSING', rows3[0][1] if rows3 else None, 'MISSING')

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--names', help='只比这些组（逗号分隔）')
    a = ap.parse_args()
    if a.self_test:
        return 0 if self_test() else 2
    names = set(x.strip() for x in a.names.split(',')) if a.names else None
    fac = factory_group_sums()
    ours = ours_group_sums()
    print('  工厂组 %d 个 / 我们组 %d 个（工厂函数 %d 个）'
          % (len(fac), len(ours), sum(len(v['clones']) for v in fac.values())))
    rows = compare(fac, ours, names, a.all)
    report(rows)
    return 2 if any(r[1] == 'FAIL' for r in rows) else 0


if __name__ == '__main__':
    sys.exit(main())
