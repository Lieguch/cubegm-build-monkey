#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""blockread_slot_probe —— 穷举「块读函数族」调用点的栈槽 DCE 探针。

为什么需要它（R180 / GAP 18.02）
--------------------------------
`dce_ref_diff.py` 的集合级 Δ 有个盲区（GAP 18.01）：若某工厂符号在本 TU 的**别处**
仍被引用，它的死写被 -Os 消除**不会**改变符号在场性 ⇒ Δ 为空、门禁放行。
`mui_DisplayThumbnail` 正是因此漏网：af29c/af2a0/af6b8/af6bc/af6c0/af6c4 在函数的
memcpy 循环里都用到了，而块读参数槽里的同名死写被整段删除，集合级 Δ 完全看不见。

本探针用**不依赖符号集合**的判据：对每个调用「块读函数族」的 TU，分别编译 -O0/-Os，
比较函数体内**栈存储指令数**。-Os 明显少于 -O0 ⇒ 参数槽写入被消除 ⇒ 待核。

块读函数族 = 工厂里用 `int *param` 索引 param[0..5] 的五个函数：
    blockcopy / blockadaptive / mui_blockcopy / popwindows / popoffwindows

判据分级（都不是缺陷证明，是**分诊**）：
    ★  -Os 栈存储 < -O0 栈存储            ⇒ 待核（可能 UB-DCE）
    ★★ 且调用点前 stores < 2               ⇒ 强嫌疑（块读参数槽整体死写）
    OK  otherwise

确认必须回到工厂反汇编（tools/factory_fn_stack.py）逐槽数读/写，或直接
dump 该调用点前后的 -Os 汇编（本工具 --dump 模式）。

用法
----
    CC=arm-linux-gnueabihf-gcc python3 tools/blockread_slot_probe.py            # 全量
    python3 tools/blockread_slot_probe.py --dump FUN_00014f84_mui_DisplayThumbnail.c
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'proprietary')
INC = os.path.join(ROOT, 'src', 'compat')

BLOCKREAD_CALLERS = ('blockcopy', 'blockadaptive', 'mui_blockcopy',
                     'popwindows', 'popoffwindows')
CALL_RE = re.compile(r'\bbl\s+(' + '|'.join(BLOCKREAD_CALLERS) + r')\b')
# 栈存储：基址 sp / r7 / fp(r11) / r13，常量位移或纯基址
STR_RE = re.compile(r'\b(str\w*)\s+(\w+)\s*,\s*\[(sp|r7|fp|r11|r13)(?:\s*,\s*#(-?\d+))?\]')
LABEL_RE = r'^%s:\s*$'


def asm_of(path, opt, cc=None):
    cc = (cc or os.environ.get('CC', 'arm-linux-gnueabihf-gcc')).split()
    cmd = cc + [opt, '-S', '-w', '-I' + INC, '-march=armv7-a',
                '-mfloat-abi=hard', '-mfpu=neon', '-fno-pic',
                '-fno-stack-protector', path, '-o', '-']
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def fn_name(path):
    b = os.path.basename(path)
    m = re.match(r'FUN_[0-9a-f]+_([A-Za-z0-9_]+)\.c$', b)
    return m.group(1) if m else b[:-2]


def fn_body(text, fn):
    """切出 `fn:` 标签到 `.size fn, .-fn` 之间的函数体。"""
    if not text:
        return ''
    m = re.search(LABEL_RE % re.escape(fn), text, re.M)
    if not m:
        return ''
    rest = text[m.end():]
    e = re.search(r'^\s*\.size\s+' + re.escape(fn) + r'\b', rest, re.M)
    return rest[:e.start()] if e else rest


def stores_before_calls(body):
    """返回 [(调用前 stores 数, 调用符号名), ...]（按调用顺序）。"""
    out = []
    lines = body.splitlines()
    n = 0
    for ln in lines:
        if CALL_RE.search(ln):
            out.append((n, CALL_RE.search(ln).group(1)))
            n = 0
            continue
        if STR_RE.search(ln):
            n += 1
    return out


def probe(path, cc=None):
    fn = fn_name(path)
    a = asm_of(path, '-O0', cc)
    b = asm_of(path, '-Os', cc)
    if a is None or b is None:
        return None
    ba, bb = fn_body(a, fn), fn_body(b, fn)
    if not ba or not bb:
        return None
    sa = len(STR_RE.findall(ba))
    sb = len(STR_RE.findall(bb))
    calls = stores_before_calls(bb)
    return {'fn': fn, 'o0': sa, 'os': sb, 'calls': calls,
            'body_os': bb, 'body_o0': ba}


def iter_sources():
    out = []
    for dp, dn, fn in os.walk(SRC):
        for f in sorted(fn):
            if f.endswith('.c'):
                p = os.path.join(dp, f)
                try:
                    t = open(p, encoding='utf-8', errors='replace').read()
                except OSError:
                    continue
                if any(s + '(' in t for s in BLOCKREAD_CALLERS):
                    out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', help='dump 指定文件的 -Os 函数体（可按 basename 匹配）')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    if a.dump:
        for p in iter_sources():
            if a.dump in os.path.basename(p):
                r = probe(p)
                if not r:
                    print('  ★ %s 探针失败' % p)
                    continue
                print('=' * 96)
                print('%s   fn=%s   -O0 栈存储=%d  -Os 栈存储=%d'
                      % (os.path.basename(p), r['fn'], r['o0'], r['os']))
                print('=' * 96)
                for n, sym in r['calls']:
                    print('  调用 %-14s 前有 %d 条栈存储 %s'
                          % (sym, n, '★ 强嫌疑（参数槽整体死写）' if n < 2 else ''))
                print('--- -Os 函数体 ---')
                print(r['body_os'])
                return 0
        print('  ★ 没找到匹配 %r 的块读调用者' % a.dump)
        return 2

    files = iter_sources()
    if a.limit:
        files = files[:a.limit]
    print('=' * 96)
    print('块读函数族调用点栈槽 DCE 探针（-O0 vs -Os 栈存储指令数）')
    print('=' * 96)
    n_flag = 0
    for p in files:
        r = probe(p)
        rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
        if r is None:
            print('%-64s 探针失败（编译/函数体切分）' % rel)
            continue
        weak = [n for n, _ in r['calls'] if n < 2]
        if r['os'] < r['o0']:
            n_flag += 1
            tag = '★ 待核'
            if weak:
                tag += '（%d 处调用前 <2 条栈存储 ⇒ 强嫌疑）' % len(weak)
            print('%-64s -O0=%-3d -Os=%-3d  %s' % (rel, r['o0'], r['os'], tag))
        else:
            print('%-64s -O0=%-3d -Os=%-3d  OK' % (rel, r['o0'], r['os']))
    print()
    print('  待核文件 %d 个 / 共 %d 个块读调用者' % (n_flag, len(files)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
