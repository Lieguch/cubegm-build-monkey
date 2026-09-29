#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""abi_shift_screen —— 筛查"参数被编译器删掉导致 ABI 位移"的函数（假发散嫌疑）。

为什么需要它（2026-09-27，本轮根因）：
  LLVM 会把**内部函数（static）开头未使用的参数删掉**并把剩余参数**左移一个寄存器**。
  实测最小复现（build/_probe_arg/q.c，同一 zig/clang、-Os）：
      static int t_unused(conv_t conv, const char*s, size_t n, ucs4_t*pwc)  ← conv 未使用
          ⇒ 编译后 **s 在 r1、n 在 r2**（ABI 左移一格）
      static int t_used  (conv_t conv, const char*s, size_t n, ucs4_t*pwc)  ← conv 被使用
          ⇒ 编译后 **conv 在 r0、s 在 r1、n 在 r2**（正确）
  工厂用 GCC 6.2，**没有**做这件事（`cns11643_1_mbtowc` 把 r0..r3 全存进栈）。
  ⇒ 逐函数对拍会因此产出**假发散**：同一份 r0..r3 喂进去，两侧读的寄存器位置不同。

判据（纯静态、可复算）：
  取函数**前 N 条指令**，看 **r0 是否作为源被读过**。
    · 两侧都读 r0，或都不读 ⇒ 无位移嫌疑（'same'）
    · 仅工厂读 r0、我方不读 ⇒ **嫌疑 MINE_SHIFTED**（我方首参被删/未用）
    · 仅我方读 r0、工厂不读 ⇒ **嫌疑 FACTORY_SHIFTED**
  只看前 N 条是因为参数使用/入栈通常发生在**序言**。

用法: python tools/abi_shift_screen.py --names <每行一个函数名> [--n 12]
"""
import argparse
import sys

from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, CS_MODE_LITTLE_ENDIAN

FACTORY = 'golden/factory.rkgame.bin'


def load(path):
    e = ELFFile(open(path, 'rb'))
    fns = {}
    st = e.get_section_by_name('.symtab')
    if st is None:
        return e, fns
    for s in st.iter_symbols():
        if s.name and s['st_info']['type'] == 'STT_FUNC' and s['st_size'] > 0:
            va = s['st_value'] & ~1
            if s.name not in fns:
                fns[s.name] = (va, s['st_size'], bool(s['st_value'] & 1), s['st_shndx'])
    return e, fns


def prologue_read_set(e, info, n=14):
    """→ 序言里"先读后写"的寄存器集合（只到第一条分支/调用为止）。

    ★ 为什么是"先读后写"：参数在序言里被读取（用/存栈）时，目标寄存器通常还没被覆盖。
      指令形如 `ldrb r3,[r1]`：r1 是源（基址）⇒ r1 读过；r3 是目标 ⇒ 不算读。
    """
    va, size, thumb, shndx = info
    if not isinstance(shndx, int):
        return None
    sec = e.get_section(shndx)
    if sec is None:
        return None
    off = va - sec['sh_addr']
    code = sec.data()[off:off + max(size, 4)]
    md = Cs(CS_ARCH_ARM, (CS_MODE_THUMB if thumb else CS_MODE_ARM) | CS_MODE_LITTLE_ENDIAN)
    read, written = set(), set()
    cnt = 0
    for i in md.disasm(code, va):
        ops = [o.strip() for o in i.op_str.split(',')] if i.op_str else []
        # 源操作数（含 [] 基址）——粗略但一致地取"除第一个操作数外"的全部
        for o in ops[1:]:
            for r in ('r0', 'r1', 'r2', 'r3'):
                if r in o and r not in written:
                    read.add(r)
        # ★ store 类指令（str/strb/strh/strd）的**第一个操作数也是源**，不是目标。
        #   实测踩过：工厂序言是 `str r0,[r7,#0xc]`（把参数存栈）⇒ 旧版把它当"写 r0"
        #   ⇒ 工厂读集恒为空 ⇒ 整族被误判成 'unclear'（iconv 全族都中招）。
        _is_store = i.mnemonic.startswith('str') or i.mnemonic.startswith('push') or i.mnemonic.startswith('stm')
        if _is_store and ops:
            # store 的首操作数是**源**（如 `str r0,[r7,#0xc]` ⇒ 读 r0）
            for r in ('r0', 'r1', 'r2', 'r3'):
                if ops[0].strip() == r and r not in written:
                    read.add(r)
        if ops and not _is_store:
            d = ops[0]
            if not d.startswith('['):
                for r in ('r0', 'r1', 'r2', 'r3'):
                    if d == r:
                        written.add(r)
        cnt += 1
        if cnt >= n or i.mnemonic in ('bl', 'blx', 'b', 'bx'):
            break
    return read


def shift_of(fac_set, our_set):
    """→ ('none'|'mine_shifted'|'factory_shifted'|'unclear', 说明)

    判据：**"我方读到的寄存器集合"是否等于"工厂的集合整体下移一格"**。
      工厂 ABI 正确 ⇒ 读 {r0..rk}；我方首参被删 ⇒ 读 {r1..r(k+1)}。
      即 `our_set == {next(r) for r in fac_set}`。
    """
    order = ['r0', 'r1', 'r2', 'r3']
    nxt = {order[i]: order[i + 1] for i in range(3)}

    def down(s):
        return {nxt[r] for r in s if r in nxt}
    if fac_set is None or our_set is None:
        return 'unknown', ''
    if fac_set == our_set:
        return 'none', ''
    if our_set == down(fac_set):
        return 'mine_shifted', '工厂读 %s ⇒ 平移后 %s == 我方 %s' % (
            sorted(fac_set), sorted(down(fac_set)), sorted(our_set))
    if fac_set == down(our_set):
        return 'factory_shifted', '我方读 %s ⇒ 平移后 == 工厂 %s' % (
            sorted(our_set), sorted(fac_set))
    return 'unclear', '工厂 %s vs 我方 %s' % (sorted(fac_set), sorted(our_set))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--names', required=True)
    ap.add_argument('--ours', default='build/ab/lic16.elf')
    ap.add_argument('--n', type=int, default=12)
    a = ap.parse_args()

    names = [l.strip() for l in open(a.names, encoding='utf-8') if l.strip() and not l.startswith('#')]
    ef, ff = load(FACTORY)
    eo, fo = load(a.ours)
    cat = {'mine_shifted': [], 'factory_shifted': [], 'none': [], 'unclear': [], 'unknown': []}
    for nm in names:
        if nm not in ff or nm not in fo:
            cat['unknown'].append(nm)
            continue
        rf = prologue_read_set(ef, ff[nm], a.n)
        ro = prologue_read_set(eo, fo[nm], a.n)
        k, why = shift_of(rf, ro)
        cat.setdefault(k, []).append(nm if not why else '%s   (%s)' % (nm, why))
    print('筛查 %d 个函数（前 %d 条指令内是否读 r0）：' % (len(names), a.n))
    for k in ('mine_shifted', 'factory_shifted', 'none', 'unclear', 'unknown'):
        print('  %-18s %d' % (k, len(cat[k])))
        for nm in cat[k][:25]:
            print('       %s' % nm)
    return 0


if __name__ == '__main__':
    sys.exit(main())
