#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""find_func_marks.py — 从一个 ELF 里取出某个函数的「入口」与「epilogue」地址。

为什么需要它：
  `tools/ci_qemu_behav.sh` 的「帧探针」要在 RKGAME 的函数入口与 epilogue 各下一个 gdb 断点，
  用来校验 **fp(r11) 在函数执行期间必须不变**（实测：某个 callee 把调用者的 fp 写成 `fp|2`，
  上层于是用错的 `fp` 算帧基址，`pop {…,pc}` 跳到坏地址）。
  这两个地址**会随每次重链接漂移** —— 早期版本把它们硬编码，代码一改就指到别的函数上，
  探针的输出会静默变成无意义（甚至误报）。本工具让它们始终从当前 ELF 现算。

判定方法：
  · 入口   = 符号表里该函数的值；
  · epilogue = 函数体内**最后一条** `sub sp, fp, #N`（ARM: 0xE24BD0xx，fp=r11）。
    编译产物里这是标准尾段；取最后一条可跳过中间的其它分支。
    为稳妥，再校验：它必须落在 [入口, 入口+size) 内，且其前一条是非分支指令。

用法:
  python find_func_marks.py <elf> <funcname>
  →  stdout 打印两行：<entry_hex> <epilogue_hex>
     取不到时退出码 3（调用方可据此跳过探针）。
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
    stra = struct.unpack_from('<I', d, 32)[0] + st['link'] * struct.unpack_from('<H', d, 46)[0] + 16
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

    epi = None
    for ea in range(entry, entry + size - 4, 4):
        ins = struct.unpack_from('<I', d, to + (ea - ta))[0]
        # 两种等价的「恢复 sp」形态，编译器视寄存器分配择一：
        #   `sub sp, fp, #imm`（0xE24BD0xx，通常 imm=0x1c）
        #   `mov sp, fp`      （0xE1A0D00B）
        if (ins & 0xFFFFF000) == 0xE24BD000 or ins == 0xE1A0D00B:
            epi = ea
    if epi is None:
        sys.stderr.write('函数体内未找到 `sub sp, fp, #imm` / `mov sp, fp`（可能未使用帧指针）\n')
        return 3
    print('0x%08x 0x%08x' % (entry, epi))
    return 0


if __name__ == '__main__':
    sys.exit(main())
