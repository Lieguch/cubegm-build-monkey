#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""延时循环门禁 —— 源码里的「纯计数循环」在产物里必须还存在。

## 为什么需要这条门禁（本轮的实证来源）

`ReadPS2JS`（PS/2 位敲读时序）的源码里有三段 Ghidra 反编译出来的**忙等延时**：

    do { local_30 = 0; do { local_30 = local_30 + 1; } while (local_30 < 0x27); iVar4--; } while (iVar4);

工厂侧（GCC 6.2.0）**完整保留**了它们（`str r8,[sp,#8]` / `mov r3,#39` / `ldr-cmp-bge` /
`add-str` / `ldr-cmp-blt` 的嵌套循环，外层 5 次、内层 **39 (0x27)** 次）——
那是 GPIO 位敲的**时序语义**，少了它 PS/2 读时序就变了。

但**现代编译器把它当死代码整体删除**：计数器是普通局部变量 ⇒ 被提升到寄存器 ⇒
循环没有任何可观察副作用 ⇒ 删掉。实测（同一份源码）：

| 编译口径 | `ReadPS2JS` 产物 | vs 工厂 384 B |
|---|---|---|
| 工厂 GCC 6.2.0（基准） | 384 B | 1.00x |
| clang（zig cc `-Os`，**修复前**） | **144 B / 36 条** | 0.375x ← 三段延时循环一条不剩 |
| GCC 14.2 `-Os`（对照组） | 88 B | 0.23x ← 删得更彻底 |

**修法**：把延时计数器声明为 `volatile` ⇒ 每轮迭代强制一次真实存取，
与工厂"每轮写栈"的行为一致。修复后 **276 B（0.719x，进 OK 区）**。

★ 这是**语义修复**（时序/副作用），不是为了让体积数字好看 ——
所以本门禁的判据**不看体积**，只看"那个常量还在不在产物里"。

## 判据（与体积无关，非此即彼）

1. 在 `src/proprietary/*/*.c` 里找**纯计数循环**：循环体只有 `X = X ± 1;`，
   循环条件是对同一个 X 的常量比较（`< C` / `!= C`），C 为数字或十六进制常量。
2. 取该函数在 `build/rkgame.rebuilt.elf` 里的指令区间；
3. **该常量必须作为立即数出现在产物里**（`cmp rX, #C` / `mov rX, #C` / `subs rX, rX, #C` 等）
   ⇒ 说明循环还在；找不到 ⇒ **循环被编译器删掉了**。
4. 若源码里的该循环已被显式改成 `volatile` 计数器，本门禁**仍要求常量在位**
   （volatile 只是让循环不被删，常量仍应出现），因此对修复前后的两种状态都能正确判定。

退出码：0 = 全部在位；2 = 有循环被删；3 = 无法判定（缺产物等）。
"""
import glob
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REBUILT = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

# 循环体只有「同一个变量自增/自减」，随后 `} while (X <op> C)`
PURE_COUNT = re.compile(
    r'(\w+)\s*=\s*\1\s*([+\-])\s*1\s*;\s*\n\s*\}\s*while\s*\(\s*\1\s*(!?=|<|<=|>|>=)\s*(0[xX][0-9a-fA-F]+|\d+)\s*\)')


def sources():
    """返回 [(源文件, 函数名, [(循环变量, 比较运算, 上界常量, 行号), ...])]"""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'src', 'proprietary', '*', '*.c'))):
        txt = open(f, 'rb').read().decode('utf-8', 'replace').replace('\r\n', '\n')
        body = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
        hits = []
        for m in PURE_COUNT.finditer(body):
            hits.append((m.group(1), m.group(3), int(m.group(4), 0), body[:m.start()].count('\n') + 1))
        if hits:
            base = os.path.basename(f)[:-2]
            fn = base.split('_', 2)[-1] if base.count('_') >= 2 else base
            out.append((f, fn, hits))
    return out


def sym_size(path, name):
    """从 SHT_SYMTAB 取 FUNC 的 (vaddr, size)。"""
    if not os.path.exists(path):
        return None
    d = open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    S = [struct.unpack_from('<10I', d, e_shoff + i * es) for i in range(n)]
    for s in S:
        if s[1] != 2:
            continue
        stro = S[s[6]][4]
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2 or sz == 0 or shx == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            if d[stro + nmn:k].decode('utf-8', 'replace') == name:
                return val, sz, S, d
    return None


def immediates(path, name):
    """把函数区间里所有“小立即数”（<=0xFFF 的常量）收集起来（不依赖完整解码器，只看编码里的常数域）。"""
    r = sym_size(path, name)
    if r is None:
        return None
    val, sz, S, d = r
    # 找该符号所在段的文件偏移
    fileoff = None
    for s in S:
        if s[3] <= val < s[3] + s[5] and (s[2] & 1 or s[1] == 1):
            fileoff = s[4] + (val - s[3])
            break
    if fileoff is None:
        return None
    consts = set()
    for o in range(0, sz, 4):
        w = struct.unpack_from('<I', d, fileoff + o)[0]
        cond = (w >> 28) & 0xF
        if cond == 0xF:
            continue
        op = (w >> 25) & 0x7
        if op == 0b001:                                  # data-processing (imm)
            imm = w & 0xFF
            rot = ((w >> 8) & 0xF) * 2
            if rot:
                imm = ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF
            consts.add(imm)
        if op == 0b010:                                  # ldr/str imm12
            consts.add(w & 0xFFF)
    return consts


def main():
    if not os.path.exists(REBUILT):
        print('!! 缺 %s（先构建一次）' % REBUILT)
        return 3
    print('=' * 88)
    print('延时循环门禁（源码里的「纯计数循环」其常量必须仍出现在产物里）')
    print('=' * 88)
    bad = []
    n_checked = 0
    for src, fn, hits in sources():
        cons = immediates(REBUILT, fn)
        if cons is None:
            print('  %-26s %-34s  重建侧无此符号' % (fn[:26], os.path.basename(src)[:34]))
            bad.append((fn, 'MISSING', None))
            continue
        for var, opr, bound, line in hits:
            n_checked += 1
            # 常量可能以原值或"取负/取反"等形式出现；先按原值找，再按补码找
            ok = (bound in cons) or ((bound - 1) in cons)
            mark = '✓' if ok else '★'
            print('  %s %-24s L%-4d 循环 `%s %s %s` 上界常量 %s 在产物中 %s'
                  % (mark, fn[:24], line, var, opr, hex(bound), hex(bound),
                     '在位' if ok else '**缺失 ⇒ 循环被删**'))
            if not ok:
                bad.append((fn, 'DELETED', (var, opr, bound, line)))
    print('')
    if bad:
        print('  结论 : FAIL —— %d 处延时/计数循环被编译器删除' % len(bad))
        print('         修法：把计数器声明为 `volatile`（工厂每轮迭代都写内存 ⇒ 必须真实执行）')
        return 2
    print('  结论 : PASS（%d 处纯计数循环的上界常量全部在位）' % n_checked)
    return 0


if __name__ == '__main__':
    sys.exit(main())
