#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
group_arity_errors.py —— 把 report/arity_compile.txt 的错误**按被调函数分组**，并打印该函数的定义签名

为什么需要：清账要"按函数定案"，不能按文件逐个看。同一函数往往在多个文件里被同样地错用；
一次看清"这个函数的形参类型 vs 所有调用点传什么"，才能决定是改**定义类型**还是改**实参**。
"""
import io
import os
import re
import glob
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REP = os.path.join(ROOT, 'report/arity_compile.txt')


def defs():
    """{name: (path, signature)} —— 从源码定义里抓签名"""
    out = {}
    pat = re.compile(r'^\s*([A-Za-z_][\w \*]*?)\b(\w+)\s*\(([^)]*)\)\s*$', re.M)
    for path in glob.glob(os.path.join(ROOT, 'src/proprietary/**/*.c'), recursive=True):
        txt = io.open(path, encoding='utf-8', errors='replace').read()
        for m in pat.finditer(txt):
            ret, name, params = m.group(1).strip(), m.group(2), m.group(3).strip()
            if ret in ('return', 'else', 'case'):
                continue
            out.setdefault(name, (os.path.relpath(path, ROOT), '%s %s(%s)' % (ret, name, params)))
    return out


def main():
    txt = io.open(REP, encoding='utf-8', errors='replace').read().splitlines()
    cur_file = None
    groups = {}
    for i, ln in enumerate(txt):
        m = re.match(r'^===== (.+\.c)$', ln)
        if m:
            cur_file = m.group(1)
            continue
        if 'error:' not in ln:
            continue
        # 出错位置
        loc = re.match(r'^(D:[^\n:]+):(\d+):(\d+): error: (.*)$', ln)
        if not loc:
            continue
        path, line, col, msg = loc.group(1), int(loc.group(2)), int(loc.group(3)), loc.group(4)
        # 从源码同一行的调用里取被调函数名
        callee = '?'
        try:
            src = io.open(path, encoding='utf-8', errors='replace').read().splitlines()[line - 1]
            seg = src[max(0, col - 1):]
            mm = re.match(r'([A-Za-z_]\w*)\s*\(', seg) or re.search(r'([A-Za-z_]\w*)\s*\(', src)
            if mm:
                callee = mm.group(1)
        except Exception:
            pass
        if msg.startswith('conflicting types'):
            cm = re.search(r"conflicting types for '(\w+)'", msg)
            callee = cm.group(1) if cm else callee
        if msg.startswith('too few') or msg.startswith('too many') or msg.startswith('incompatible'):
            pass
        key = callee
        groups.setdefault(key, {'n': 0, 'kinds': {}, 'sites': []})
        groups[key]['n'] += 1
        kind = msg.split(' ')[0] if msg.startswith('conflicting') else ' '.join(msg.split(' ')[:3])
        groups[key]['kinds'][kind] = groups[key]['kinds'].get(kind, 0) + 1
        groups[key]['sites'].append('%s:%d' % (os.path.basename(path), line))
    d = defs()
    print('按被调函数分组（%d 个）：' % len(groups))
    print('%-28s %-4s %-46s %s' % ('callee', 'n', '定义签名', '错误种类'))
    for name, g in sorted(groups.items(), key=lambda kv: -kv[1]['n']):
        sig = d[name][1] if name in d else '(未找到定义)'
        print('%-28s %-4d %-46s %s' % (name[:28], g['n'], sig[:46], g['kinds']))
        print('     sites: %s' % ', '.join(g['sites'][:6]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
