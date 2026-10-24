#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_argcount.py —— 门禁：找出"实参少于原型形参"的调用点

为什么需要（R262，真机代价换来的）：
    真机第 4 轮的症状是"画面静止、按什么都没反应"。根因不是驱动、不是硬件，
    而是 **7 处 `sunxi_gpio_output(...)` 只传了 1 个实参**（原型是 2 个）。
    这类缺陷的来源是 Ghidra 反编译：`mov r1,#1 ; mov r0,r1 ; bl f` 被折叠成 `f(1)`，
    第二个实参（本来在 r1）被丢掉 ⇒ 编译后 r1 是**残留值** ⇒ C 里属于未定义行为
    ⇒ 位带 SPI 的 CS/CLK 电平随机 ⇒ RF 按键芯片不回话 ⇒ 自检失败 ⇒ 按键线程不建。

判据（本脚本）：
    对每个 `proto.h` 里能解析出形参个数的函数，扫描 proprietary/upgrade 下的调用点，
    实参少于形参即报错。故意**不**处理可变参数与 K&R 原型（它们合法地少参）。
退出码：0 = 干净；1 = 有可疑调用（**硬失败**，不要用「看起来没事」放行）。
"""
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))



def strip_comments_strings(txt):
    """去掉 /*...*/、//...、'...'、"..." 的内容，用空格填充但**保留换行**（行号不变）。
    为什么：注释与字符串里出现的 `foo()` 会被误判成调用点（实测 4 处误报全部来自这里）。
    带误报的门禁会被当成摆设，所以必须做这一步。"""
    out = []
    i, n = 0, len(txt)
    state = None          # None / 'block' / 'line' / 'sq' / 'dq'
    while i < n:
        c = txt[i]
        nx = txt[i + 1] if i + 1 < n else ''
        if state is None:
            if c == '/' and nx == '*':
                state = 'block'; out.append('  '); i += 2; continue
            if c == '/' and nx == '/':
                state = 'line'; out.append('  '); i += 2; continue
            if c == '"':
                state = 'dq'; out.append(' '); i += 1; continue
            if c == "'":
                state = 'sq'; out.append(' '); i += 1; continue
            out.append(c); i += 1; continue
        if state == 'block':
            if c == '*' and nx == '/':
                state = None; out.append('  '); i += 2; continue
            out.append('\n' if c == '\n' else ' '); i += 1; continue
        if state == 'line':
            if c == '\n':
                state = None; out.append('\n'); i += 1; continue
            out.append(' '); i += 1; continue
        if state in ('sq', 'dq'):
            if c == '\\':
                out.append('  '); i += 2; continue
            if (state == 'dq' and c == '"') or (state == 'sq' and c == "'"):
                state = None; out.append(' '); i += 1; continue
            out.append(' '); i += 1; continue
    return ''.join(out)

def proto_nargs():
    txt = io.open(os.path.join(ROOT, 'src/compat/proto.h'), encoding='utf-8', errors='replace').read()
    out = {}
    for m in re.finditer(r'extern\s+[A-Za-z_][\w \*]*?\b(\w+)\s*\(([^)]*)\)\s*;', txt):
        name, params = m.group(1), m.group(2).strip()
        head = txt[max(0, m.start() - 80):m.start()]
        if 'K&R' in head or '...' in params:      # K&R / 可变参数：合法少参
            continue
        if params in ('void', '', 'void)'):
            n = 0
        else:
            depth = 0
            n = 1
            for ch in params:
                if ch in '([':
                    depth += 1
                elif ch in ')]':
                    depth -= 1
                elif ch == ',' and depth == 0:
                    n += 1
        out[name] = n
    return out


def count_args(args):
    depth = 0
    n = 1
    for ch in args:
        if ch in '([':
            depth += 1
        elif ch in ')]':
            depth -= 1
        elif ch == ',' and depth == 0:
            n += 1
    return n



def def_nargs():
    """从**函数定义**里取形参个数。
    ★ 为什么必须有这一步（R262 的真教训）：proto.h 里大量硬件函数被声明成 K&R 空参
      （`extern gh_u4 sunxi_gpio_output();  /* K&R: 参数不可信/不可解析 */`），
      **编译器因此不做实参个数检查** ⇒ Ghidra 丢掉的实参可以静默编译通过。
      只按 proto.h 建表会把这类函数整体漏掉（实测：门禁对本轮的真实缺陷是**假绿**）。
      定义优先：定义里写的是 n 个形参，就以 n 为准。"""
    out = {}
    pat = re.compile(r'\b(\w+)\s*\(([^)]*)\)\s*\n\s*\{')
    for path in glob.glob(os.path.join(ROOT, 'src/proprietary/**/*.c'), recursive=True):
        raw = io.open(path, encoding='utf-8', errors='replace').read()
        txt = strip_comments_strings(raw)
        for m in pat.finditer(txt):
            name, params = m.group(1), m.group(2).strip()
            if params in ('void', ''):
                n = 0
            elif '...' in params:
                continue
            else:
                n = count_args(params)
            out.setdefault(name, n)
    return out

def main():
    nargs = proto_nargs()
    dfn = def_nargs()
    nargs.update(dfn)   # 定义优先（K&R 声明不可信）
    call_re = re.compile(r'\b(\w+)\s*\(([^();]*)\)')
    bad = []
    files = glob.glob(os.path.join(ROOT, 'src/proprietary/**/*.c'), recursive=True)
    files += glob.glob(os.path.join(ROOT, 'src/upgrade/*.c'))
    for path in files:
        raw = io.open(path, encoding='utf-8', errors='replace').read()
        txt = strip_comments_strings(raw)
        for m in call_re.finditer(txt):
            name, args = m.group(1), m.group(2).strip()
            if name not in nargs:
                continue
            # ★ R264 修正：原先这里写成 `nargs[name] < 2: continue`，
            #   结果 0 形参的函数**根本进不到下面的反向规则** ⇒ 对 PlaySound 那一类
            #   （定义 0 参、调用传 2 参）**假绿**。实测：注入已知样本仍 PASS。
            #   现在：≥2 形参走"少参"规则；定义 0 形参且确有实参的走"丢参"规则。
            if nargs[name] < 2 and not (nargs[name] == 0 and name in dfn):
                continue
            # 跳过函数定义本身（行首是类型 + 名字 + '(' 且后接 '{' 的那种形状）
            line_start = txt.rfind('\n', 0, m.start()) + 1
            prefix = txt[line_start:m.start()]
            if re.search(r'\b(void|int|char|gh_\w+|float|double|unsigned)\b[\w \*]*$', prefix):
                continue
            if args in ('', 'void'):
                got = 0
            else:
                got = count_args(args)
            if got < nargs[name]:
                ln = txt[:m.start()].count('\n') + 1
                bad.append((os.path.relpath(path, ROOT), ln, name, got, nargs[name], args[:60]))
            elif got > nargs[name] and nargs[name] == 0 and name in dfn:
                # ★ R264 新增（PlaySound 教训）：**定义 0 形参、调用点却传实参**
                #   ⇒ 重建时把形参丢了（Ghidra 看不到用到的寄存器就不列形参），
                #   编译器又不校验（K&R 声明），于是实参被静默丢弃。
                #   这类缺陷的后果可以很硬：PlaySound 因此让 driver.so 收到垃圾缓冲/长度
                #   ⇒ 全程无声 + 按键后冻死。凡是这种形状，一律报出来人工判定。
                ln = txt[:m.start()].count('\n') + 1
                bad.append((os.path.relpath(path, ROOT), ln, name + '[实参被丢]', got, nargs[name], args[:60]))
    # ---- 基线制：既有缺陷登记在案，只有**新增**才硬失败 ----
    #  为什么：一次性修 45 处 mui_DispBlock/UnDispBlock 的末位实参需要逐点核对工厂 r3，
    #  属于独立任务；但门禁不能因此变成"永远红"（红久必被无视）。
    base_path = os.path.join(ROOT, 'tools/argcount_baseline.txt')
    cur = ['%s|%s|%d|%d' % (p.replace('\\', '/'), n, g, t) for p, l, n, g, t, a in bad]
    if '--update-baseline' in sys.argv:
        io.open(base_path, 'w', encoding='utf-8', newline='\n').write(
            '# check_argcount 基线（R262）：已登记、待逐点核对工厂实参的调用点\n'
            '# 格式：相对路径|函数名|实参个数|形参个数\n' + '\n'.join(sorted(set(cur))) + '\n')
        print('已写入基线 %s（%d 条）' % (base_path, len(set(cur))))
        return 0
    known = set()
    if os.path.exists(base_path):
        for ln in io.open(base_path, encoding='utf-8', errors='replace'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                known.add(ln)
    new_bad = [c for c in cur if c not in known]
    if not new_bad:
        print('check_argcount: PASS（已知 arity %d；基线内待判定 %d 处，新增缺陷 0）'
              % (len(nargs), len(known)))
        return 0
    print('check_argcount: FAIL —— 出现**基线之外**的少参调用（编译后 r1/r2/r3 是残留值）：')
    for c in new_bad:
        print('  ' + c)
    return 1
    print('check_argcount: FAIL —— 以下调用点的实参少于原型形参（编译后 r1/r2 是残留值）：')
    for p, ln, n, g, t, a in bad:
        print('  %s:%d  %s(…%s)  实参 %d / 形参 %d' % (p, ln, n, a, g, t))
    return 1


if __name__ == '__main__':
    sys.exit(main())
