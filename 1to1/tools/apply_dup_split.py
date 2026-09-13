#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3 二期④：按「实测 TU 归属」拆分重名符号的源码引用。

决策来源（全部为二进制实测，非推测）
-----------------------------------
tools/xref_scan.py —— A32 PIC 指令级交叉引用（含 GOT 中介与「锚点+偏移」直访内存）
tools/dup_assign.py —— TU 多数票
报告：report/xref_dup.txt

| 名字       | 主名（globals.h 现有声明）      | 拆分别名             | 谁用哪个（实测） |
|-----------|-------------------------------|---------------------|-----------------|
| handle    | 0x3b21c8 os_windows_rk.c static | handle_emurun 0x3cf988 | 4 vs 17 |
| diff_prev | 0x3bc414 ui_jkt.c static        | diff_prev_global 0x3e1a38 | 15 static vs 4 经 GOT |

用法：
  python tools/apply_dup_split.py            # 预演（只报告）
  python tools/apply_dup_split.py --write    # 实际改写
"""
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'proprietary')

# 函数入口地址 → 归属（由 report/xref_dup.txt 实测得出）
HANDLE_EMURUN = {0x2b59bc, 0x2b5a4c, 0x2b5c08, 0x2b616c, 0x2b63c0, 0x2b6614,
                 0x2b6868, 0x2b6abc, 0x2b6c14, 0x2b6f58, 0x2b737c, 0x2b7a68,
                 0x2b7ccc, 0x2b7f30, 0x2b8194, 0x2b83e8, 0x2b8570}
HANDLE_OSWIN = {0xd628, 0xd678, 0xdae0, 0xdb08}
DIFF_PREV_GLOBAL = {0xb430, 0xb4b0, 0x2b4d64, 0x2b5c08}
DIFF_PREV_UIJKT = {0x19874, 0x21c08, 0x23204, 0x23e10, 0x25094, 0x277bc,
                   0x28a74, 0x2a00c, 0x2b2b4, 0x2d0d4, 0x2e040, 0x2eac8,
                   0x2f320, 0x2fe44, 0x2ff8c}

FN = re.compile(r'FUN_([0-9a-fA-F]{6,8})_')
RULES = [
    # (标识符, 目标地址集, 新名)
    ('handle',    HANDLE_EMURUN,     'handle_emurun'),
    ('diff_prev', DIFF_PREV_GLOBAL,  'diff_prev_global'),
]


def main():
    write = '--write' in sys.argv
    files = {}
    for p in glob.glob(os.path.join(SRC, '**', '*.c'), recursive=True):
        m = FN.search(os.path.basename(p))
        if not m:
            continue
        files[int(m.group(1), 16)] = p

    print('源文件数 : %d' % len(files))
    plan = []
    covered = set()
    for name, addrs, new in RULES:
        pat = re.compile(r'\b%s\b' % re.escape(name))
        for a in sorted(addrs):
            p = files.get(a)
            if not p or not os.path.exists(p):
                print('  !! 找不到函数 0x%x 的源文件' % a)
                continue
            t = open(p, encoding='utf-8').read()
            n = len(pat.findall(t))
            if n == 0:
                print('  !! %s 中未出现 %s' % (os.path.basename(p), name))
                continue
            covered.add((a, name))
            plan.append((p, name, new, n))

    print()
    print('=== 改写计划 ===')
    for p, name, new, n in plan:
        print('  %-58s %s -> %-18s x%d' %
              (os.path.basename(p), name, new, n))
    print()
    print('改写文件数 : %d ；替换次数 : %d' % (len(plan), sum(x[3] for x in plan)))

    # 反向核查：还有哪些文件引用了这两个名字但不在计划中（应只留主名那一份）
    print()
    print('=== 未纳入改写的引用者（应为「主名」使用者）===')
    for name in ('handle', 'diff_prev'):
        pat = re.compile(r'\b%s\b' % re.escape(name))
        left = []
        for a, p in sorted(files.items()):
            t = open(p, encoding='utf-8').read()
            if pat.search(t):
                left.append((a, os.path.basename(p)))
        print('  %s : %d 个' % (name, len(left)))
        for a, b in left:
            print('     0x%06x %s' % (a, b))

    if not write:
        print()
        print('（预演模式，未改写；加 --write 生效）')
        return 0

    for p, name, new, n in plan:
        t = open(p, encoding='utf-8').read()
        t2 = re.sub(r'\b%s\b' % re.escape(name), new, t)
        open(p, 'w', encoding='utf-8', newline='\n').write(t2)
    print()
    print('已改写 %d 个文件' % len(plan))
    return 0


if __name__ == '__main__':
    sys.exit(main())
