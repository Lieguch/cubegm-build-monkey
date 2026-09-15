#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""find_func_marks.py — 从一个 ELF 里取出某函数的「入口」与**所有** epilogue 地址。

为什么需要它：
  `tools/ci_qemu_behav.sh` 的「帧探针」要在 RKGAME 的某函数入口与 epilogue 各下一个 gdb 断点，
  用来校验 **fp(r11) 在函数执行期间必须不变**（实测：某个 callee 把调用者的 fp 写成 `fp|2`，
  上层于是用错的 `fp` 算帧基址，`pop {…,pc}` 跳到坏地址）。
  这两个地址**会随每次重链接漂移**；硬编码会指到别的函数上，让探针静默失去意义。

★ 必须返回**全部** epilogue 候选：一个函数体里可能有多条返回路径，各自带一份
  `sub sp, fp, #N` + `pop {…,pc}`。只押"最后一条"会押错路径（实测踩过：断点永不命中，
  探针只测到入口的 `fp-sp`，得出无意义的 0）。

判定方法：
  · 入口 = 符号表里该函数的值；
  · epilogue 候选 = 函数体内所有满足「`sub sp, fp, #imm`（0xE24BD0xx）或 `mov sp, fp`（0xE1A0D00B）」
    且**紧跟**一条含 pc 的 `pop/ldm` 的位置。要求"紧跟"，可排除字面量池里凑巧同形的数据字。

输出:
  第 1 行 = 入口地址；之后每行一个 epilogue 候选地址（十六进制）。
  取不到时退出码 3（调用方据此跳过探针）。

用法:
  python find_func_marks.py <elf> <funcname>
"""
import struct
import sys


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
    stra = struct.unpack_from('<I', d, 32)[0] + st['link'] * es + 16
    stroff = struct.unpack_from('<I', d, stra)[0]
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

    def is_pop_pc(ins):
        if ins is None:
            return False
        if (ins >> 24) != 0xE8:            # ldm/ldmib/... 单寄存器版
            return False
        if ((ins >> 20) & 1) != 1:         # L=1
            return False
        return bool((ins & 0xFFFF) >> 15)  # register list 含 pc

    cands = []
    for ea in range(entry, entry + size, 4):
        ins = word(ea)
        if ins is None:
            break
        sub_fp = (ins & 0xFFFFF000) == 0xE24BD000
        mov_fp = (ins == 0xE1A0D00B)
        if (sub_fp or mov_fp) and is_pop_pc(word(ea + 4)):
            cands.append(ea)
    if not cands:
        sys.stderr.write('未找到「恢复 sp + pop 含 pc」的 epilogue\n')
        return 3

    print('0x%08x' % entry)
    for a in cands:
        print('0x%08x' % a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
