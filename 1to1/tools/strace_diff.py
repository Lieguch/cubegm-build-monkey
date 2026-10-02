#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""strace_diff.py —— **启动链的首个分叉点**（两侧 strace 归一化后**按线程**对齐）

## 为什么需要它（现有判据差在哪）
现有三条启动链判据都是**粗粒度**：`behav_diff.py`（事件）/ `milestones.py`（阶段）/
`qemu_coverage.py`（比例）。两侧「都过 M5、都 exit=139」时，它们回答不了
**"第一条不同的系统调用是哪一条"**。而这份粒度的数据 `qemu-user -strace` 本来就在采。

## ★★ 第 113 轮的关键修正：**必须按线程分开对齐**
`qemu-user -strace` 是**多线程交错**输出，交错时还会**丢掉换行**：
```
A: futex(...)18024 mmap2(...)      B: mmap2(...)18983 futex(...)
```
⇒ 逐行 diff 会把"两个线程的调度顺序不同"误判成"行为差异"，制造大量**假分叉**。
⇒ 做法：用 pid 标记把原始流切成 `(pid, 每条 syscall)`，**按 pid 分组**，
两侧线程**按首次出现顺序配对**（pid 本身必然不同），再逐线程对齐。

## 归一化规则（只抹掉"必然不同"的）
  · pid 标记（线程身份只用于配对，不进比较）
  · `0x…` → `0x#`（地址/指针）
  · **十进制大数（≥ 8 位）→ `#`**：本 guest 里那只会是地址（fd/长度/flags 都是小整数）；
    `nanosleep(1082131616,…)` 这类"十进制栈地址"曾制造大量假分叉
  · **签名白名单噪声**：`set_tid_address`/`getpid`/`gettid`… 的**返回值就是 pid**
  · 保留：syscall 名、**字符串实参（路径/文件名）**、十进制标量、`PROT_*`/`MAP_*`、`errno=N`
  · **不做"只取公共前缀"的截断**（该判据已被两次证伪）

## 用法
    python tools/strace_diff.py <a.txt> <b.txt> [--label-a factory] [--label-b rebuild]
                                [--out report/x.txt]
退出: 0 = 无行为类分叉；2 = 存在行为类分叉；3 = 一侧为空；11 = 读不到输入
"""
import argparse
import difflib
import io
import re
import sys

PID_RE = re.compile(r'^\s*\d+\s+')
HEX_RE = re.compile(r'0x[0-9a-fA-F]+')
PID_MARK = re.compile(r'(\d{3,7}) (?=[A-Za-z_][A-Za-z0-9_]*\(|[-+]{3})')
BIGDEC_RE = re.compile(r'(?<![\w.])-?\d{8,}(?![\w.])')
RET_RE = re.compile(r'^(?P<call>\w+)\((?P<args>.*)\)\s*=\s*(?P<ret>.*)$')
GEOM = re.compile(r'^\s*(mprotect|mmap2?|munmap|mremap|brk|madvise|rt_sigprocmask)\b')

PID_RET = ('set_tid_address', 'getpid', 'gettid', 'getppid',
           'getuid', 'geteuid', 'getgid', 'getegid')
NOISE_MARKS = []


def norm(line):
    s = line.rstrip('\n')
    s = PID_RE.sub('', s)
    s = HEX_RE.sub('0x#', s)
    s = BIGDEC_RE.sub('#', s)
    m = RET_RE.match(s)
    if m and m.group('call') in PID_RET:
        s = '%s(%s) = #' % (m.group('call'), m.group('args'))
        if m.group('call') not in NOISE_MARKS:
            NOISE_MARKS.append(m.group('call'))
    return s.rstrip()


def load_raw(path):
    try:
        return io.open(path, encoding='utf-8', errors='replace').read()
    except Exception as e:
        print('!! 读不到 %s: %s' % (path, e))
        return None


def split_threads(text):
    marks = [(m.start(), m.group(1), m.end()) for m in PID_MARK.finditer(text)]
    out, order = {}, []
    for i, (s, pid, e) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        body = text[e:end].strip()
        if not body:
            continue
        if pid not in out:
            out[pid] = []
            order.append(pid)
        out[pid].append(norm(body))
    return out, order


# ★★ 2026-10-01（第 113 轮）**第三层归一**：把"非行为"的东西从序列里拿掉，但**全部计数上报**。
#   实测（gd 型）剩余分叉的构成：逐字符 write(2,…,1) 日志、丢失换行造成的 `= ret` 缺失、
#   futex/nanosleep 的时序 —— 这三类都**不是功能性差异**，却会在逐行对齐里刷出几十段假分叉。
#   ★ 纪律：归一化必须**透明**（打印各排除多少），不许静默抹平。
#   · 时序类：futex / nanosleep / sched_yield 等（同一逻辑的调度顺序本就可以不同）
#   · 日志类：连续写 fd=2（stderr）的字符流 ⇒ 折叠成一个标记（保留"这里记了日志"这一个事实）
#   · 续行类：qemu 交错时丢换行 ⇒ 没有 `= <ret>` 的行与下一行合并
TIMING_CALLS = ('futex', 'nanosleep', 'clock_nanosleep', 'sched_yield',
                'restart_syscall', 'rt_sigreturn', 'rt_sigprocmask')
DROP_STATS = {'timing': 0, 'logrun': 0, 'merged': 0}


def canon(lines):
    """把一条线程的归一化序列再收敛一层（透明计数）。"""
    # ① 合并续行（缺 `= ` 说明换行被丢掉）
    merged = []
    i = 0
    while i < len(lines):
        l = lines[i]
        while (' = ' not in l) and (i + 1 < len(lines)):
            i += 1
            DROP_STATS['merged'] += 1
            l = l + lines[i]
        merged.append(l)
        i += 1
    # ② 丢时序类；③ 折叠连续 stderr 写
    out = []
    logrun = 0
    for l in merged:
        name = l.split('(', 1)[0].strip()
        if name in TIMING_CALLS:
            DROP_STATS['timing'] += 1
            continue
        # ★ 易错点（我自己踩过）：fd 跟在**左括号**后 ⇒ 判据必须是 `write(2,` 前缀，
        #   写成 `,2,` 会永远匹配不上（于是"折叠 0 条"却看不出问题）。
        if name == 'write' and l.replace(' ', '').startswith('write(2,'):
            logrun += 1
            continue
        if logrun:
            out.append('write(2,#)x%d   [stderr 日志折叠]' % logrun)
            DROP_STATS['logrun'] += logrun
            logrun = 0
        out.append(l)
    if logrun:
        out.append('write(2,#)x%d   [stderr 日志折叠]' % logrun)
        DROP_STATS['logrun'] += logrun
    return out


def regions_of(na, nb):
    sm = difflib.SequenceMatcher(None, na, nb, autojunk=False)
    regs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        sa, sb = na[i1:i2], nb[j1:j2]
        geom = bool(sa) and bool(sb) and all(GEOM.match(x) for x in sa) and all(GEOM.match(y) for y in sb)
        regs.append((tag, i1, i2, j1, j2, geom))
    return regs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('a'); ap.add_argument('b')
    ap.add_argument('--label-a', default='A'); ap.add_argument('--label-b', default='B')
    ap.add_argument('--max-regions', type=int, default=12)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()

    ta, tb = load_raw(a.a), load_raw(a.b)
    if ta is None or tb is None:
        return 11
    A, oa = split_threads(ta)
    B, ob = split_threads(tb)
    for p in list(A):
        A[p] = canon(A[p])
    for p in list(B):
        B[p] = canon(B[p])

    buf = []

    def say(s=''):
        buf.append(s)

    say('=' * 104)
    say('启动链 strace 对齐（**按线程分开**）   A=%s (%s)   B=%s (%s)' % (a.label_a, a.a, a.label_b, a.b))
    say('=' * 104)
    say('  线程数： A=%d  B=%d ；总 syscall 行： A=%d  B=%d'
        % (len(oa), len(ob), sum(len(A[p]) for p in oa), sum(len(B[p]) for p in ob)))
    if not oa or not ob:
        say('')
        say('  ★ 一侧为空 ⇒ **无法对齐**（不是"相同"）。')
        txt = '\n'.join(buf)
        print(txt)
        if a.out:
            io.open(a.out, 'w', encoding='utf-8', newline='\n').write(txt + '\n')
        return 3

    rows = []
    tot_reg = tot_geom = 0
    first = None
    main_regs = []          # tid#0 的分叉段（用于明细）
    main_seqs = (None, None)
    for k in range(min(len(oa), len(ob))):
        pa, pb = oa[k], ob[k]
        na, nb = A[pa], B[pb]
        regs = regions_of(na, nb)
        if k == 0:
            main_regs = regs
            main_seqs = (na, nb)
        g = sum(1 for r in regs if r[5])
        tot_reg += len(regs)
        tot_geom += g
        pre = 0
        for x, y in zip(na, nb):
            if x != y:
                break
            pre += 1
        rows.append((k, pa, pb, len(na), len(nb), pre, len(regs), g))
        if regs and first is None:
            tag, i1, i2, j1, j2, geom = regs[0]
            first = (k, i1, geom,
                     na[i1] if i1 < len(na) else '«A 结束»',
                     nb[j1] if j1 < len(nb) else '«B 结束»')

    say('')
    say('--- 逐线程统计（tid# = 首次出现顺序，两侧按该顺序配对）---')
    say('  %-5s %-8s %-8s %-7s %-7s %-9s %-7s' % ('tid#', 'pidA', 'pidB', '行A', '行B', '等号前缀', '分叉段'))
    for k, pa, pb, la, lb, pre, nr, g in rows:
        say('  %-5d %-8s %-8s %-7d %-7d %-9d %-7d' % (k, pa, pb, la, lb, pre, nr))

    if NOISE_MARKS:
        say('  已按白名单抹除噪声项：%s（返回值本身就是 pid）' % ', '.join(NOISE_MARKS))
    say('  ★ 透明计数（归一化拿掉了多少）：时序类 %d ／ stderr 日志折叠 %d ／ 续行合并 %d'
        % (DROP_STATS['timing'], DROP_STATS['logrun'], DROP_STATS['merged']))
    if first:
        k, idx, geom, la, lb = first
        say('')
        say('--- 首个分叉（tid#%d 第 %d 行）%s ---'
            % (k, idx, '【装载几何类】' if geom else '【行为类】'))
        say('  A: %s' % la[:150])
        say('  B: %s' % lb[:150])

    behave = tot_reg - tot_geom
    # ---- 明细：主线（tid#0）的前 N 个分叉段（可执行信息就在这里）----
    na, nb = main_seqs
    if main_regs and na is not None:
        say('')
        say('--- tid#0 分叉段明细（前 %d 段）---' % a.max_regions)
        for tag, i1, i2, j1, j2, geom in main_regs[:a.max_regions]:
            say('  [%s%s] A[%d:%d](%d) B[%d:%d](%d)'
                % (tag, '-GEOM' if geom else '', i1, i2, i2 - i1, j1, j2, j2 - j1))
            if tag == 'replace':
                say('      A: %s' % (' | '.join(na[i1:i2])[:140]))
                say('      B: %s' % (' | '.join(nb[j1:j2])[:140]))
            elif tag == 'delete':
                for l in na[i1:i2][:2]:
                    say('      A-only: %s' % l[:130])
            else:
                for l in nb[j1:j2][:2]:
                    say('      B-only: %s' % l[:130])
    say('')
    say('-' * 104)
    verdict = 'ALIGNED' if tot_reg == 0 else ('ALIGNED-EXCEPT-LOADER-GEOMETRY' if behave == 0 else 'DIVERGE')
    say('  结论： %s（分叉段合计 %d ／ 装载几何类 %d ／ **行为类 %d**）'
        % (verdict, tot_reg, tot_geom, behave))
    say('  ★ 读法：按线程分开对齐后，"两个线程调度顺序不同"不再算差异；')
    say('    装载几何类 = 段页数/映射大小不同（预期会有）；**行为类 = 真正要修的**。')

    txt = '\n'.join(buf)
    print(txt)
    if a.out:
        io.open(a.out, 'w', encoding='utf-8', newline='\n').write(txt + '\n')
    return 0 if behave == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
