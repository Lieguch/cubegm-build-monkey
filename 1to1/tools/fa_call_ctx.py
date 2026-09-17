#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量取证：给定函数名列表，打印工厂侧每处调用点之前 5 条指令（用于人工定参）。

为什么需要：
  `tools/scan_kr_argcount.py` 只能报"我们比工厂少传了几个参数"，
  但**少传的那个参数到底应该是什么**，必须看工厂每个调用点的 r0..r3 是怎么摆的。
  本脚本把这步取证自动化：一次性把候选函数的调用上下文摊开，避免逐个反复敲 objdump。
"""
import os
import re
import subprocess
import sys

FA = 'golden/factory.rkgame.bin'
OBJ = os.environ.get('OBJDUMP', 'C:/objdump')
CACHE = 'build/_fa_dis_ctx.txt'

PAT_CALL = re.compile(r'^\s*([0-9a-f]+):\s+bl\s+([0-9a-f]+)\s*<([^>]*)>')
PAT_INS = re.compile(r'^\s*([0-9a-f]+):\s+(\S+)\s*(.*)$')


def symtab(elf):
    out = subprocess.run([OBJ, '-t', elf], capture_output=True, text=True).stdout
    m = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) == 6 and p[1] in 'glw' and p[2] == 'F':
            try:
                m[p[5]] = int(p[0], 16)
            except ValueError:
                pass
    return m


def load_dis():
    need = True
    if os.path.exists(CACHE) and os.path.getsize(CACHE) > 1_000_000:
        need = os.path.getmtime(CACHE) >= os.path.getmtime(FA)
    if need:
        os.makedirs('build', exist_ok=True)
        tmp = CACHE + '.tmp'
        for extra in ([], ['-m', 'arm']):
            with open(tmp, 'w', encoding='utf-8') as f:
                r = subprocess.run([OBJ, '-d', '--no-show-raw-insn'] + extra + [FA],
                                   stdout=f, stderr=subprocess.PIPE, text=True)
            if r.returncode == 0 and os.path.getsize(tmp) > 1_000_000:
                break
        os.replace(tmp, CACHE)
    return open(CACHE, encoding='utf-8', errors='replace').read().splitlines()


def main(names):
    sym = symtab(FA)
    lines = load_dis()
    idx = {}
    for i, l in enumerate(lines):
        m = PAT_CALL.match(l)
        if m:
            idx.setdefault(m.group(3), []).append(i)
    for n in names:
        sites = idx.get(n, [])
        print('=== %s   (工厂 %d 处调用, @0x%x)' % (n, len(sites), sym.get(n, 0)))
        for i in sites[:2]:
            print('   -- 调用点 %s' % lines[i].strip()[:64])
            for j in range(max(0, i - 5), i):
                m = PAT_INS.match(lines[j])
                if m:
                    print('        %s  %-6s %s' % (m.group(1), m.group(2), m.group(3)[:60]))
        print()


if __name__ == '__main__':
    main(sys.argv[1:])
