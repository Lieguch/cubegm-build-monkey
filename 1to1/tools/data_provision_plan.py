#!/usr/bin/env python3
"""
data_provision_plan.py — P3 数据段供应缺口分析。

背景：重建只产出**函数**。函数引用的全局（.data/.bss/.rodata）必须在链接期按工厂
内存布局精确供应，否则烧死在指令里的绝对地址（如 `(int *)0x3afc44`）会失效。

关键事实：Ghidra 的 `DAT_003af268` 这类名字**不是工厂符号**——工厂真符号可能是
`m_ui`（size 0x5e4，覆盖 0x3af264..0x3af848）。因此：
  - `DAT_x` 落在某个工厂对象区间内 ⇒ 它是该对象的**字段**，必须以 alias 定义（不另占空间）；
  - `DAT_x` 不在任何工厂对象内 ⇒ 未命名区域，需按 .data/.bss 镜像单独供应。

输入：
  1) link_audit 报告（取 MISSING 列表）   2) ledger/factory_globals.tsv（权威布局）
输出：
  report/data_provision_plan.txt（分类统计 + 明细）

用法:
  python3 tools/data_provision_plan.py <link_audit.txt> <factory_globals.tsv>
"""
import os
import re
import sys
from collections import defaultdict

RE_DAT = re.compile(r'^DAT_([0-9a-fA-F]{6,8})$')
RE_MISSING_HDR = '【3】MISSING 明细'


def load_ledger(p):
    objs = []
    for i, line in enumerate(open(p, encoding='utf-8')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 7:
            continue
        objs.append(dict(name=f[0], addr=int(f[1], 16), size=int(f[2], 16),
                         section=f[3], bind=f[4], type=f[5]))
    objs.sort(key=lambda r: r['addr'])
    return objs


def load_missing(p):
    """优先读机器可读清单（_link_missing.txt，TAB 分隔 kind<TAB>name）；
    否则从审计报告正文的「【3】MISSING 明细」段解析。"""
    if p.endswith('_link_missing.txt') or os.path.basename(p) == '_link_missing.txt':
        out = []
        for line in open(p, encoding='utf-8', errors='replace'):
            f = line.rstrip('\n').split('\t')
            if len(f) >= 2 and f[0] == 'MISSING':
                out.append(f[1])
        return out
    out, on = [], False
    for line in open(p, encoding='utf-8', errors='replace'):
        if line.startswith(RE_MISSING_HDR):
            on = True
            continue
        if on:
            s = line.strip()
            if not s:
                break
            if s.startswith('【') or s.startswith('===='):
                break
            if s.startswith('...'):
                break
            out.append(s)
    return out


def find_container(objs, addr):
    lo, hi = 0, len(objs) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        o = objs[mid]
        if o['addr'] <= addr:
            if o['addr'] < addr < o['addr'] + o['size']:
                best = o
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    audit, ledger = sys.argv[1], sys.argv[2]
    objs = load_ledger(ledger)
    byname = {o['name']: o for o in objs}
    missing = load_missing(audit)

    exact, field, orphan, unknown = [], [], [], []
    for m in missing:
        if m in byname:
            exact.append((m, byname[m]))
            continue
        md = RE_DAT.match(m)
        if md:
            addr = int(md.group(1), 16)
            c = find_container(objs, addr)
            if c:
                field.append((m, addr, c))
            else:
                orphan.append((m, addr))
        else:
            unknown.append(m)

    L = []
    A = L.append
    A('=' * 70)
    A('P3 数据段供应缺口分析')
    A('=' * 70)
    A('MISSING 符号总数   : %d' % len(missing))
    A('工厂权威数据对象数 : %d' % len(objs))
    A('')
    A('【A】与工厂符号**同名** → 按工厂 size/section 直接定义        : %d' % len(exact))
    A('【B】Ghidra `DAT_x` 落在工厂对象区间内 → 必须定义为其字段(alias) : %d' % len(field))
    A('【C】Ghidra `DAT_x` 不在任何工厂对象内 → 未命名区域，需镜像供应  : %d' % len(orphan))
    A('【D】其它命名（非 DAT_x 且不在工厂符号表）→ 待定性            : %d' % len(unknown))
    A('')

    A('--- A 明细（同名，直接供应；前 40）---')
    for m, o in exact[:40]:
        A('  %-24s @%08x size=%-8d %s' % (m, o['addr'], o['size'], o['section']))
    if len(exact) > 40:
        A('  ... 共 %d' % len(exact))
    A('')

    grp = defaultdict(list)
    for m, addr, c in field:
        grp[c['name']].append((m, addr - c['addr']))
    A('--- B 明细（按父对象聚合；这些字段不占独立空间）---')
    for name, items in sorted(grp.items(), key=lambda kv: -len(kv[1]))[:30]:
        o = byname[name]
        A('  父对象 %-22s @%08x size=%-7d 字段数 %d  偏移样本 %s' % (
            name, o['addr'], o['size'], len(items),
            ', '.join('+0x%x' % off for _, off in sorted(items, key=lambda x: x[1])[:6])))
    A('')
    A('--- C 明细（未命名区域；前 60）---')
    for m, addr in orphan[:60]:
        A('  %-24s @%08x' % (m, addr))
    if len(orphan) > 60:
        A('  ... 共 %d' % len(orphan))
    A('')
    A('--- D 明细 ---')
    for m in unknown[:60]:
        A('  %s' % m)
    if len(unknown) > 60:
        A('  ... 共 %d' % len(unknown))

    txt = '\n'.join(L) + '\n'
    sys.stdout.write(txt)
    rep = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'report', 'data_provision_plan.txt')
    os.makedirs(os.path.dirname(rep), exist_ok=True)
    open(rep, 'w', encoding='utf-8').write(txt)
    sys.stderr.write('report -> %s\n' % rep)
    return 0


if __name__ == '__main__':
    sys.exit(main())
