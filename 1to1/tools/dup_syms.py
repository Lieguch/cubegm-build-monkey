#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从工厂 symtab 解析「同名重复符号 → 归属编译单元(TU)」映射。

背景：工厂里存在同名但分属不同 TU 的符号（static 局部符号，或 TU 内全局）。
我们的别名生成器按名字去重 → 只保留一份 ⇒ 布局门禁出现全局偏差、且语义可能错。
本工具给出「名字 → [(addr, size, bind, TU), ...]」的权威映射，用于按 TU 拆分。
"""
import re, sys, collections, json, os

ROW = re.compile(r'^([0-9a-fA-F]{8})\s+(\S+)\s+(\S+)\s+(\S+)\s+([0-9a-fA-F]{8})\s+(.*)$')


def parse(path):
    tu = '(none)'
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        m = ROW.match(line)
        if not m:
            continue
        addr, bind, typ, sec, size, name = m.groups()
        name = name.strip()
        # STT_FILE: bind='l' type='df' section '*ABS*'
        if typ == 'df':
            if name:
                tu = name
            continue
        out.append(dict(addr=int(addr, 16), bind=bind, typ=typ, sec=sec,
                        size=int(size, 16), name=name, tu=tu))
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else \
        'D:/output/rkgame/decompiled/01-static/symtab.txt'
    syms = parse(path)
    print('符号条目 : %d' % len(syms))

    tus = collections.Counter(s['tu'] for s in syms)
    print('编译单元 : %d' % len(tus))
    print()

    # 只看有尺寸的数据对象（O/*）与函数（F）
    objs = [s for s in syms if s['size'] > 0 and s['typ'] in ('O', 'F')]
    g = collections.defaultdict(list)
    for s in objs:
        g[s['name']].append(s)

    dups = {k: v for k, v in g.items() if len(v) > 1}
    print('有尺寸对象 : %d ；重名组 : %d' % (len(objs), len(dups)))

    # 重名中「跨 TU」才是真冲突；同 TU 内重名=异常
    cross = {k: v for k, v in dups.items() if len(set(x['tu'] for x in v)) > 1}
    print('跨 TU 重名组 : %d' % len(cross))
    print()

    rows = []
    for name in sorted(cross):
        v = sorted(cross[name], key=lambda x: x['addr'])
        addrset = set(x['addr'] for x in v)
        rows.append(dict(name=name, n=len(v), distinct_addr=len(addrset),
                         items=[dict(addr=x['addr'], size=x['size'], bind=x['bind'],
                                     sec=x['sec'], tu=x['tu']) for x in v]))

    # 统计：哪些重名同时存在 g 绑定（外部可见）
    with_g = [r for r in rows if any(i['bind'] == 'g' for i in r['items'])]
    print('跨 TU 重名且含全局(g)绑定 : %d' % len(with_g))
    print()

    print('%-28s %3s %6s  %s' % ('name', 'n', 'distinct', '归属(TU@addr bind)'))
    for r in rows[:40]:
        desc = ' | '.join('%s@%08x %s' % (os.path.basename(i['tu']), i['addr'], i['bind'])
                          for i in r['items'])
        print('%-28s %3d %6d  %s' % (r['name'], r['n'], r['distinct_addr'], desc))
    if len(rows) > 40:
        print('... 共 %d 组，仅显示前 40' % len(rows))

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'report', 'dup_syms.json')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print()
    print('详细映射 → report/dup_syms.json')


if __name__ == '__main__':
    main()
