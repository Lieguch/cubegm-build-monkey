#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_blk12.py —— 验证某 TU 在 -Os 下是否把块读参数槽全部写入。

为什么需要它（R180 / GAP 18.02-18.04）
--------------------------------------
`dce_ref_diff.py` 的集合级 Δ 有盲区（GAP 18.01）：若某工厂符号在本 TU 别处仍被
引用，它的死写被 -Os 消除不会改变符号在场性 ⇒ Δ 为空、门禁放行。
R180 用它连抓 4 条漏网（DisplayThumbnail / SeletEmuCore / mui_recent / mui_shoucang）。

本工具用**不依赖符号集合**的判据，且**锚定实参基址**（不是简单数存储条数——
R180 实测：只数条数会把 mui_recent 误判为 OK，因为它函数前段恰好也存了 6 个槽）。

判据（机械、无推断）：
  1. 编译 -O0 / -Os 到 .s，切出目标函数体；
  2. 逐行扫描，维护 `寄存器 -> sp 偏移` 表（来自 `add rX, sp, #imm`），
     并**势精度地**跟踪 r0/r1 的最近一次设置（`add r0,sp,#imm` / `mov r0,rX`）；
     遇到**标签或分支**则视其失效（跨基本块的定义不能当本次实参——R180 实测踩过：
     mui_shoucang 的 `add r0,sp,#24` 距 `bl popwindows` 有 22 行，固定 12 行回看
     窗口既会漏掉合法调用点、也会把别的基本块的定义误当实参）；
  3. 遇到 `bl <块读函数>` 时取 r0（param_1，单组）或 r0+r1（param_1+param_2，两组）
     的基址，要求**每个基址起的 6 个 int 槽**都在"此前累计写过的栈槽集合"里。
     - blockcopy / blockadaptive / mui_blockcopy：两组各 6 int ⇒ 校验 r0 与 r1
       （两组在栈上相邻，但**不能**从 r0 起连数 12 槽——那样会把 param_2 的 6 槽
       算到 param_1 头上，把已修好的文件误报为死写，R180 实测踩过）。
     - popwindows / popoffwindows：一组 6 int ⇒ 只校验 r0。

用法：
    CC=arm-linux-gnueabihf-gcc python3 tools/verify_blk12.py <file.c> [fn]
"""
import os
import re
import subprocess
import sys

CC = os.environ.get('CC', 'arm-linux-gnueabihf-gcc')
INC = 'src/compat'
BLOCKREAD = ('blockcopy', 'blockadaptive', 'mui_blockcopy',
             'popwindows', 'popoffwindows')
CALL = re.compile(r'\bbl\s+(' + '|'.join(BLOCKREAD) + r')\b')
ADD = re.compile(r'\badd\s+(r\d+)\s*,\s*sp\s*,\s*#(-?\d+)')
STR = re.compile(r'\b(str\w*|stm\w*)\s+([^;]*?)\s*(?:;.*)?$')
SLOT = re.compile(r'\[(r\d+|sp|fp|r11|r13)(?:\s*,\s*#(-?\d+))?\]')
MOV_R0 = re.compile(r'\bmov\s+r0\s*,\s*(r\d+|sp|fp)\b')
MOV_R1 = re.compile(r'\bmov\s+r1\s*,\s*(r\d+|sp|fp)\b')
ADD_R0 = re.compile(r'\badd\s+r0\s*,\s*sp\s*,\s*#(-?\d+)')
ADD_R1 = re.compile(r'\badd\s+r1\s*,\s*sp\s*,\s*#(-?\d+)')

NEED = {'blockcopy': 12, 'blockadaptive': 12, 'mui_blockcopy': 12,
        'popwindows': 6, 'popoffwindows': 6}
GROUP = 6                  # 每组参数槽固定 6 个 int
BARRIER = re.compile(r'^\.?L?\w+:\s*$|\b(b|bne|beq|bgt|blt|bhi|bls|bx|cbz|cbnz)\b')


def compile_asm(path, opt):
    cmd = [CC, opt, '-S', '-w', '-I' + INC, '-march=armv7-a',
           '-mfloat-abi=hard', '-mfpu=neon', '-fno-pic',
           '-fno-stack-protector', path, '-o', '-']
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def fn_body(text, fn):
    m = re.search(r'^%s:\s*$' % re.escape(fn), text, re.M)
    if not m:
        return ''
    rest = text[m.end():]
    e = re.search(r'^\s*\.size\s+' + re.escape(fn) + r'\b', rest, re.M)
    return rest[:e.start()] if e else rest


def store_offsets(line, reg2sp):
    """返回该行所有写向栈的 4 字节槽偏移列表。"""
    ms = STR.match(line.strip())
    if not ms:
        return []
    mnem = ms.group(1)
    if not mnem.startswith('str') and not mnem.startswith('stm'):
        return []
    out = []
    for m in SLOT.finditer(ms.group(2)):
        base, disp = m.group(1), m.group(2)
        if base == 'sp':
            off = int(disp, 10) if disp else 0
        elif base in reg2sp:
            off = reg2sp[base] + (int(disp, 10) if disp else 0)
        else:
            continue
        if mnem.startswith('stm'):
            nreg = len(re.findall(r'r\d+', ms.group(2)))
            for k in range(min(nreg, 16)):
                out.append(off + 4 * k)
        elif mnem == 'strd':
            out.append(off)
            out.append(off + 4)
        else:
            out.append(off)
    return out


def analyse(path, fn):
    a = compile_asm(path, '-O0')
    b = compile_asm(path, '-Os')
    if a is None or b is None:
        print('  ★ 编译失败')
        return
    for tag, body in (('-O0', fn_body(a, fn)), ('-Os', fn_body(b, fn))):
        if not body:
            print('  ★ %s 函数体切分失败' % tag)
            continue
        lines = [l.rstrip() for l in body.splitlines() if l.strip()]
        reg2sp = {}
        cum = set()                 # 累计写过的栈槽（字节偏移）
        last = {'r0': None, 'r1': None}   # (行号, sp 偏移)，势精度
        print('  === %s ===' % tag)
        for idx, l in enumerate(lines, 1):
            ma = ADD.search(l)
            if ma:
                reg2sp[ma.group(1)] = int(ma.group(2), 10)
            # 记录 r0/r1 的最近设置（后出现者覆盖先出现者）
            for reg, add_re, mov_re in (('r0', ADD_R0, MOV_R0),
                                        ('r1', ADD_R1, MOV_R1)):
                m1 = add_re.search(l)
                if m1:
                    last[reg] = (idx, int(m1.group(1), 10))
                    continue
                m2 = mov_re.search(l)
                if m2:
                    src = m2.group(1)
                    if src in ('sp', 'fp'):
                        last[reg] = (idx, 0)
                    elif src in reg2sp:
                        last[reg] = (idx, reg2sp[src])
            # 标签 / 分支 / 调用之后的定义不能跨越到本行使用
            if BARRIER.search(l):
                for reg in ('r0', 'r1'):
                    if last[reg]:
                        last[reg] = None
            if CALL.search(l):
                sym = CALL.search(l).group(1)
                need = NEED.get(sym, 12)
                nbases = 2 if need == 12 else 1
                # r0 优先（param_1），r1 次之（param_2）
                order = ['r0', 'r1'] if last.get('r0') else ['r1', 'r0']
                bases = [(r, last[r][1]) for r in order if last.get(r)][:nbases]
                if not bases:
                    print('    调用 %-14s ★ 解析不到实参基址（需人工看汇编：'
                          'grep -B30 "bl %s"）' % (sym, sym))
                else:
                    bad = []
                    for reg, b in bases:
                        want = [b + 4 * k for k in range(GROUP)]
                        miss = [w for w in want if w not in cum]
                        if miss:
                            bad.append('%s=sp+%d 缺 %s'
                                       % (reg, b, ' '.join('sp+%d' % m for m in miss)))
                    if bad:
                        print('    调用 %-14s ★ 参数槽死写：%s' % (sym, ' ; '.join(bad)))
                    elif len(bases) < nbases:
                        print('    调用 %-14s ◆ 仅校验 %s（另一实参基址未解析到，'
                              '需人工补验）' % (sym, ','.join(r for r, _ in bases)))
                    else:
                        print('    调用 %-14s %s 各 %d 槽全写 OK'
                              % (sym, '+'.join('%s=sp+%d' % (r, b) for r, b in bases),
                                 GROUP))
                cum |= set(store_offsets(l, reg2sp))
                last = {'r0': None, 'r1': None}   # 调用破坏调用方寄存器
                continue
            cum |= set(store_offsets(l, reg2sp))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    path = sys.argv[1]
    fn = sys.argv[2] if len(sys.argv) > 2 else None
    if fn is None:
        m = re.match(r'FUN_[0-9a-f]+_([A-Za-z0-9_]+)\.c$', os.path.basename(path))
        fn = m.group(1) if m else os.path.basename(path)[:-2]
    print('%s   fn=%s' % (os.path.basename(path), fn))
    analyse(path, fn)
    return 0


if __name__ == '__main__':
    sys.exit(main())
