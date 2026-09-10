#!/usr/bin/env python3
"""
inject_includes.py — 给 Ghidra 函数文件注入标准 include 块。

根因：Ghidra 导出的函数 .c **没有任何 #include**，导致 undefined4/FILE 等类型未定义。
      （首轮 CI 实测：213 个文件中仅 24 个可编译，主因即此。）

做法：在文件开头的 Ghidra 注释块之后插入
        #include "ghidra_compat.h"
        #include "globals.h"
        #include "proto.h"
      幂等：已注入则跳过。
"""
import os, re

ROOT = r'D:/output/rkgame-1to1/src/proprietary'
MARK = '#include "ghidra_compat.h"'
BLOCK = ('/* ---- 重建注入：Ghidra 函数文件本身无 include ---- */\n'
         '#include "ghidra_compat.h"\n'
         '#include "globals.h"\n'
         '#include "proto.h"\n')

n_add = n_skip = 0
for dp, dn, fn in os.walk(ROOT):
    for f in fn:
        if not f.endswith('.c'):
            continue
        p = os.path.join(dp, f)
        t = open(p, encoding='utf-8', errors='replace').read()
        if MARK in t:
            n_skip += 1
            continue
        # 现有注释块（/* ... */）之后插入，保持原注释在最上方
        m = re.match(r'\s*(/\*.*?\*/)\s*', t, re.S)
        if m:
            new = m.group(1) + '\n\n' + BLOCK + '\n' + t[m.end():]
        else:
            new = BLOCK + '\n' + t
        open(p, 'w', encoding='utf-8').write(new)
        n_add += 1

print('injected: %d files, skipped(already): %d' % (n_add, n_skip))
