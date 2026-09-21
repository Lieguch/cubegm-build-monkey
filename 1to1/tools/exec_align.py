#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两侧执行轨迹对齐 —— 直接给出**首个分歧点**（Laelaps 法的落地）。

## 为什么需要它（为什么 `exec_set_diff` 不够）

`tools/exec_set_diff.py` 比的是**执行集合**（无序、去重）。它是定位分歧的**第一手**证据，
但有两处天然盲区：

1. **不含顺序**：两侧"都执行了 A 和 B"，但一边是 A→B、另一边是 B→A，集合差集看不出来；
2. **不含"谁先退出"**：参照侧提前崩溃时，另一侧会"凭空中多出"一整套函数
   （2026-09-20 C5 实测：差集显示"重建侧多跑 24 个函数"，实际是**工厂侧空指针早逝**）。

本工具补上这两块：把两侧的 `-d exec` 完整轨迹**按顺序**对齐，给出**第一个分歧点**与上下文。
这正是固件差分测试的标准做法（Laelaps, ACM 10.1145/3427228.3427280：
导出翻译块执行轨迹 → 对齐 → 定位首个分歧）。

## 关键设计 1：只对齐主程序自身代码段，并按各自 symtab 归一

两侧是**两个不同的二进制**（地址不同、还各自链了不同版本的 libc/ld.so）⇒
地址序列**天然不可直接比**。所以：
- 先把 PC **过滤**到主程序自身可执行段（PT_LOAD PF_X / SHF_EXECINSTR）——丢掉 libc/ld.so 的帧；
- 再用**各自的 symtab** 把 PC 归一成 `函数名+偏移` ⇒ 变成可比序列。
（★ 字段映射已逐条校验：qemu `-d exec` 行第 2 个 16 进制字段就是 PC，
  且 qemu 追加的符号名与本仓 symtab **逐条一致**，实测 8/8。）

## 关键设计 2（★ 首跑踩坑后加的）：**必须从"锚点"开始比，不能从下标 0**

首跑实测（CI `20ba70e4`，C5）三个视图**全部报"第 0 次就不同"** —— 这是**仪器缺陷**，不是发现：
两个不同二进制的 **CRT / loader 前导天然不同**
（factory 首个主程序帧 = `main+0x1ec`，rebuild = `_init+0x8`），从下标 0 比必然立刻分歧，
于是整份报告变成"两侧入口不同"这种**废话**，真正的分歧点被前导噪声顶掉了。

⇒ 改为**锚点对齐**：取两侧**共有的第一个"实质"符号**（默认 `main`；可选 `--anchor`），
从它各自**首次出现**的位置开始比；锚点之前的差异只作**信息性**记录（前导长度），不参与判决。
若定不到锚点 ⇒ 判 `INCONCLUSIVE`（exit 3），**不给"无分歧"这种假绿**。

## 三个视图（都报；锚点之后）

| 视图 | 归一方式 | 用途 |
|---|---|---|
| ① 逐次执行 | `函数名+0x偏移` | 最细：同一函数内走了不同路径 |
| ② 按函数名 | `函数名`（丢偏移） | 中等：偏移差异不算分歧 |
| ③ 按函数转移 | 折叠连续重复 → `A→B→C` | 最可读：高层路径是否走偏 |

## 用法

    python3 tools/exec_align.py --factory report/qemu_c5/exec_factory.log \
                                --ours    report/qemu_c5/exec_rebuild.log \
                                [--anchor main] [--out report/qemu_c5/exec_align.txt]
退出码：0 = 锚点之后三视图都无分歧；1 = 有分歧（**观测项**）；3 = 无法判定（缺日志/定不到锚点）。
"""
import argparse
import bisect
import os
import re
import struct
import sys

LINE = re.compile(r'^Trace\s+\d+:\s+0x[0-9a-fA-F]+\s+\[([0-9a-fA-F]{8})/([0-9a-fA-F]{8})/'
                  r'([0-9a-fA-F]{8})/([0-9a-fA-F]{8})\]')

# ★★ CRT / loader 样板符号：两侧必然不同（链的 crt 版本、ld 不同）⇒ **不参与分歧判决**。
#    不排除它们的后果实测过：三个视图全部在第 0 次报分歧，报告变成废话。
CRT_RE = re.compile(
    r'^(_init|_fini|_start|__libc_csu_init|__libc_csu_fini|__libc_start_main|'
    r'__ARMv7ABSLongThunk_|__ARMv7A_LongThunk_|_dl_|frame_dummy|'
    r'register_tm_clones|deregister_tm_clones|__do_global_dtors_aux|'
    r'__gnu_|@nosym|@0x)')


def is_crt(nm):
    return bool(CRT_RE.match(nm))


def elf_exec_ranges_and_syms(path):
    """返回 (可执行地址区间列表, 已排序的 (addr, name) 列表)。

    可执行区间取 PT_LOAD 里 `PF_X` 的那些 + `SHF_EXECINSTR` 的节（两者并集，稳妥）。
    符号取 `SHT_SYMTAB` 的 `STT_FUNC`（★ 不能用 dynsym —— 重建产物的 dynsym 只有 85 项）。
    """
    d = open(path, 'rb').read()
    if d[:4] != b'\x7fELF':
        return None, None
    phoff = struct.unpack_from('<I', d, 28)[0]
    phentsize = struct.unpack_from('<H', d, 42)[0]
    phnum = struct.unpack_from('<H', d, 44)[0]
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    shentsize = struct.unpack_from('<H', d, 46)[0]
    shnum = struct.unpack_from('<H', d, 48)[0]

    rng = []
    for i in range(phnum):
        p_type, p_off, p_va, p_pa, p_filesz, p_memsz, p_flags = \
            struct.unpack_from('<7I', d, phoff + i * phentsize)[:7]
        if p_type == 1 and (p_flags & 1):                      # PT_LOAD | PF_X
            rng.append((p_va, p_va + p_memsz))
    S = [struct.unpack_from('<10I', d, e_shoff + i * shentsize) for i in range(shnum)]
    for s in S:
        if (s[2] & 0x4) and s[5] > 0:                          # SHF_EXECINSTR
            rng.append((s[3], s[3] + s[5]))

    syms = []
    for s in S:
        if s[1] != 2:                                          # SHT_SYMTAB
            continue
        stro = S[s[6]][4]
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2 or sz == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            syms.append((val, d[stro + nmn:k].decode('utf-8', 'replace')))
    syms.sort()
    return rng, syms


def read_trace(path, rng):
    """读出轨迹里的 PC 序列（只保留落在 `rng` 内的 = 主程序自身代码段）。"""
    pcs = []
    total = 0
    with open(path, encoding='utf-8', errors='replace') as f:
        for ln in f:
            m = LINE.match(ln)
            if not m:
                continue
            total += 1
            pc = int(m.group(2), 16)
            for lo, hi in rng:
                if lo <= pc < hi:
                    pcs.append(pc)
                    break
    return pcs, total


def normalize(pcs, syms):
    """PC 序列 → [(函数名, 函数名+偏移)]。找不到符号的用 `@0x...`。"""
    starts = [v for v, _ in syms]
    out = []
    for pc in pcs:
        i = bisect.bisect_right(starts, pc) - 1
        if i < 0:
            out.append(('@nosym', '@0x%x' % pc))
            continue
        base, nm = syms[i]
        out.append((nm, '%s+0x%x' % (nm, pc - base)))
    return out


def first_index_of(seq, name, key=0):
    for i, x in enumerate(seq):
        if x[key] == name:
            return i
    return -1


def find_anchor(nf, nr, want=None):
    """定锚：返回 (锚点名, factory 侧首次下标, rebuild 侧首次下标)；定不到返回 (None, -1, -1)。

    规则：
      1. `--anchor` 指定时先试它；
      2. 否则试 `main`（两侧都有，且是"业务代码起点"的自然锚）；
      3. 再否则退化为"factory 侧首个**非 CRT** 且 rebuild 侧也出现过的符号"。
    ★ 为什么需要锚：见模块 docstring「关键设计 2」——CRT/loader 前导天然不同，
      从下标 0 比会把真正的分歧点顶掉。
    """
    cands = []
    if want:
        cands.append(want)
    else:
        cands.append('main')
    rb_first = {}
    for i, x in enumerate(nr):
        rb_first.setdefault(x[0], i)
    for nm in cands:
        ia = first_index_of(nf, nm)
        ib = rb_first.get(nm, -1)
        if ia >= 0 and ib >= 0:
            return nm, ia, ib
    if want:
        return None, -1, -1
    for i, x in enumerate(nf):
        nm = x[0]
        if is_crt(nm):
            continue
        if nm in rb_first:
            return nm, i, rb_first[nm]
    return None, -1, -1


def transitions(seq, key=0):
    """折叠连续重复 → 转移序列。"""
    out = []
    for x in seq:
        if not out or out[-1] != x[key]:
            out.append(x[key])
    return out


def first_diff(a, b):
    """返回首个不同处的下标；完全相同返回 -1；一方是另一方前缀时返回较短长度。"""
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return -1 if len(a) == len(b) else n


def show_ctx(title, fa, fb, i, width=6):
    L = ['  --- %s ---' % title]
    if i < 0:
        L.append('     ✓ 锚点之后两侧**完全一致**（各 %d / %d 次）' % (len(fa), len(fb)))
        return L
    L.append('     ★ 首个分歧点 = 锚点之后第 %d 次（0 基）；之前 %d 次完全一致' % (i + 1, i))
    lo = max(0, i - width)
    L.append('     %-6s %-34s | %s' % ('idx', 'factory', 'rebuild'))
    for k in range(lo, min(len(fa), len(fb), i + 3)):
        mark = '★' if k == i else ' '
        L.append('     %s%-5d %-34s | %s' % (mark, k, str(fa[k])[:34], str(fb[k])[:34]))
    if i >= len(fa):
        L.append('     ⚠️ factory 侧锚点后只剩 %d 次（rebuild %d 次）⇒ 之后的分歧都是"早逝的影子"'
                 % (len(fa), len(fb)))
    if i >= len(fb):
        L.append('     ⚠️ rebuild 侧锚点后只剩 %d 次（factory %d 次）⇒ 之后的分歧都是"早逝的影子"'
                 % (len(fb), len(fa)))
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', required=True, help='-d exec 原始日志（factory 侧）')
    ap.add_argument('--ours', required=True, help='-d exec 原始日志（rebuild 侧）')
    ap.add_argument('--factory-elf', default='golden/factory.rkgame.bin')
    ap.add_argument('--ours-elf', default='build/rkgame.rebuilt.elf')
    ap.add_argument('--anchor', default=None, help='锚点符号（默认 main）')
    ap.add_argument('--label', default='')
    ap.add_argument('--out', default=None)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    for p in (a.factory, a.ours, a.factory_elf, a.ours_elf):
        if not os.path.exists(p):
            print('  [skip] 缺文件：%s' % p)
            return 3

    fr, fs = elf_exec_ranges_and_syms(a.factory_elf)
    orr, os_ = elf_exec_ranges_and_syms(a.ours_elf)
    pf, tf = read_trace(a.factory, fr)
    pr, tr = read_trace(a.ours, orr)
    if not pf or not pr:
        print('  [skip] 主程序代码段内的执行数为 0（factory=%d / rebuild=%d）' % (len(pf), len(pr)))
        return 3

    nf = normalize(pf, fs)
    nr = normalize(pr, os_)

    L = []
    L.append('== 执行轨迹对齐（exec_align）%s ==' % (('（' + a.label + '）') if a.label else ''))
    L.append('  轨迹总行数：factory %d / rebuild %d' % (tf, tr))
    L.append('  落在**主程序自身代码段**的执行数：factory %d / rebuild %d' % (len(pf), len(pr)))
    L.append('     （其余是 libc/ld.so 的帧 —— 两侧链的库不同，地址不可直接比 ⇒ 已过滤）')

    anchor, ia, ib = find_anchor(nf, nr, a.anchor)
    if anchor is None:
        L.append('')
        L.append('  ★ 无法定锚（两侧没有可用的共同非 CRT 符号）⇒ **INCONCLUSIVE**：')
        L.append('    不能判"无分歧" —— 那会是假绿。请用 --anchor 指定一个两侧都执行的符号。')
        txt = '\n'.join(L) + '\n'
        print(txt, end='')
        if a.out:
            os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
            open(a.out, 'w', encoding='utf-8', newline='\n').write(txt)
        return 3

    L.append('')
    L.append('  ★ 锚点 = `%s`（默认取两侧共有的业务代码起点；可用 --anchor 覆盖）' % anchor)
    L.append('     锚点**之前**（CRT/loader 前导）执行数：factory %d / rebuild %d ——'
             % (ia, ib))
    L.append('     两个不同二进制的 crt/ld 版本不同，**前导天然不同 ⇒ 不参与分歧判决**（只作记录）。')
    L.append('     ⚠️ 首跑教训（CI 20ba70e4）：不做锚点对齐时，三个视图**全部**报"第 0 次就不同"'
             '（factory `main+0x1ec` vs rebuild `_init+0x8`）⇒ 报告退化成废话。')

    sf, sr = nf[ia:], nr[ib:]
    tfa, trb = transitions(sf), transitions(sr)
    L.append('')
    L.append('  锚点之后：factory %d 次执行 / %d 次转移；rebuild %d 次执行 / %d 次转移'
             % (len(sf), len(tfa), len(sr), len(trb)))
    L.append('')
    L.append('  三个视图的**首个分歧点**（锚点之后）：')
    d1 = first_diff([x[1] for x in sf], [x[1] for x in sr])
    L += show_ctx('① 逐次执行（函数名+偏移）', [x[1] for x in sf], [x[1] for x in sr], d1)
    L.append('')
    d2 = first_diff([x[0] for x in sf], [x[0] for x in sr])
    L += show_ctx('② 按函数名（丢偏移）', [x[0] for x in sf], [x[0] for x in sr], d2)
    L.append('')
    d3 = first_diff(tfa, trb)
    L += show_ctx('③ 按函数转移（折叠连续重复）', tfa, trb, d3)
    L.append('')

    # 锚点之后的"只在一侧出现"的符号（排除 CRT）—— 比逐次对齐更抗噪声
    setf = {x[0] for x in sf if not is_crt(x[0])}
    setr = {x[0] for x in sr if not is_crt(x[0])}
    only_f = sorted(setf - setr)
    only_r = sorted(setr - setf)
    L.append('  锚点之后的**符号集合差集**（排除 CRT 样板）：')
    L.append('     仅 factory 执行（%d 个）：%s' % (len(only_f), ', '.join(only_f[:14]) or '（无）'))
    L.append('     仅 rebuild 执行（%d 个）：%s' % (len(only_r), ', '.join(only_r[:14]) or '（无）'))
    L.append('')
    L.append('  ★ 读法（顺序不能反）：')
    L.append('     1) 先看**两侧锚点后的长度**与终止状态 —— 一侧若提前结束，后面的分歧都是"早逝的影子"；')
    L.append('     2) 再看 ② 与 ③（按函数名/转移）—— 它们才是"高层路径是否走偏"的判据；')
    L.append('     3) ① 只用于定位"同一函数内的哪一段"；')
    L.append('     4) ③ 的首个分歧点往往是最有用的一个：它给出"两侧最后一次在同一个函数里"的位置。')
    txt = '\n'.join(L) + '\n'
    print(txt, end='')
    if a.out:
        os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
        open(a.out, 'w', encoding='utf-8', newline='\n').write(txt)
    return 1 if (d1 >= 0 or d2 >= 0 or d3 >= 0) else 0


# ---------------------------------------------------------------- selftest
def selftest():
    """★ 仪器自证（正负双向）。锚点人工核对过。

    为什么必须有：本工具的"过滤 + 归一 + 定锚"三环都极易**悄悄失效** ——
    过滤区间写错 ⇒ 序列为空（看起来"无分歧"）；归一写错 ⇒ 序列恒不同；
    定锚写错 ⇒ 又把 CRT 前导算进判决（**首跑就是这样错的**）。三者都会产出"看起来正常"的输出。
    """
    cases = [
        # (a, b, 期望 first_diff)
        (['A', 'B', 'C'], ['A', 'B', 'C'], -1, '完全一致 ⇒ -1'),
        (['A', 'B', 'C'], ['A', 'X', 'C'], 1, '第 1 次分歧'),
        (['A', 'B'], ['A', 'B', 'C'], 2, '一方是另一方前缀 ⇒ 返回较短长度'),
        (['A', 'B', 'C'], ['A', 'B'], 2, '反向前缀 ⇒ 同样返回 2'),
        ([], ['A'], 0, '空序列 vs 非空 ⇒ 0'),
    ]
    print('=' * 78)
    print('exec_align 自证（对齐原语 + 归一 + 定锚）')
    print('=' * 78)
    bad = 0
    for a, b, want, note in cases:
        got = first_diff(a, b)
        ok = (got == want)
        bad += (not ok)
        print('  %-6s %-16s vs %-16s → %-3s (期望 %-3s)  %s'
              % ('✓' if ok else '★FAIL', a, b, got, want, note))

    syms = [(0x1000, 'Foo'), (0x1100, 'Bar')]
    got = normalize([0x1004, 0x1104], syms)
    want = [('Foo', 'Foo+0x4'), ('Bar', 'Bar+0x4')]
    ok = (got == want)
    bad += (not ok)
    print('  %-6s 归一化 [0x1004,0x1104] → %s (期望 %s)' % ('✓' if ok else '★FAIL', got, want))

    got = transitions([('A', ''), ('A', ''), ('B', ''), ('B', ''), ('A', '')])
    want = ['A', 'B', 'A']
    ok = (got == want)
    bad += (not ok)
    print('  %-6s 转移折叠 → %s (期望 %s)' % ('✓' if ok else '★FAIL', got, want))

    # ---- CRT 过滤 ----
    crt_names = ['_init', '_start', '__libc_csu_init', '__ARMv7ABSLongThunk_memcpy',
                 'frame_dummy', '@nosym', '__gnu_thumb1_case_uqi']
    non_crt = ['main', 'mui_menu', 'ReadUSBJoy']
    got = [is_crt(n) for n in crt_names + non_crt]
    want = [True] * len(crt_names) + [False] * len(non_crt)
    ok = (got == want)
    bad += (not ok)
    print('  %-6s CRT 识别（%d 个应真 / %d 个应假）→ %s'
          % ('✓' if ok else '★FAIL', len(crt_names), len(non_crt), '正确' if ok else got))

    # ---- 定锚：★ 首跑踩的坑就是这里 ----
    # 构造与实测同形的前导：factory 以 main 开头，rebuild 以 _init 开头
    nf = [('main', 'main+0x1ec'), ('main', 'main+0x200'), ('mui_menu', 'mui_menu+0x0')]
    nr = [('_init', '_init+0x8'), ('__libc_csu_init', 'x'),
          ('main', 'main+0x10'), ('main', 'main+0x20'), ('mui_menu', 'mui_menu+0x0')]
    an, ia_, ib_ = find_anchor(nf, nr)
    ok = (an == 'main' and ia_ == 0 and ib_ == 2)
    bad += (not ok)
    print('  %-6s 定锚（默认 main）→ %s @factory[%d] / rebuild[%d] (期望 main @0 / @2)'
          % ('✓' if ok else '★FAIL', an, ia_, ib_))
    sf, sr = nf[ia_:], nr[ib_:]
    got = first_diff([x[0] for x in sf], [x[0] for x in sr])
    ok = (got == -1)
    bad += (not ok)
    print('  %-6s ★ 锚点之后应**无分歧**（前导差异不得算进判决）→ %s (期望 -1)'
          % ('✓' if ok else '★FAIL', got))

    # ---- 定不到锚 ⇒ 必须 INCONCLUSIVE（不许假绿）----
    an2, _, _ = find_anchor([('_init', 'x')], [('_init', 'y')])
    ok = (an2 is None)
    bad += (not ok)
    print('  %-6s 两侧只有 CRT 符号 ⇒ 定不到锚（必须 INCONCLUSIVE，不许假绿）→ %s'
          % ('✓' if ok else '★FAIL', an2))

    print('-' * 78)
    print('  结论：%s' % ('★ 有锚点未通过 ⇒ 判据不可信，必须修' if bad else '全部锚点通过 ✓'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
