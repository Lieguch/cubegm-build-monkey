#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按「编译单元(TU)」判定重名符号归属 —— P3 二期④。

原理（严格遵循 C 语义）
----------------------
工厂里同名符号可能有两份：
  · 一份是某 TU 的 **static**（`l` 绑定，只在本 TU 内可见）
  · 另一份是 **全局**（`g` 绑定，经 GOT 访问）

因此对任一函数 F：
  · 若 F 与 static 定义**同 TU** → F 引用的是 static；
  · 否则 F 只能引用全局那份（或根本不用）。

判定 F 属于哪个 TU：统计 F 引用到的 `l` 绑定符号，多数票即其 TU。
（Ghidra 导出的 function size 常越过下一函数，故边界取「下一函数入口」。）

输入
----
  report/xref.json        —— xref_scan.py 产出（函数 → direct/got 引用）
  <symtab.txt>            —— 工厂符号表（含 STT_FILE、绑定）

产出
----
  report/dup_assign.tsv   —— 函数 → TU → 每个重名符号的采用地址
"""
import json
import os
import re
import sys
import collections

ROW = re.compile(r'^([0-9a-fA-F]{8})\s+(\S+)\s+(\S+)\s+(\S+)\s+([0-9a-fA-F]{8})\s+(.*)$')

# 重名符号：name -> {static_addr, static_tu, global_addr(可空)}
DUPES = {
    'handle':      dict(statics={0x3b21c8: 'os_windows_rk.c',
                                 0x3cf988: 'EmuRun.c'},
                        global_=None),
    'diff_prev':   dict(statics={0x3bc414: 'ui_jkt.c'},
                        global_=0x3e1a38),
    'SoundBuffer': dict(statics={0x3ceaf0: 'ui_jkt.c'},
                        global_=0x3e1944),
    'ArchivePath': dict(statics={0x3ae610: 'ui_jkt.c'},
                        global_=0x3e18d4),
}


def parse_symtab(path):
    """→ (sym2tu, tu_of_addr)  sym2tu: (name,addr) -> TU"""
    tu = '(none)'
    sym2tu = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        m = ROW.match(line.rstrip('\n'))
        if not m:
            continue
        addr, bind, typ, sec, size, name = m.groups()
        name = name.strip()
        if typ == 'df':
            if name:
                tu = name
            continue
        if bind == 'l' and typ == 'O':
            sym2tu[(name, int(addr, 16))] = tu
    return sym2tu


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    symtab = sys.argv[1] if len(sys.argv) > 1 else \
        'D:/output/rkgame/decompiled/01-static/symtab.txt'
    xref = json.load(open(os.path.join(root, 'report', 'xref.json'),
                          encoding='utf-8'))
    sym2tu = parse_symtab(symtab)

    # 收集每个函数引用到的 `l` 符号及重名符号
    rows = []
    tu_votes = collections.defaultdict(collections.Counter)
    ref_of = {}
    for fa, info in xref.items():
        a = int(fa, 16)
        votes = collections.Counter()
        for d in info['direct'].values():
            for nm in d['names']:
                t = sym2tu.get((nm, d['addr']))
                if t:
                    votes[t] += 1
        for d in info['got'].values():          # GOT 目标也可能有 l 绑定别名
            for nm in d['names']:
                t = sym2tu.get((nm, d['addr']))
                if t:
                    votes[t] += 1
        # 重名符号引用（direct / got）
        found = {}
        for d in info['direct'].values():
            for nm, cfg in DUPES.items():
                if d['addr'] in cfg['statics']:
                    found[nm] = ('static', d['addr'])
        for d in info['got'].values():
            for nm, cfg in DUPES.items():
                if cfg['global_'] is not None and d['addr'] == cfg['global_']:
                    found[nm] = ('global', d['addr'])
        tu_votes[a] = votes
        ref_of[a] = (info['name'], found)

    def pick_tu(a, exclude=()):
        """多数票 TU；同票时取「引用点数」加权后的首个。"""
        c = tu_votes.get(a)
        if not c:
            return None
        for t, _ in c.most_common():
            if t not in exclude:
                return t
        return None

    for a in sorted(ref_of):
        name, found = ref_of[a]
        tu = pick_tu(a)
        votes = tu_votes.get(a) or collections.Counter()
        decide = {}
        for nm, cfg in DUPES.items():
            if nm in found:
                decide[nm] = found[nm]
                continue
            # 无直接证据 → 用 TU 判定
            if tu in cfg['statics'].values():
                addr = [k for k, v in cfg['statics'].items() if v == tu][0]
                decide[nm] = ('static(TU)', addr)
            elif cfg['global_'] is not None:
                decide[nm] = ('global(TU)', cfg['global_'])
            else:
                decide[nm] = ('unused', None)
        rows.append(dict(addr=a, name=name, tu=tu or '?',
                         votes=dict(votes.most_common(3)), decide=decide))

    out = os.path.join(root, 'report', 'dup_assign.tsv')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# func_addr\tfunc\tTU\t重名符号采用(证据/TU 推定)\n')
        for r in rows:
            ds = '; '.join('%s=%s@%s' % (k, v[0], ('0x%08x' % v[1]) if v[1] else '-')
                           for k, v in r['decide'].items() if k in
                           ('handle', 'diff_prev', 'SoundBuffer', 'ArchivePath'))
            if ds:
                f.write('0x%08x\t%s\t%s\t%s\n' % (r['addr'], r['name'], r['tu'], ds))

    # ---- 汇总 ----
    print('函数总数 : %d' % len(rows))
    tuc = collections.Counter(r['tu'] for r in rows)
    print('可判 TU  : %d' % sum(1 for r in rows if r['tu'] != '?'))
    print()
    print('%-14s %-18s %s' % ('符号', '决策', '函数'))
    for nm in ('handle', 'diff_prev', 'SoundBuffer', 'ArchivePath'):
        for kind in ('static', 'static(TU)', 'global', 'global(TU)', 'unused'):
            fs = [r['name'] for r in rows if r['decide'].get(nm, (None,))[0] == kind]
            if fs:
                print('%-14s %-18s %d 个: %s' % (nm, kind, len(fs), ', '.join(fs[:6]) +
                                                 ('…' if len(fs) > 6 else '')))
    # 需要拆分（同符号出现两种决策）的符号
    print()
    print('=== 需拆分 ===')
    for nm in DUPES:
        kinds = set(r['decide'].get(nm, (None,))[0] for r in rows)
        kinds.discard(None)
        kinds.discard('unused')
        if len(kinds) > 1:
            print('  %s : %s' % (nm, sorted(kinds)))
    others = [r['decide'][nm][0] for r in rows for nm in DUPES
              if r['decide'].get(nm, (None,))[0] in ('static(TU)', 'global(TU)')]
    print()
    print('★ 依赖 TU 推定（无直接指令证据）的判定数 : %d' % len(others))
    print('详细 → report/dup_assign.tsv')


if __name__ == '__main__':
    main()
