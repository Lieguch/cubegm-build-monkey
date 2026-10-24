#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_callgraph_args.py —— **全量**审计"工厂调用点设了几个实参 vs 我方源码传了几个"

为什么要有这个工具（这是"大局观"那条要求的技术答案）
------------------------------------------------------------------
7 轮真机里反复出现**同一族**缺陷：重建源码把工厂的实参丢了。
    · sunxi_gpio_output  ×7 处（丢第二个实参 ⇒ 位带 SPI 电平随机 ⇒ RF 自检失败 ⇒ 无按键线程）
    · mui_DispBlock      ×3 处（丢块索引 ⇒ 画错块）
    · PlaySound          ×1 处（丢 buf/len ⇒ driver.so 收到垃圾指针 ⇒ 全程无声 + 按键后冻死）
根因有两层：① Ghidra 看不到寄存器被"用到"就不列形参；② `proto.h` 把这些函数声明成
**K&R 空参** `f()`，于是 **C 编译器完全不做实参个数检查**，缺陷静默通过。
一行一行凭"撞到再改"去补，就是穷举。正确的做法是**对整个调用图做一次机械对账**：

   工厂机器码 → 每个 `bl <callee>` 之前 r0..r3 被写了哪几个 → callee 的"实参下界"
   我方源码   → 同一 callee 的每个调用点实参个数
   不一致（工厂设了 rN，我方只传 N 个以下）⇒ 报告

输出：按"callee | 工厂实参下界 | 我方实参 | 判定"排序，只列可疑项。
局限（必须写清，避免又变成"绿了就当对"）：
   · 只覆盖**直接调用 `bl <sym>`**；间接调用（函数指针 / driver.so API）另列清单人工核对。
   · "工厂实参下界"是从寄存器写入推断的**下界**，可能低估（例如参数由更早的指令算好）。
     ⇒ 它**只用于发现"我方传得比工厂少"**，不用来断言"我方一定对"。
"""
import io
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIS = os.path.join(ROOT, 'build/_dis_factory.rkgame.bin.txt')

# objdump 行： "    d274:\tbl\tcaa4 <SPI_Read>"
RE_INSN = re.compile(r'^\s*([0-9a-f]{4,8}):\t([a-z][\w\.]*)\t?(.*)$')
RE_BL = re.compile(r'\b(?:bl|blx|b)\s+([0-9a-f]+)\s+<([^>]+)>')
RE_MOVI = re.compile(r'\bmovw?\s+(r[0-3])\s*,\s*#(-?\d+|0x[0-9a-f]+)')
RE_MOVR = re.compile(r'\bmovs?\s+(r[0-3])\s*,\s*(r\d+|sl|fp|ip)')
RE_LDRPC = re.compile(r'\bldr\s+(r[0-3])\s*,\s*\[pc')
RE_PUSH = re.compile(r'\b(?:push|pop)\b')
RE_STR_PC = re.compile(r'\bstr\s+(r[0-3])\s*,\s*\[sp')


def load_factory():
    """返回 {callee: {'maxreg': {site: n}, 'consts': {...}}}"""
    callees = defaultdict(lambda: {'sites': [], 'consts': defaultdict(set)})
    if not os.path.exists(DIS):
        raise SystemExit('缺少工厂反汇编：%s' % DIS)
    lines = io.open(DIS, encoding='utf-8', errors='replace').read().splitlines()
    hist = []          # 最近若干条指令文本（含寄存器写入）
    cur_fn = '?'
    for ln in lines:
        m = RE_INSN.match(ln)
        if not m:
            if ln and not ln.startswith(' ') and ln.endswith(':') and '<' in ln:
                cur_fn = ln.strip().rstrip(':')
                hist = []
            continue
        ins = m.group(3) or ''
        bl = RE_BL.search(ins)
        if bl:
            name = bl.group(2)
            # 往回 16 条内，找 r0..r3 的最后一次写入
            written = {}
            for back in reversed(hist[-16:]):
                for r, imm in RE_MOVI.findall(back):
                    written.setdefault(r, ('imm', imm))
                for r, src in RE_MOVR.findall(back):
                    written.setdefault(r, ('reg', src))
                for r in RE_LDRPC.findall(back):
                    written.setdefault(r, ('lit', ''))
                for r in RE_STR_PC.findall(back):
                    written.setdefault(r, ('stack', ''))
            if written:
                idx = max(int(r[1]) for r in written)
                callees[name]['sites'].append((cur_fn, idx, dict(written)))
                for r, (kind, v) in written.items():
                    if kind == 'imm':
                        callees[name]['consts'][r].add(v)
            hist = []
            continue
        if RE_PUSH.search(ins) or re.match(r'^\s*b\b', ins):
            hist = []
            continue
        hist.append(ins)
        if len(hist) > 40:
            hist.pop(0)
    return callees


def src_arity():
    """我方源码：每个函数的**定义形参个数**（K&R/空参 = 0）"""
    out = {}
    pat = re.compile(r'\b(\w+)\s*\(([^)]*)\)\s*\n\s*\{')
    for path in _src_files():
        txt = _strip(io.open(path, encoding='utf-8', errors='replace').read())
        for m in pat.finditer(txt):
            name, params = m.group(1), m.group(2).strip()
            if params in ('', 'void'):
                n = 0
            elif '...' in params:
                continue
            else:
                n = _count(params)
            out.setdefault(name, n)
    return out


def src_calls():
    """我方源码：每个调用点的实参个数（多次调用取**最大**，因为缺陷常是"某处少传"）"""
    out = defaultdict(int)
    site_lines = defaultdict(list)
    pat = re.compile(r'\b(\w+)\s*\(([^();]*)\)')
    for path in _src_files():
        raw = io.open(path, encoding='utf-8', errors='replace').read()
        txt = _strip(raw)
        for m in pat.finditer(txt):
            name, args = m.group(1), m.group(2).strip()
            ln = txt[:m.start()].count('\n') + 1
            prefix = txt[txt.rfind('\n', 0, m.start()) + 1:m.start()]
            if re.search(r'\b(void|int|char|gh_\w+|float|double|unsigned)\b[\w \*]*$', prefix):
                continue          # 函数定义
            got = 0 if args in ('', 'void') else _count(args)
            if got > out[name]:
                out[name] = got
            site_lines[name].append((os.path.relpath(path, ROOT), ln, got))
    return out, site_lines


def _src_files():
    import glob
    return glob.glob(os.path.join(ROOT, 'src/proprietary/**/*.c'), recursive=True)


def _count(args):
    depth, n = 0, 1
    for ch in args:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        elif ch == ',' and depth == 0:
            n += 1
    return n


def _strip(txt):
    out, i, n, st = [], 0, len(txt), None
    while i < n:
        c = txt[i]
        nx = txt[i + 1] if i + 1 < n else ''
        if st is None:
            if c == '/' and nx == '*':
                st = 'b'; out.append('  '); i += 2; continue
            if c == '/' and nx == '/':
                st = 'l'; out.append('  '); i += 2; continue
            if c == '"':
                st = 'd'; out.append(' '); i += 1; continue
            if c == "'":
                st = 's'; out.append(' '); i += 1; continue
            out.append(c); i += 1; continue
        if st == 'b':
            if c == '*' and nx == '/':
                st = None; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        if st == 'l':
            if c == '\n':
                st = None; out.append('\n'); i += 1; continue
            out.append(' '); i += 1; continue
        if c == '\\':
            out.append('  '); i += 2; continue
        if (st == 'd' and c == '"') or (st == 's' and c == "'"):
            st = None
        out.append(' '); i += 1
    return ''.join(out)


def main():
    fac = load_factory()
    dec = src_arity()
    calls, sites = src_calls()
    rows = []
    for name, info in fac.items():
        if name.startswith('_') or name in ('__aeabi_uidiv',):
            pass
        fac_max = max(s[1] for s in info['sites'])
        our = calls.get(name)
        if our is None:
            continue                       # 我方根本没有这个调用点（可能未实现/内联）
        if fac_max + 1 > our:
            rows.append((name, fac_max + 1, our, info['sites'][0][0]))
    rows.sort(key=lambda r: (r[1] - r[2]), reverse=True)
    print('工厂调用点实参下界 > 我方源码实参个数（**这一类就是丢参**）：%d 条' % len(rows))
    print('%-34s %-8s %-8s %s' % ('callee', '工厂下界', '我方', '首个工厂调用点'))
    for name, f, o, where in rows:
        print('%-34s %-8d %-8d %s' % (name[:34], f, o, where))
    # 附：间接调用清单（函数指针 / driver.so API）
    print('\n间接调用（函数指针/driver.so API）—— 需人工核对 arity：')
    pat = re.compile(r'\(\*\s*([\w\.]+)\s*\)\s*\(([^();]*)\)')
    seen = set()
    for path in _src_files():
        raw = io.open(path, encoding='utf-8', errors='replace').read()
        for m in pat.finditer(_strip(raw)):
            key = (m.group(1), _count(m.group(2)) if m.group(2).strip() else 0)
            if key in seen:
                continue
            seen.add(key)
            print('  %-30s 传 %d 个实参' % (key[0], key[1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
