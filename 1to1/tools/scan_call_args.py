#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用点实参个数对拍（**逐函数、逐调用点**，权威来源 = 工厂反编译 C）。

为什么换掉"机器码聚合"口径（2026-09-17 实测，四次修正仍未收敛）：
  以工厂机器码数 `bl` 前的 r0..r3 个数，无论取 min / max / 前缀，都会被三类噪声污染：
    · 寄存器被当临时变量（`mxmlDelete` 的调用点里 r3 是别的用途 ⇒ 多算）；
    · 尾调用继承 r0（`mxmlRelease → mxmlDelete` ⇒ 少算）；
    · 编译器为"未使用的形参"预置 0（`stbtt_GetFontVMetrics(font,&asc,0)` 会把 r3 也置 0 ⇒ 多算）。
  实测产物：19 项清单里至少 3 项是**假阳性**（`stbtt_GetFontVMetrics` / `GetFilenameExt` / `FilePreEmu`
  工厂自己也用少参调用，我们没错）。

正确口径：
  工厂的 **per-function 反编译 C** 已经按"C 语言语义"渲染了每个调用点的**真实实参**。
  我们与工厂**同名函数**（`FUN_xxxx_<name>.c`）里，**同一个被调者**的实参个数应当一致。
  ⇒ 判据：对 (调用者, 被调者) 对，若 `max(工厂实参) > max(我们实参)` ⇒ 该调用点漏参。
  这样"工厂自己也少传"的情况天然被排除（双方一致即不报）。

自证（铁律 101）：内置三个**已人工核对过**的锚点：
  · dir_serial_list —— 工厂 `dir_serial_list(iVar9,&DAT_002dd860)` = 2 参；
  · strupr —— 工厂 `strupr(&FilenameExt)` = 1 参；
  · stbtt_GetFontVMetrics —— 工厂 `(auStack_9c,&local_a8,&local_a4,&local_a0)` = 4 参。
  ★ 注意**不能**用 `mxmlLoadFile` 当锚点：工厂机器码明确是 3 参（`mov r2,#0`），
    但 Ghidra 因其推断原型只有 2 参而把它**渲染成 `mxmlLoadFile(0,__stream)`**。
    好在这个偏差方向是"只少算不多算" ⇒ 本门禁**保守、不会产生假阳性**
    （代价：像 mxmlLoadFile 这种 Ghidra 少算的漏参会漏报，由机器码口径的
    `tools/scan_kr_argcount.py` 兜住）。
  锚点命中不了 ⇒ 解析器或口径坏了 ⇒ 拒绝出结论。

用法：python tools/scan_call_args.py [--root .] [--ghidra <per-function 目录>] [--pending <台账>]
退出码 0 = 无新增；1 = 有新增漏参；2 = 自证失败。
"""
import argparse
import glob
import os
import re
import sys

GHIDRA_DIR = 'D:/output/rkgame/decompiled/02-ghidra-c/03-per-function'
SRC_DIR = 'src/proprietary'

# 允许清单：**工厂在我们这个调用者函数里本来就少传**，或该调用点已人工核对无碍。
# 每条都必须能说出理由，禁止为了过门禁而堆白名单。
ALLOW = {
    # (caller, callee): '理由'
    ('FUN_00021c08_SeletEmuCore', 'FilePreEmu'): '工厂同一函数内也是 0 参调用（Ghidra: iVar1 = FilePreEmu();）',
}


def strip_comments_and_strings(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    s = re.sub(r'//[^\n]*', ' ', s)
    s = re.sub(r'"(?:\\.|[^"\\])*"', '""', s)
    s = re.sub(r"'(?:\\.|[^'\\])*'", "''", s)
    return s


KEYWORDS = {
    'if', 'for', 'while', 'switch', 'return', 'sizeof', 'do', 'else', 'case',
    'defined', 'typeof', '__attribute__', 'break', 'continue', 'goto',
}


def calls_in(text):
    """返回 [(callee, argc)]（只取形如 name(...) 的调用；跳过关键字与宏）。"""
    body = strip_comments_and_strings(text)
    out = []
    for m in re.finditer(r'(?<![A-Za-z0-9_>.])([A-Za-z_]\w*)\s*\(', body):
        name = m.group(1)
        if name in KEYWORDS:
            continue
        i = m.end()
        depth, j = 1, i
        while j < len(body) and depth > 0:
            if body[j] == '(':
                depth += 1
            elif body[j] == ')':
                depth -= 1
            j += 1
        if depth != 0:
            continue
        args = body[i:j - 1].strip()
        # ★★ 关键过滤：**函数定义行不是调用**。
        #   实测假阳性：`void spi_printf(char *param_1, ...)` 被当成"2 参调用"，
        #   而工厂侧同名的定义行 `void spi_printf(char *p1,p2,p3,p4)` 被当成"4 参调用"
        #   ⇒ 凭空造出一条"漏参"。判据：`)` 之后紧跟 `{`，或整行以类型开头且以 `)` 收尾。
        tail = body[j:j + 8]
        line_start = body.rfind('\n', 0, m.start()) + 1
        before = body[line_start:m.start()]
        is_definition = ('{' in tail) or (';' not in before and '=' not in before
                                         and '(' not in before and ')' not in before
                                         and before.strip() != '' and before.strip().split()[0]
                                         in ('void', 'int', 'char', 'byte', 'unsigned', 'long',
                                             'short', 'float', 'double', 'undefined4', 'undefined1',
                                             'undefined2', 'undefined8', 'gh_u1', 'gh_u2', 'gh_u4',
                                             'gh_byte', 'gh_uint', 'static'))
        if is_definition:
            continue
        n = 0 if args in ('', 'void') else (1 + len(re.findall(r',(?![^()\[\]]*[\)\]])', args)))
        out.append((name, n))
    return out


def caller_name(fname):
    """`FUN_00016f08_FilePreEmu.c` -> `FUN_00016f08_FilePreEmu`；也兼容别的命名。"""
    return fname[:-2] if fname.endswith('.c') else fname


def index_calls(root, fnames):
    """caller -> {callee: max_argc}"""
    res = {}
    for fn in fnames:
        txt = open(fn, encoding='utf-8', errors='replace').read()
        c = caller_name(os.path.basename(fn))
        d = res.setdefault(c, {})
        for callee, n in calls_in(txt):
            if n > d.get(callee, -1):
                d[callee] = n
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--ghidra', default=GHIDRA_DIR)
    ap.add_argument('--pending', default=None)
    ap.add_argument('--write-pending', action='store_true')
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    if not os.path.isdir(a.ghidra):
        print('  [SKIP] 找不到工厂反编译目录 %s' % a.ghidra)
        return 0
    fa = index_calls(root, sorted(glob.glob(os.path.join(a.ghidra, '*.c'))))
    ours = index_calls(root, sorted(glob.glob(os.path.join(root, SRC_DIR, '**', '*.c'), recursive=True)))

    # ---- 自证 ----
    anchors = [('dir_serial_list', 2), ('strupr', 1), ('stbtt_GetFontVMetrics', 4)]
    ok = 0
    for callee, want in anchors:
        found = max([d.get(callee, -1) for d in fa.values()] or [-1])
        if found != want:
            print('  [FATAL] 自证失败：锚点 %s 在工厂反编译里量到 %d 参（期望 %d）'
                  ' ⇒ 解析器不可信，拒绝出结论' % (callee, found, want))
            return 2
        ok += 1
    print('  自证通过（%d 个锚点：%s）'
          % (ok, ', '.join('%s=%d' % (c, n) for c, n in anchors)))

    if len(fa) < 300 or len(ours) < 150:
        print('  [FATAL] 自证失败：工厂函数 %d / 我们函数 %d（阈值 300/150）' % (len(fa), len(ours)))
        return 2

    pend = set()
    if a.pending and os.path.exists(a.pending):
        for ln in open(a.pending, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                pend.add(tuple(ln.split()[:3]))

    bad = []
    pairs = 0
    for caller, dfa in fa.items():
        dou = ours.get(caller)
        if not dou:
            continue
        for callee, wa in dfa.items():
            if callee not in dou:
                continue
            wu = dou[callee]
            pairs += 1
            if wa > wu and (caller, callee, str(wa)) not in pend and (caller, callee) not in ALLOW:
                bad.append((caller, callee, wa, wu))

    print('  可比对 (调用者,被调者) 对：%d 个' % pairs)

    if a.write_pending:
        with open(a.pending or 'tools/call_args_pending.txt', 'w', encoding='utf-8', newline='\n') as f:
            f.write('# 调用点漏参·已知待修台账（棘轮）。格式: <调用者函数> <被调者> <工厂实参个数>\n')
            f.write('# 新增违例不在本台账内 ⇒ 门禁直接失败。修好一项就删一行。\n')
            for caller, callee, wa, wu in bad:
                f.write('%s %s %d\n' % (caller, callee, wa))
        print('  已写入台账：%d 项' % len(bad))
        return 0

    known = [b for b in bad if (b[0], b[1], str(b[2])) in pend]
    new_ = [b for b in bad if (b[0], b[1], str(b[2])) not in pend]
    if known:
        print('  台账内已知待修：%d 项' % len(known))
    if new_:
        print('  ★★ 新增漏参 %d 处（不在台账内 ⇒ 判失败）：' % len(new_))
        for caller, callee, wa, wu in sorted(new_)[:40]:
            print('     %-34s -> %-26s 工厂 %d 参 / 我们 %d 参' % (caller, callee, wa, wu))
        return 1
    print('  ✓ 无新增漏参（台账剩余 %d 项）' % len(known))
    return 0


if __name__ == '__main__':
    sys.exit(main())
