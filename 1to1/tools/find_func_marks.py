#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""find_func_marks.py — 提取某函数的「入口 / epilogue 候选 / 帧形状期望值」，供帧探针用。

背景（一次真实的、只有运行时能发现的 bug）：
  某个 callee 把**调用者的 fp(r11)** 写坏成 `fp|2`（它写"命令行第 2 个字"，而调用方把那两个字
  写成两个独立标量，编译器把它们排反了 ⇒ 那次写入越出标量、命中调用者帧里保存的 fp 槽）。
  上层于是用错的 fp 算帧基址，`pop {…,pc}` 按错位读栈、跳到不可映射地址 ⇒ SIGSEGV。
  编译 / 链接 / 全部静态门禁都是绿的。

因此 `tools/ci_qemu_behav.sh` 用 qemu 的 gdbstub 在**入口**与**epilogue**各停一次，校验：
      epilogue 处 `fp - sp` 必须 == 期望值
（epilogue 处 `sub sp, fp, #N` 尚未执行，故 `$sp` 就是帧基址；两值独立，校验非平凡。）

★ 期望值**必须从 prologue 现算**，不能写死常量：
    · `push {r4..fp,lr}` → 压入 n 个寄存器 ⇒ 入口 sp - 4n 就是"保存区底"；
    · `add fp, sp, #M`（或 `mov fp, sp` ⇒ M=0）；
    · `sub sp, sp, #N` ⇒ 帧基址 = 保存区底 - N；
    ⇒ 期望 `fp - 帧基址 = M + N`。
  ★ 实测教训：我第一次写死 0x128，改了一个局部变量后帧形状变成 0x130，门禁就**假红**了。

★ epilogue 必须给出**全部**候选：函数体里可能有多条返回路径，各带一份 `sub sp,fp,#N`+`pop {…,pc}`；
  只押"最后一条"会押错路径（实测踩过：断点永不命中，探针只测到入口，得出无意义的 0）。

输出（每行 key=value）:
  entry=0x…        入口地址
  expdiff=0x…      epilogue 处 fp - 帧基址 的期望值
  savedoff=0x…     保存寄存器区（r4）相对 fp 的负偏移（用于 dump）
  regs=<n>         压入的寄存器个数
  epi=0x…          epilogue 候选（可能多行）
取不到时退出码 3。

用法:
  python find_func_marks.py <elf> <funcname>
"""
import struct
import sys


def rot_imm(imm12):
    """★ ARM 数据处理立即数 = imm8 循环右移 (2*rot) —— 实测 `sub sp,sp,#0x114` 的
    imm12 读出来是 0xf45（不是 0x114）。直接用 `ins & 0xFFF` 会算错期望值，
    进而让帧门禁**假红**（本轮踩过）。"""
    imm8 = imm12 & 0xFF
    rot = (imm12 >> 8) & 0xF
    if rot == 0:
        return imm8
    return ((imm8 >> (2 * rot)) | (imm8 << (32 - 2 * rot))) & 0xFFFFFFFF


def load(path):
    d = open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    si = struct.unpack_from('<H', d, 50)[0]
    stroff = struct.unpack_from('<I', d, e_shoff + si * es + 16)[0]
    secs = {}
    for i in range(n):
        o = e_shoff + i * es
        sh = struct.unpack_from('<10I', d, o)
        e = d.index(b'\x00', stroff + sh[0])
        secs[d[stroff + sh[0]:e].decode('utf-8', 'replace')] = \
            dict(typ=sh[1], addr=sh[3], off=sh[4], size=sh[5], link=sh[6], entsz=sh[9])
    return d, secs


def find_sym(d, secs, name):
    st = secs['.symtab']
    es = struct.unpack_from('<H', d, 46)[0]
    stroff = struct.unpack_from('<I', d, struct.unpack_from('<I', d, 32)[0] + st['link'] * es + 16)[0]
    ent = st['entsz'] or 16
    for j in range(st['size'] // ent):
        o = st['off'] + j * ent
        nm, val, sz, info, other, shndx = struct.unpack_from('<IIIBBH', d, o)
        if nm == 0:
            continue
        e = d.index(b'\x00', stroff + nm)
        if d[stroff + nm:e].decode('utf-8', 'replace') == name:
            return val, sz
    return None, None


def main():
    if len(sys.argv) < 3:
        sys.stderr.write('用法: find_func_marks.py <elf> <funcname>\n')
        return 2
    elf, fname = sys.argv[1], sys.argv[2]
    d, secs = load(elf)
    entry, size = find_sym(d, secs, fname)
    if not entry or not size:
        sys.stderr.write('找不到符号或大小为 0: %s\n' % fname)
        return 3
    ta, to, tsz = secs['.text']['addr'], secs['.text']['off'], secs['.text']['size']
    if not (ta <= entry < ta + tsz):
        sys.stderr.write('符号不在 .text 内\n')
        return 3

    def word(ea):
        if ea + 4 > ta + tsz:
            return None
        return struct.unpack_from('<I', d, to + (ea - ta))[0]

    # ---- ① prologue：push{n} + add fp,sp,#M + sub sp,sp,#N ----
    nregs = 0
    M = None
    N = None
    for ea in range(entry, entry + 32, 4):
        ins = word(ea)
        if ins is None:
            break
        if (ins >> 24) == 0xE9 and ((ins >> 16) & 0xF) == 0xD and nregs == 0:
            mask = ins & 0xFFFF
            nregs = bin(mask).count('1')
            continue
        if M is None and (ins & 0xFFFFF000) == 0xE28DB000:      # add fp, sp, #imm
            M = rot_imm(ins & 0xFFF)
            continue
        if M is None and ins == 0xE1A0B00D:                     # mov fp, sp
            M = 0
            continue
        if M is not None and N is None and (ins & 0xFFFFF000) == 0xE24DD000:
            N = rot_imm(ins & 0xFFF)
            break
    if not nregs or M is None or N is None:
        sys.stderr.write('prologue 不是「push + add fp,sp,#M + sub sp,sp,#N」形态（无需帧探针）\n')
        return 3

    # ---- ② epilogue 候选：恢复 sp 且**紧跟**含 pc 的 pop/ldm ----
    def is_pop_pc(ins):
        if ins is None or (ins >> 24) != 0xE8 or ((ins >> 20) & 1) != 1:
            return False
        return bool((ins & 0xFFFF) >> 15)

    cands = []
    for ea in range(entry, entry + size, 4):
        ins = word(ea)
        if ins is None:
            break
        if ((ins & 0xFFFFF000) == 0xE24BD000 or ins == 0xE1A0D00B) and is_pop_pc(word(ea + 4)):
            cands.append(ea)
    if not cands:
        sys.stderr.write('未找到「恢复 sp + pop 含 pc」的 epilogue\n')
        return 3

    print('entry=0x%08x' % entry)
    print('expdiff=0x%x' % (M + N))
    print('savedoff=0x%x' % (4 * (nregs - 2)))
    print('regs=%d' % nregs)
    for a in cands:
        print('epi=0x%08x' % a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
