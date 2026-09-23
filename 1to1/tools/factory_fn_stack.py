#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""factory_fn_stack —— 工厂函数里「栈槽读/写」的离线分类器。

为什么需要它（GAP 17.00 的判定入口）
------------------------------------
`tools/dce_ref_diff.py` 会报出「源码里对工厂数据的引用在 -Os 下消失」的 Δ 清单，但
**Δ 只是待核清单**：一定要判定「那次写入在原厂是不是死的」。判定不能靠读 C 源码
（C 源码本身就是 Ghidra 的渲染，它已经把结构弄丢过一次），**只能回到工厂机器码**。

本工具做一件事：把某个工厂函数反汇编，列出所有「基址寄存器 = sp / fp(r11) / r7」且
**位移是常量**的访存，按偏移分别统计 **读（ldr/ldrb/ldrh/ldrsb/ldrsh/ldrd）** 与
**写（str/strb/strh/strd）**。

判据
----
* 某偏移 **写了但从不读** ⇒ 该槽在原厂就是死的 ⇒ Δ 属**合法 DCE**。
* 某偏移 **既写又读** ⇒ 该槽有意义 ⇒ 若我们的 -Os 把它消掉 ⇒ **真缺陷**（UB-DCE 或丢读）。

用法
----
    python tools/factory_fn_stack.py --fn mui_load_state
    python tools/factory_fn_stack.py --addr 0x2eac8 --size 0x858
    python tools/factory_fn_stack.py --fn mui_load_state --slots 0xb8,0xb4
    python tools/factory_fn_stack.py --self-test

依赖：capstone（pip install capstone）。工厂 ELF 默认取 golden/factory.rkgame.bin，
函数地址/大小取自 D:/output/rkgame/decompiled/01-static/symtab.txt（objdump -t 格式）。
"""
import argparse
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTORY = os.environ.get('FACTORY_ELF', os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
SYMTAB = os.environ.get('FACTORY_SYMTAB',
                        r'D:/output/rkgame/decompiled/01-static/symtab.txt')

READ_MNEMONICS = ('ldr', 'ldrb', 'ldrh', 'ldrsb', 'ldrsh', 'ldrd', 'ldrt', 'ldrbt', 'ldrht')
WRITE_MNEMONICS = ('str', 'strb', 'strh', 'strd', 'strt', 'strbt', 'strht')
BASE_REGS = ('sp', 'fp', 'r11', 'r7', 'r13')


# ------------------------------------------------------------------ ELF 支持
class Elf32(object):
    def __init__(self, path):
        self.b = open(path, 'rb').read()
        b = self.b
        e_phoff, = struct.unpack_from('<I', b, 0x1c)
        self.e_phentsize, self.e_phnum = struct.unpack_from('<HH', b, 0x2a)
        self.loads = []
        for i in range(self.e_phnum):
            o = e_phoff + i * self.e_phentsize
            t, off, va, pa, fsz, msz, fl, al = struct.unpack_from('<8I', b, o)
            if t == 1:
                self.loads.append((va, off, fsz))

    def v2f(self, va):
        for va0, off, fsz in self.loads:
            if va0 <= va < va0 + fsz:
                return off + (va - va0)
        return None


def parse_symtab(path=SYMTAB):
    """objdump -t 格式：`0002eac8 g     F .text\\t00000858              mui_load_state`"""
    out = {}
    if not os.path.exists(path):
        return out
    rex = re.compile(r'^([0-9a-f]{8})\s+\S+\s+\S+\s+(\S+)\s+([0-9a-f]{8})\s+(\S+)\s*$')
    for line in open(path, encoding='utf-8', errors='replace'):
        m = rex.match(line.rstrip('\n'))
        if not m:
            continue
        addr, sec, size, name = m.groups()
        if sec.startswith('.text') and int(size, 16) > 0:
            out.setdefault(name, (int(addr, 16), int(size, 16)))
    return out


# ------------------------------------------------------------------ 栈访问
def stack_slots(code, base_addr, mode_thumb=False):
    """返回 {offset: {'r': n, 'w': n, 'w_addrs': [...]}}，只统计常量位移的 sp/fp 访存。"""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM,
                     capstone.CS_MODE_THUMB if mode_thumb else capstone.CS_MODE_ARM)
    md.detail = True
    slots = {}
    for ins in md.disasm(code, base_addr):
        mn = ins.mnemonic.split('.')[0]
        if mn not in READ_MNEMONICS and mn not in WRITE_MNEMONICS:
            continue
        if not ins.operands:
            continue
        mem = None
        for op in ins.operands:
            if op.type == capstone.arm.ARM_OP_MEM:
                mem = op.mem
                break
        if mem is None:
            continue
        base = ins.reg_name(mem.base) if mem.base else ''
        if base not in BASE_REGS:
            continue
        if mem.index:
            continue                      # 只有寄存器+寄存器（无常量位移）⇒ 跳过
        off = mem.disp
        if off < 0:                       # fp 负位移（frame pointer 向下）按绝对值记
            off = -off
        e = slots.setdefault(off, {'r': 0, 'w': 0, 'w_at': []})
        if mn in READ_MNEMONICS:
            e['r'] += 1
        else:
            e['w'] += 1
            e['w_at'].append('0x%x' % ins.address)
    return slots


def report(fn=None, addr=None, size=None, only=None, thumb=False):
    syms = parse_symtab()
    if addr is None:
        if fn not in syms:
            print('  ★ symtab 里找不到函数 %r；可用 --addr' % fn)
            return 2
        addr, size = syms[fn]
    if not size:
        size = 0x1000
    e = Elf32(FACTORY)
    off = e.v2f(addr)
    if off is None:
        print('  ★ 地址 0x%x 不落在任何 PT_LOAD' % addr)
        return 2
    code = e.b[off:off + size]
    slots = stack_slots(code, addr, thumb)

    print('=' * 96)
    print('工厂函数栈槽访问  fn=%s  addr=0x%x  size=0x%x  指令字节=%d' %
          (fn or '-', addr, size, len(code)))
    print('=' * 96)
    if not slots:
        print('  （没有常量位移的 sp/fp 访存）')
        return 0
    keys = sorted(slots)
    if only:
        want = set(int(x, 16) for x in only.split(','))
        keys = [k for k in keys if k in want]
    print('  %-10s %6s %6s   %s' % ('偏移', '读', '写', '判定'))
    for k in keys:
        s = slots[k]
        if s['w'] and not s['r']:
            verdict = '★ 写了从不读（原厂也是死槽）'
        elif s['r'] and not s['w']:
            verdict = '只读（可能是入参拷贝区）'
        else:
            verdict = '既写又读 ⇒ 有意义'
        print('  0x%-8x %6d %6d   %s' % (k, s['r'], s['w'], verdict))
    n_dead = sum(1 for k in slots if slots[k]['w'] and not slots[k]['r'])
    n_live = sum(1 for k in slots if slots[k]['r'])
    print()
    print('  小结：%d 个槽有常量位移访存；其中「写但从不读」%d 个；「被读」%d 个'
          % (len(slots), n_dead, n_live))
    return 0


def self_test():
    """用一段**手算过答案**的 ARM 指令流验仪器。"""
    import capstone
    print('=' * 96)
    print('自证：用手算过答案的指令流验仪器')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-56s got=%-16s %s' % (tag, got, '✓' if good else '★ FAIL'))

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    # 手写：str r3,[sp,#0xb8] / ldr r3,[sp,#0xb4] / str r2,[sp,#0xb4] / ldr r1,[r0,#4]
    code = (b'\x2d\x30\x8d\xe5'      # str r3,[sp,#0x2d]?? -> 用汇编器更稳，这里用已知编码
            )
    # 直接构造编码更可控：
    #   str r3,[sp,#0xb8] = E58D30B8  -> bytes b8 30 8d e5
    #   ldr r3,[sp,#0xb4] = E59D30B4  -> b4 30 9d e5
    #   str r2,[sp,#0xb4] = E58D20B4  -> b4 20 8d e5
    #   ldr r1,[r0,#4]    = E5901004  -> 04 10 90 e5   (base r0 ⇒ 不计)
    code = (b'\xb8\x30\x8d\xe5' + b'\xb4\x30\x9d\xe5' + b'\xb4\x20\x8d\xe5' + b'\x04\x10\x90\xe5')
    txt = '\n'.join('     %s' % i.mnemonic + ' ' + i.op_str for i in md.disasm(code, 0x1000))
    print(txt)
    s = stack_slots(code, 0x1000)
    chk('sp+0xb8 写 1 读 0', (s.get(0xb8, {}).get('w'), s.get(0xb8, {}).get('r')), (1, 0))
    chk('sp+0xb4 写 1 读 1', (s.get(0xb4, {}).get('w'), s.get(0xb4, {}).get('r')), (1, 1))
    chk('bas=r0 不计入', 4 in s, False)
    chk('槽数 = 2', len(s), 2)

    # 反例：ldr r1,[r0,r2]（寄存器索引，无常量位移）必须被跳过
    code2 = b'\x02\x10\x90\xe7'      # ldr r1,[r0,r2]
    chk('寄存器索引寻址 → 跳过', len(stack_slots(code2, 0x2000)), 0)

    # 反例：fp 负位移按绝对值归并
    #   ldr r3,[r11,#-0x20] = E51B3020 -> 20 30 1b e5
    code3 = b'\x20\x30\x1b\xe5'
    s3 = stack_slots(code3, 0x3000)
    chk('fp 负位移归并到 0x20', sorted(s3), [0x20])

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fn')
    ap.add_argument('--addr')
    ap.add_argument('--size')
    ap.add_argument('--slots', help='只看这些偏移，逗号分隔十六进制')
    ap.add_argument('--thumb', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return 0 if self_test() else 2
    return report(a.fn, int(a.addr, 16) if a.addr else None,
                  int(a.size, 16) if a.size else None, a.slots, a.thumb)


if __name__ == '__main__':
    sys.exit(main())
