#!/usr/bin/env python3
"""
find_undeclared.py — 取证：专有函数文件里**调用了但未声明**的标识符清单。

不猜：纯静态比对
  集合 A = 每个 .c 里形如 "ident(" 的调用目标
  集合 B = 已声明集合（proto.h 的 extern 函数名 + globals.h 的变量名 + libc/关键字白名单）
给出 A - B，即隐式声明/未声明调用 -> 这正是 `void value not ignored` 类错误的来源。

用法: python tools/find_undeclared.py [--top N]
"""
import re, os, glob, sys, collections

ROOT = r'D:/output/rkgame-1to1'
PROTO = os.path.join(ROOT, 'src/compat/proto.h')
GLOB = os.path.join(ROOT, 'src/compat/globals.h')
SRC = os.path.join(ROOT, 'src/proprietary')

# C 关键字 / 控制流 / 运算符（不是函数调用）
KEYWORDS = {
    'if', 'while', 'for', 'switch', 'return', 'sizeof', 'do', 'else', 'case', 'break',
    'continue', 'goto', 'default', 'void', 'int', 'char', 'long', 'short', 'unsigned',
    'signed', 'float', 'double', 'const', 'struct', 'union', 'enum', 'typedef', 'extern',
    'static', 'inline', 'volatile', 'defined',
}


def declared_names():
    names = set()
    for p in (PROTO, GLOB):
        if not os.path.exists(p):
            continue
        t = open(p, encoding='utf-8', errors='replace').read()
        t = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
        for m in re.finditer(r'extern\s+[\w\s\*]+?\s+\*?(\w+)\s*[\(\[]', t):
            names.add(m.group(1))
    return names


declared = declared_names()
print('已声明（proto.h + globals.h）: %d 个' % len(declared))

# 调用点：ident 直接后跟 '('
CALL = re.compile(r'\b([A-Za-z_]\w*)\s*\(')
undeclared = collections.Counter()
per_file = {}
for p in glob.glob(os.path.join(SRC, '*', '*.c')):
    t = open(p, encoding='utf-8', errors='replace').read()
    # 去掉注释与字符串
    t = re.sub(r'/\*.*?\*/', ' ', t, flags=re.S)
    t = re.sub(r'//[^\n]*', ' ', t)
    t = re.sub(r'"(?:[^"\\]|\\.)*"', '""', t)
    t = re.sub(r"'(?:[^'\\]|\\.)*'", "''", t)
    # 去掉函数自己的定义名（紧跟换行后跟 {）
    misses = set()
    for m in CALL.finditer(t):
        name = m.group(1)
        if name in KEYWORDS or name in declared:
            continue
        if name.startswith(('gh_', '__builtin', '__asm')):
            continue
        misses.add(name)
    if misses:
        per_file[os.path.basename(p)] = misses
        for x in misses:
            undeclared[x] += 1

print('存在未声明调用的文件: %d / %d' % (len(per_file), len(glob.glob(os.path.join(SRC, '*', '*.c')))))
print('未声明调用目标（唯一）: %d 个' % len(undeclared))
n = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 40
print()
print('--- 未声明目标 Top%d（按被多少文件调用）---' % n)
for name, c in undeclared.most_common(n):
    print('  %-36s %3d 个文件' % (name, c))
