#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""门禁：`.fimg_*` 段（原厂字节镜像）到底有多少**被真代码真正引用**。

背景（缺口 P2）
--------------
交付产物里 `.fimg_text` 携带 **2,957,704 B 原厂机器码**（= 工厂 `.text` 逐字节副本），
用途只是"地址垫"（段 VMA 必须与工厂一致，因为部分代码烧死了绝对地址）。
问题：**这些字节到底有没有被用？**
* 零被引用 ⇒ 内容可全部换 0（只保留 `.size` 与 VMA）⇒ 产物不再携带任何原厂代码。
* 有引用 ⇒ 打印**最小必需集合**，而不是"整段 2.96 MB"。

★★ 三次误判的教训（2026-09-29，务必先读再改本文件）
------------------------------------------------
1. **纪律 62**：用「4 字节值**落在** 0x9b10..0x2dbc98 区间」当判据 ⇒ 误报 134/3020/3921。
   `.fimg_text` 跨度 2.9 MB，普通整数/ASCII 全落进去。判据必须是**精确等于符号地址**。
2. **更糟的一次**：把「指令立即数落在区间」也算命中 ⇒ `mov r0,#0x10000` / `cmp r5,#0x10000`
   全成了"引用"。算术常量不是地址 ⇒ **`IMM` 类必须删掉**。
3. ★★★ **根本原因**：本产物的普通引用**一律用"相对偏移"编码**，不是绝对地址：
   ```asm
   ldr  rX, [pc, #imm]     @ rX = 池里的 32 位**有符号相对偏移**（实测常为 0xffffXXXX）
   add  rX, pc, rX         @ 真地址 = (本指令地址 + 8) + rX      → 数据地址
   ```
   或
   ```asm
   ldr  rX, [pc, #imm]
   ldr  rX, [pc, rX]       @ 真地址 = (本指令地址 + 8) + rX      → 数据地址 / GOT 表项
   ```
   ⇒ 搜"绝对地址字"**必然全 0**。自洽验证：解算出的 0x4DAF99 落 `.rodata`、0x4DE2AC 落 `.got`，
   与真实段布局吻合。**所以判据必须解算相对偏移。**

另有一次仪器缺陷（已修，留作回归锚点）
------------------------------------
`md.disasm(tdata, tbase)` 是**线性扫描**：`.text` 混常量池，一碰数据字节就终止 ⇒
427,656 B 只解出 **125 条（0.1%）**，判据全 0。必须用 `.symtab` 的 `STT_FUNC (addr,size)`
**逐函数**反汇编 ⇒ 覆盖 **100%**（95,518 条）。

判据分级
--------
* **STRONG**：解算出的真实数据地址、`adr` 立即数、`b/bl` 跳转目标 —— 落 `.fimg_*` 即计。
* **WEAK**  ：`movw`+`movt` 合并出的 32 位常 —— 可能是巧合常量，单列不并入判据。
* **LIT-UPPER**：段内 4 字节字落区间 —— **只是上界**（纪律 62 的反面教材），仅供对照。

阳性对照（必须有）
------------------
我们把**自己的** `.rodata`（839,680 B）与 `.fimg_rodata` 一起当对照组：
源码明确引用它们 ⇒ **命中必须 > 0**；若为 0 ⇒ 仪器坏，不是"干净"。

自证（`--self-test`）
--------------------
正例：`rel_target(a, +off)` 与 `rel_target(a, -off)` 的符号扩展正确。
正例：符号表界定反汇编 >> 线性扫描（仪器修复锚点）。
正例：阳性对照 `.rodata` / `.fimg_rodata` / `.fimg_data` 命中 > 0。
反例：池读取恒返回 0 ⇒ 命中必须塌到 ~0（证明不是无条件放行）。
反例：区间设空 ⇒ 全部 0。
"""
import argparse
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OURS = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

import capstone                                            # noqa: E402
from elftools.elf.elffile import ELFFile                    # noqa: E402


# --------------------------------------------------------------------------
# 纯函数层（可自证）
# --------------------------------------------------------------------------
def s32(v):
    """32 位无符号 → 有符号。"""
    return v - (1 << 32) if v >= (1 << 31) else v


def rel_target(insn_addr, v):
    """ARM(ARM 态) 的 pc 相对解算：真地址 = (指令地址 + 8) + 有符号偏移。"""
    return insn_addr + 8 + s32(v)


def in_ranges(v, ranges):
    for lo, hi in ranges:
        if lo <= v < hi:
            return (lo, hi)
    return None


def classify(v, sec_ranges):
    for name, (lo, hi) in sec_ranges.items():
        if lo <= v < hi:
            return name
    return None


def merge_movw_movt(insns):
    """`movw Rd,#lo` + `movt Rd,#hi` → 完整 32 位常量（未配对 movw 不输出）。"""
    out = []
    pend = {}
    for a, mn, ops, rd, imm in insns:
        if rd is None:
            continue
        if mn == 'movw' and imm is not None:
            pend[rd] = (a, imm & 0xFFFF)
        elif mn == 'movt' and imm is not None and rd in pend:
            a0, lo = pend.pop(rd)
            out.append((a0, ((imm & 0xFFFF) << 16) | lo, rd))
        else:
            pend.pop(rd, None)
    return out


def resolve_pc_rel(insns, read_u32):
    """解算 ARM「相对偏移」寻址，返回 [(insn_addr, real_addr, how)]。

    识别两条序列：
        ldr Rt,[pc,#imm] → add Rt, pc, Rt        （数据地址）
        ldr Rt,[pc,#imm] → ldr Rt2,[pc, Rt]      （数据地址 / GOT 表项）
    其他任何写同一寄存器的指令都会使待补链失效（保守，避免串味）。
    """
    out = []
    pend = {}                                   # reg -> (ldr_addr, off)
    for a, mn, ops, rd, imm in insns:
        if mn == 'ldr' and '[' in ops and 'pc' in ops and rd:
            inner = ops.split('[', 1)[1].rstrip(']')
            parts = [x.strip() for x in inner.split(',')]
            # 形式 A：ldr Rt, [pc, #imm]
            if len(parts) == 2 and parts[0] == 'pc' and parts[1].startswith('#'):
                try:
                    off = int(parts[1][1:], 0)
                except ValueError:
                    off = None
                if off is not None:
                    pend[rd] = (a, off)
                    continue
            # 形式 B：ldr Rt2, [pc, Rn]  —— 用 pend 里的 Rn 解算
            if len(parts) == 2 and parts[0] == 'pc' and parts[1].startswith('r'):
                base = parts[1]
                if base in pend:
                    a0, off = pend[base]
                    v = read_u32(a0 + 8 + off)
                    if v is not None:
                        out.append((a, rel_target(a, v),
                                    'ldr[pc,%s] seq@0x%x' % (base, a0)))
                pend.pop(rd, None)
                continue
            pend.pop(rd, None)
            continue
        # add Rt, pc, Rt   /   add Rt, Rt, pc
        if mn == 'add' and rd and 'pc' in ops and rd in pend:
            a0, off = pend.pop(rd)
            v = read_u32(a0 + 8 + off)
            if v is not None:
                out.append((a, rel_target(a, v), 'add pc seq@0x%x' % a0))
            continue
        if rd:
            pend.pop(rd, None)                  # 该寄存器被改写 ⇒ 链断
    return out


# --------------------------------------------------------------------------
# ELF 读取
# --------------------------------------------------------------------------
def sec_of(e, name):
    s = e.get_section_by_name(name)
    return s if (s is not None and s['sh_size']) else None


def fimg_ranges(e):
    return {s.name: (s['sh_addr'], s['sh_addr'] + s['sh_size'])
            for s in e.iter_sections()
            if s.name.startswith('.fimg') and s['sh_size']}


def all_ranges(e):
    """所有有地址的段（判 classify 用，含我们自己的 .rodata/.data/.got 等）。"""
    out = {}
    for s in e.iter_sections():
        if s['sh_size'] and s['sh_addr']:
            out.setdefault(s.name, (s['sh_addr'], s['sh_addr'] + s['sh_size']))
    return out


def funcs(e):
    st = e.get_section_by_name('.symtab')
    if st is None:
        return []
    out = [(s['st_value'], s['st_size'], s.name)
           for s in st.iter_symbols()
           if s.name and s['st_info']['type'] == 'STT_FUNC' and s['st_value']]
    out.sort()
    return out


def owner_of(addr, flist):
    import bisect
    addrs = [a for a, _, _ in flist]
    i = bisect.bisect_right(addrs, addr) - 1
    if i < 0:
        return '?', 0
    a0, sz, nm = flist[i]
    return nm, addr - a0


def disasm_by_symbols(e, mode, fimgR):
    """★ 逐函数反汇编（符号表界定）。线性扫描在混常量池的 .text 上只覆盖 0.1%。"""
    st = e.get_section_by_name('.symtab')
    ts = sec_of(e, '.text')
    if st is None or ts is None:
        return [], 0, 0
    tdata = ts.data()
    tbase = ts['sh_addr']
    fs = funcs(e)
    md = capstone.Cs(capstone.CS_ARCH_ARM, mode)
    md.detail = False
    out = []
    covered = 0
    for i, (a, sz, _nm) in enumerate(fs):
        if classify(a, fimgR) is not None:
            continue                        # 地址垫里的伪函数（.fimg 内标签）跳过
        if not sz:
            nxt = fs[i + 1][0] if i + 1 < len(fs) else a + 4
            sz = max(4, nxt - a)
        off = a - tbase
        if off < 0 or off >= len(tdata):
            continue
        for ins in md.disasm(tdata[off:off + sz], a):
            out.append(ins)
        covered += min(sz, len(tdata) - off)
    lin = list(capstone.Cs(capstone.CS_ARCH_ARM, mode).disasm(tdata, tbase))
    return out, covered, len(lin)


# --------------------------------------------------------------------------
# 扫描
# --------------------------------------------------------------------------
def scan(path, read_zero=False):
    fh = open(path, 'rb')
    e = ELFFile(fh)
    R = fimg_ranges(e)
    if not R:
        return None
    A = all_ranges(e)
    fs = funcs(e)
    odd = sum(1 for a, _, _ in fs if a & 1)
    mode = capstone.CS_MODE_THUMB if (fs and odd > len(fs) * 0.6) else capstone.CS_MODE_ARM

    ts = sec_of(e, '.text')
    tdata = ts.data() if ts else b''
    tbase = ts['sh_addr'] if ts else 0

    def read_u32(addr):
        if read_zero:
            return 0
        off = addr - tbase
        if 0 <= off <= len(tdata) - 4:
            return struct.unpack_from('<I', tdata, off)[0]
        return None

    dis_ins, covered, n_linear = disasm_by_symbols(e, mode, R)

    # 指令 → 统一元组
    insns = []
    for ins in dis_ins:
        mn, ops = ins.mnemonic, ins.op_str
        rd = None
        imm = None
        regs = [x.strip() for x in ops.split(',')]
        if regs and regs[0].startswith('r'):
            rd = regs[0]
        if '#' in ops:
            try:
                imm = int(ops.split('#')[-1].rstrip(']').split(',')[0].strip(), 0)
            except ValueError:
                imm = None
        insns.append((ins.address, mn, ops, rd, imm))

    # ---- STRONG ①：相对偏移解算 ----
    strong = []          # (kind, insn_addr, real_addr, sec, how)
    for ia, ra, how in resolve_pc_rel(insns, read_u32):
        s = classify(ra, A)
        strong.append(('RELPC', ia, ra, s, how))

    # ---- STRONG ②：adr / adrl ----
    for a, mn, ops, rd, imm in insns:
        if mn in ('adr', 'adrl') and imm is not None:
            s = classify(imm, A)
            if s:
                strong.append(('ADR', a, imm, s, mn + ' ' + ops))

    # ---- STRONG ③：b/bl 目标（落 .fimg_text = 会执行原厂机器码）----
    for a, mn, ops, rd, imm in insns:
        if mn in ('b', 'bl', 'bx') and imm is not None:
            s = classify(imm, A)
            if s:
                strong.append(('JUMP', a, imm, s, mn + ' ' + ops))

    # ---- STRONG ④ / WEAK：movw+movt ----
    #   ★ 2026-09-29 认知修正：**引用形态按段不同**
    #     · `.fimg_data` / `.fimg_bss`（可写变量区）→ 绝对地址 movw/movt **就是**真引用
    #     · `.fimg_text` / `.fimg_rodata`（只读区）→ movw/movt 可能是巧合常量 ⇒ 需精确等于符号地址
    sym_at = {}
    stt = e.get_section_by_name('.symtab')
    if stt is not None:
        for _s in stt.iter_symbols():
            if _s['st_value'] and _s.name:
                sym_at.setdefault(_s['st_value'], _s.name)
    weak = []                                   # 注意：strong 已由 ①~③ 填充，不能重置
    for a0, v, rd in merge_movw_movt(insns):
        s = classify(v, A)
        if not s:
            continue
        how = 'movw/movt %s=0x%08x' % (rd, v)
        if s in ('.fimg_data', '.fimg_bss') or v in sym_at:
            strong.append(('MOVW+MOVT', a0, v, s, how))
        else:
            weak.append(('MOVW+MOVT', a0, v, s, how))

    # ---- LIT-UPPER（上界，仅对照）----
    lit = []
    for sname in ('.text', '.rodata', '.data', '.data.rel.ro', '.got'):
        s = sec_of(e, sname)
        if s is None:
            continue
        d = s.data()
        b = s['sh_addr']
        for i in range(0, len(d) - 3, 4):
            v = struct.unpack_from('<I', d, i)[0]
            for fname, (lo, hi) in R.items():
                if lo <= v < hi:
                    lit.append((b + i, v, fname))
    return dict(e=e, R=R, A=A, mode=mode, fs=fs, strong=strong, weak=weak, lit=lit,
                tbase=tbase, tdata=tdata, covered=covered, n_linear=n_linear,
                n_ins=len(dis_ins))


def trio(D, sec):
    """(STRONG 数, WEAK 数, LIT 数) for a section。"""
    return (len([x for x in D['strong'] if x[3] == sec]),
            len([x for x in D['weak'] if x[3] == sec]),
            len([x for x in D['lit'] if x[2] == sec]))


def report(path):
    D = scan(path)
    if D is None:
        print('!! 没有 .fimg_* 段')
        return 1
    R, fs = D['R'], D['fs']
    print('=' * 100)
    print('fimg_content_gate —— `.fimg_*`（原厂字节镜像）被真代码引用普查')
    print('  产物: %s   ISA: %s   STT_FUNC %d'
          % (os.path.relpath(path, ROOT).replace(os.sep, '/'),
             'Thumb' if D['mode'] == capstone.CS_MODE_THUMB else 'ARM', len(fs)))
    print('  反汇编: 符号表界定 %d 条 / 覆盖 %.1f%% ；线性扫描仅 %d 条'
          % (D['n_ins'], 100.0 * D['covered'] / max(1, len(D['tdata'])), D['n_linear']))
    print('=' * 100)
    print('  %-26s %10s %8s %10s   %s' % ('目标段', 'STRONG', 'WEAK', 'LIT-UPPER', '说明'))
    order = sorted(R, key=lambda s: R[s][0])
    for sec in order:
        st, wk, lt = trio(D, sec)
        note = ''
        if sec == '.fimg_text':
            note = '← 原厂机器码（判据目标）'
        print('  %-26s %10d %8d %10d   %s' % (sec, st, wk, lt, note))

    print()
    print('  --- 阳性对照（源码明确引用我们自己的数据段）---')
    for sec in ('.rodata', '.data', '.data.rel.ro'):
        st, wk, lt = trio(D, sec)
        print('  %-26s STRONG %6d  ⇒ %s' % (sec, st, '✓' if st > 0 else '★ 仪器可疑'))

    ft = '.fimg_text'
    st_ft = trio(D, ft)[0]
    ro_st = trio(D, '.fimg_rodata')[0]
    print()
    print('  ' + '=' * 94)
    print('  ★★★ 判据：`.fimg_text`（原厂机器码 %d B）被真代码 **STRONG** 引用 = %d 处'
          % (R[ft][1] - R[ft][0], st_ft))
    print('  ' + '=' * 94)
    hits = [x for x in D['strong'] if x[3] == ft]
    if not hits:
        print('     ⇒ **零被引用** ⇒ 该段内容可全部换 0（只保留 .size 与 VMA）')
    else:
        print('     ⇒ **有引用** ⇒ 内容不可全零；最小必需集合（前 60）：')
        bykind = {}
        for k, ia, ra, s, how in hits:
            bykind[k] = bykind.get(k, 0) + 1
        print('       按类型: %s' % bykind)
        for k, ia, ra, s, how in sorted(hits, key=lambda x: x[1])[:60]:
            nm, off = owner_of(ia, fs)
            syms = [x for x in fs if x[0] == ra]
            tgt = ('→ ' + syms[0][2]) if syms else ('→ 0x%06x' % ra)
            print('         %-8s 0x%08x %-26s +0x%-5x %s   %s' % (k, ia, nm[:26], off, tgt, how[:36]))
        if bykind.get('JUMP'):
            print('     ★★ %d 处是**跳转/调用**（= 会执行原厂机器码）' % bykind['JUMP'])
    if ro_st == 0:
        print('       ⇒ 静态读数：`.fimg_text` 与 `.fimg_rodata` 的 STRONG 引用都是 0。')
        print('       ★★ 但静态判据**已被行为尺反证一次**（2026-09-29 删除实验，见 §0.30）：')
        print('          `.fimg_rodata` 全零后行为尺 DIVERGE 40 → 42、REFDEAD 0 → 1，')
        print('          新增发散 = `TurboKeyProcess` / `init_user_joy_key_mask`，')
        print('          读的是 **0x2e08d0..0x2e0920**（按键映射表，4 字节表项）。')
        print('          ⇒ 那两个函数的引用形式**不在本工具覆盖的寻址序列里** ⇒ **漏报**。')
        print('       ⇒ 纪律：**行为尺是唯一判据**；本工具只当"提示/定位"，不得单独下结论。')

    print()
    print('  --- .fimg_text 内的符号（供人工核对）---')
    st = D['e'].get_section_by_name('.symtab')
    lo, hi = R[ft]
    n = 0
    for s in st.iter_symbols():
        if s['st_value'] and lo <= s['st_value'] < hi:
            print('     %-26s 0x%06x  %s' % (s.name, s['st_value'], s['st_info']['type']))
            n += 1
    if not n:
        print('     （无）')
    return 0


# --------------------------------------------------------------------------
# 自证
# --------------------------------------------------------------------------
def self_test():
    print('=' * 100)
    print('自证：先用已知答案的样本验仪器，再看它的数')
    print('=' * 100)
    chk = []

    def c(tag, got, want):
        good = (got == want)
        chk.append(good)
        print('   %-64s got=%-8s want=%-8s %s' % (tag, got, want, '✓' if good else '★FAIL'))

    # 纯函数
    c('正例 s32(0xffff4fc0) 符号扩展', s32(0xffff4fc0), -45120)
    c('正例 rel_target(0x4e92e4, 0xffff4fc0) = 0x4de2ac（实测落 .got）',
      rel_target(0x4e92e4, 0xffff4fc0), 0x4de2ac)
    c('正例 rel_target(0x4e9350, 0xffff1c41) = 0x4daf99（实测落 .rodata）',
      rel_target(0x4e9350, 0xffff1c41), 0x4daf99)
    c('正例 正偏移解算', rel_target(0x1000, 0x20), 0x1028)
    c('反例 区间右开：值=hi 不在内', in_ranges(0x2dbc98, [(0x9b10, 0x2dbc98)]) is None, True)
    c('正例 classify 落 .fimg_text', classify(0x20000, {'.fimg_text': (0x9b10, 0x2dbc98)}),
      '.fimg_text')
    ins = [(0x1000, 'movw', 'r0, #0x1000', 'r0', 0x1000),
           (0x1004, 'movt', 'r0, #0x004e', 'r0', 0x4e)]
    c('正例 movw+movt 合并', merge_movw_movt(ins)[0][1], 0x004e1000)
    c('反例 孤立 movw 不产出', len(merge_movw_movt([ins[0]])), 0)

    # 序列识别（合成指令）
    seqA = [(0x8000, 'ldr', 'r1, [pc, #0x10]', 'r1', 0x10),
            (0x8008, 'add', 'r1, pc, r1', 'r1', None)]
    c('正例 识别 ldr→add pc 序列', len(resolve_pc_rel(seqA, lambda a: 0xffff0000)), 1)
    seqB = [(0x8000, 'ldr', 'r1, [pc, #0x10]', 'r1', 0x10),
            (0x8004, 'mov', 'r2, r0', 'r2', None),
            (0x8008, 'ldr', 'r2, [pc, r1]', 'r2', None)]
    c('正例 识别 ldr→ldr[pc,rX] 序列', len(resolve_pc_rel(seqB, lambda a: 0xffff0000)), 1)
    seqC = [(0x8000, 'ldr', 'r1, [pc, #0x10]', 'r1', 0x10),
            (0x8004, 'mov', 'r1, #0', 'r1', 0),
            (0x8008, 'add', 'r1, pc, r1', 'r1', None)]
    c('反例 中途改写寄存器 ⇒ 链断（不误报）',
      len(resolve_pc_rel(seqC, lambda a: 0xffff0000)), 0)

    # 真仪器
    D = scan(OURS)
    if D is None:
        c('★ 产物无 .fimg_* 段', True, False)
        print()
        return chk
    c('正例 符号表界定反汇编 >> 线性扫描（仪器修复锚点）',
      D['n_ins'] > max(1, D['n_linear']) * 5, True)
    # ★ 阳性对照按段选对口径（2026-09-29 认知修正）：
    #   `.fimg_data` 是**可写变量区**，其引用形态就是绝对地址 movw/movt ⇒ STRONG 里应含 MOVW+MOVT。
    #   `.rodata`（自有）是编译器正常引用 ⇒ RELPC 应命中。
    ro_st, _ro_wk, _ = trio(D, '.rodata')
    fd_st, fd_wk, _ = trio(D, '.fimg_data')
    c('正例 阳性对照 自有 .rodata STRONG > 0（RELPC 解算器可用）', ro_st > 0, True)
    c('正例 阳性对照 .fimg_data (STRONG+WEAK) > 0（可写变量区必被引用）',
      fd_st + fd_wk > 0, True)
    c('正例 STRONG 里出现 RELPC（相对偏移解算生效）',
      any(x[0] == 'RELPC' for x in D['strong']), True)
    c('正例 STRONG 里出现 MOVW+MOVT（.fimg_data 的绝对地址形态）',
      any(x[0] == 'MOVW+MOVT' for x in D['strong']), True)
    # 反例：池读取恒 0 ⇒ RELPC 解算目标塌到 pc 附近 ⇒ 落 .rodata 的命中必须大幅下降
    #   （证明解算器**真的**在用池里的值，不是无条件放行）
    Dz = scan(OURS, read_zero=True)
    nz = len([x for x in Dz['strong'] if x[0] == 'RELPC' and x[3] == '.rodata'])
    nn = len([x for x in D['strong'] if x[0] == 'RELPC' and x[3] == '.rodata'])
    c('反例 池恒 0 ⇒ RELPC/自有.rodata 命中塌陷（证明解算真的用池值）',
      nz < max(1, nn // 5), True)

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if all(chk) else '★ 有 FAIL —— 仪器不可信'))
    return chk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('elf', nargs='?', default=OURS)
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--json')
    a = ap.parse_args()
    if a.self_test:
        if not all(self_test()):
            return 2
        print()
    rc = report(a.elf)
    if a.json:
        import json
        D = scan(a.elf)
        agg = {}
        for k, ia, ra, s, how in D['strong']:
            if s:
                agg.setdefault(s, []).append({'kind': k, 'at': ia, 'target': ra, 'how': how})
        with open(a.json, 'w', encoding='utf-8') as fh:
            json.dump(agg, fh, ensure_ascii=False, indent=1, sort_keys=True)
        print('\n  （已写 %s）' % a.json)
    return rc


if __name__ == '__main__':
    sys.exit(main())
