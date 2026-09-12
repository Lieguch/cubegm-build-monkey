#!/usr/bin/env python3
"""
gen_factory_globals.py — 从工厂二进制符号表提取**权威全局布局**账本。

输入：`01-static/symtab.txt`（`nm -S` 风格，含 地址 / 绑定 / 类型 / 段 / 尺寸 / 名字）
输出：`ledger/factory_globals.tsv`（与 `ledger/factory_globals_report.txt`）

用途（P3 链接的数据段供应）：
  - 重建只产出**函数**，全局变量（.data/.rodata/.bss）需按工厂布局精确重建；
  - 本账本给出每个符号的权威 addr/size/section，且**识别别名关系**
    （小符号若落在更大符号的地址区间内，则它是该大对象的字段，必须以 alias 方式定义，
     否则链接期各占一份空间 → 破坏原厂内存布局与烧死在指令里的绝对地址）。

输出列（TAB）：
  name  addr  size  section  bind  type  parent
  其中 parent 非空 = 该符号是 parent 的字段（alias），不得独立分配空间。

用法:
  python3 tools/gen_factory_globals.py <symtab.txt> [out.tsv]
"""
import os
import re
import sys

# nm -S 行：地址(8) SP 绑定(1) SP 类型(1) SP 段名 TAB 尺寸(8) 空格... 名字
RE_OBJ = re.compile(
    r'^([0-9a-f]{8})\s+([a-zA-Z ])\s*([a-zA-Z?])\s+(\S+)\s*\t([0-9a-f]{8})\s+(\S+)\s*$')
SEC_KEEP = ('.data', '.bss', '.rodata', '.data.rel.ro', '.init_array', '.fini_array')


def parse(path):
    rows = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = RE_OBJ.match(line.rstrip('\n'))
        if not m:
            continue
        addr, bind, typ, sec, size, name = m.groups()
        if sec not in SEC_KEEP:
            continue
        if typ not in ('O', 'o', 'R', 'r', 'B', 'b', 'D', 'd', 'V', 'v'):
            continue
        rows.append(dict(name=name, addr=int(addr, 16), size=int(size, 16),
                         section=sec, bind=bind, type=typ))
    return rows


def assign_parents(rows):
    """按地址升序扫描，把落在更大符号区间内的小符号标记为该大符号的字段(alias)。"""
    rs = sorted(rows, key=lambda r: (r['addr'], -r['size']))
    placed = []          # 已确定为「独立对象」的 (addr, end, name)
    for r in rs:
        parent = None
        for (a, e, n) in placed:
            if a < r['addr'] < e and r['addr'] + max(r['size'], 1) <= e:
                parent = n
                break
        r['parent'] = parent or ''
        if not parent and r['size'] > 0:
            placed.append((r['addr'], r['addr'] + r['size'], r['name']))
    return rows


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    src = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'ledger', 'factory_globals.tsv')
    rows = assign_parents(parse(src))
    rows.sort(key=lambda r: r['addr'])

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('name\taddr\tsize\tsection\tbind\ttype\tparent\n')
        for r in rows:
            f.write('%s\t%08x\t%08x\t%s\t%s\t%s\t%s\n' % (
                r['name'], r['addr'], r['size'], r['section'],
                r['bind'], r['type'], r['parent']))

    secs = {}
    for r in rows:
        d = secs.setdefault(r['section'], [0, 0, 0])
        d[0] += 1
        d[1] += r['size']
        if not r['parent']:
            d[2] += 1
    aliases = [r for r in rows if r['parent']]

    L = []
    A = L.append
    A('=' * 66)
    A('工厂权威全局布局账本（来源：%s）' % os.path.basename(src))
    A('=' * 66)
    A('数据类符号总数 : %d' % len(rows))
    A('独立对象数     : %d' % (len(rows) - len(aliases)))
    A('别名字段数     : %d   ← 落在更大对象区间内，定义时必须 alias' % len(aliases))
    A('')
    A('%-14s %8s %10s %10s' % ('section', 'count', 'bytes', 'independent'))
    for s, (c, b, ind) in sorted(secs.items()):
        A('%-14s %8d %10d %10d' % (s, c, b, ind))
    A('')
    A('--- 别名样例（前 40，显示 字段 -> 父对象）---')
    for r in aliases[:40]:
        A('  %-24s @%08x size=%-6d -> %s' % (r['name'], r['addr'], r['size'], r['parent']))
    if len(aliases) > 40:
        A('  ... 共 %d 条' % len(aliases))
    A('')
    A('--- 最大独立对象（前 20）---')
    ind = [r for r in rows if not r['parent']]
    for r in sorted(ind, key=lambda x: -x['size'])[:20]:
        A('  %-24s @%08x size=%-8d %s' % (r['name'], r['addr'], r['size'], r['section']))
    txt = '\n'.join(L) + '\n'
    sys.stdout.write(txt)
    rep = out.replace('.tsv', '_report.txt')
    open(rep, 'w', encoding='utf-8').write(txt)
    sys.stderr.write('ledger -> %s\nreport -> %s\n' % (out, rep))
    return 0


if __name__ == '__main__':
    sys.exit(main())
