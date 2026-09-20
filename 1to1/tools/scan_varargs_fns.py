#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""变参函数保真度门禁 —— Ghidra 会把变参函数渲染成「单参数」，重建时极易丢 `...`。

## 为什么需要这条门禁（血泪来源）

Ghidra 对 `void RARCH_LOG(const char *fmt, ...)` 反编译出的是：

    void RARCH_LOG(undefined4 param_1) { RARCH_LOG_V(param_1); return; }

**`...` 被整个丢掉**，我们照抄后：`RARCH_LOG_V(char *fmt, va_list ap)` 的第二个参数
（`va_list`）就成了**调用者的 r1 残留值**。实测后果（P5 第五个真实分歧）：

    main_Menu() 里 RARCH_LOG("root_path:%s\n", root_path) 被调用时 r1 = root_path(0x3e1398)
    ⇒ RARCH_LOG_V 拿 0x3e1398 当 va_list ⇒ vfprintf 把**字符串自己的内存**当参数列表
    ⇒ `%s` 取到的"指针" = 0x6364732f = "/sdc" 的**内容**
    ⇒ 崩在 libc strlen（shim 现场：r1 = r0 & ~7、r4 = 7 对齐掩码）⇒ 观测窗口停在 18/32。

## 判据（不依赖源码，纯机器码）

**工厂侧**：变参函数有 AAPCS32 变参序言 —— 把 r0..r3 存进「寄存器保存区」。
最典型的是 `push {r0, r1, r2, r3}`（`0xE92D000F`）。全 `.text` 扫这个 opcode 即得变参函数清单。

**重建侧**：编译器不同、序言形状不同（LLVM 用 `sub sp,#12` + `stm r0,{r1,r2,r3}`），
所以**不能**要求同一 opcode；改为要求「函数序言区里存在一条把 {r1,r2,r3} 一起存出去的
`stm`/`push`」——这既覆盖 GCC 形状也覆盖 LLVM 形状。

退出码：0 = 全部保真；2 = 有函数丢了变参；3 = 无法判定（缺工厂 ELF 等）。
"""
import bisect
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

FACTORY = os.environ.get('FACTORY_ELF', 'D:/output/rkgame/rkgame')
REBUILT = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

PUSH_R0_R3 = 0xE92D000F          # push {r0, r1, r2, r3}

# ★★ 2026-09-20 放宽（本轮发现的**门禁盲区**）：旧判据只认 `push {r0,r1,r2,r3}`，
#   但 GCC 只保存**真正需要**的变参寄存器 —— 若 r0 是已消费的固定参数（实例：
#   `log_dummy(int lvl, const char *fmt, ...)` 里的 `lvl`），序言就是
#   `push {r1, r2, r3}`（`0xE92D000E`）⇒ 旧判据整族漏掉（实测 `log_dummy` 因此
#   一直没被发现，直到 `prop_equiv` 用它 52B→16B 的 0.31x 偏小把它顶出来）。
#   新判据：`STMDB sp!, {…}` 的寄存器列表里**必须同时含 r1,r2,r3**（低 4 位掩码 & 0xE == 0xE），
#   r0 可有可无。宁可放宽（本门禁是"逐个人工核对"性质，多列一个可接受），不可漏。
STMDB_SP_MASK = 0xFFFF0000
STMDB_SP_OP   = 0xE92D0000
VARARG_RLOW   = 0x000E           # r1|r2|r3
VARARG_PROLOGUE_LIMIT = 32       # 变参序言必须落在函数入口 +N 字节内（实测 log_dummy = +8）


def load(path):
    if not os.path.exists(path):
        return None, None, None
    d = open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    si = struct.unpack_from('<H', d, 50)[0]
    stroff = struct.unpack_from('<I', d, e_shoff + si * es + 16)[0]
    S = {}
    for i in range(n):
        o = e_shoff + i * es
        sh = struct.unpack_from('<10I', d, o)
        e = d.index(b'\x00', stroff + sh[0])
        S[d[stroff + sh[0]:e].decode('utf-8', 'replace')] = (sh[3], sh[4], sh[5])
    syms = {}
    for i in range(n):
        o = e_shoff + i * es
        sh = struct.unpack_from('<10I', d, o)
        if sh[1] != 2:                      # SHT_SYMTAB
            continue
        st = struct.unpack_from('<I', d, e_shoff + sh[6] * es + 16)[0]
        ent = sh[9] or 16
        for j in range(sh[5] // ent):
            oo = sh[4] + j * ent
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, oo)
            if nmn == 0 or (inf & 0xf) != 2 or shx == 0:
                continue
            e = d.index(b'\x00', st + nmn)
            syms.setdefault(d[st + nmn:e].decode('utf-8', 'replace'), val)
    return d, S, syms


def owner_lookup(syms, lo, hi):
    items = sorted((v, k) for k, v in syms.items() if lo <= v < hi)
    starts = [v for v, _ in items]

    def owner(ea):
        i = bisect.bisect_right(starts, ea) - 1
        return items[i][1] if i >= 0 else '?'
    return owner


def owner_lookup_full(syms, lo, hi):
    """同 owner_lookup，但**同时返回符号起点地址**（位置判据需要）。"""
    items = sorted((v, k) for k, v in syms.items() if lo <= v < hi)
    starts = [v for v, _ in items]

    def owner(ea):
        i = bisect.bisect_right(starts, ea) - 1
        return (items[i][1], items[i][0]) if i >= 0 else ('?', -1)
    return owner


def factory_varargs(d, S):
    """工厂里带 A32 变参「寄存器保存区」序言的函数名。

    判据（2026-09-20 放宽后）：`STMDB sp!, {…}` 且寄存器列表**同时含 r1,r2,r3**。
      · 旧判据只认 `push {r0,r1,r2,r3}`（低 4 位 == 0xF）⇒ 漏掉「r0 是已消费的固定参数」
        那一族（实例 `log_dummy(int lvl, const char *fmt, ...)` ⇒ `push {r1,r2,r3}`）。
      · 放宽后仍要求 r1..r3 三者齐备，故不会误收普通的 `push {r4,lr}` 之类。
    """
    ta, to, ts = S['.text']
    owner = owner_lookup_full(_SYMS_F, ta, ta + ts)
    hits = {}
    for k in range(0, ts - 4, 4):
        w = struct.unpack_from('<I', d, to + k)[0]
        if (w & STMDB_SP_MASK) != STMDB_SP_OP or (w & 0xFFFF & VARARG_RLOW) != VARARG_RLOW:
            continue
        nm, base = owner(ta + k)
        if nm == '?' or base < 0:
            continue
        # ★★ 位置判据（2026-09-20 补）：变参序言必须**在函数入口附近**。
        #   放宽掩码后立刻抓到假阳性 —— `PauseMenu`（真序言 `push {r4..fp,lr}`）被判成
        #   "重建侧丢了变参"，因为函数**体内部**（入口 +2128 B 处）恰好有一条
        #   `push {r1,r2,r3}`（GCC 用它把 3 个字压栈）。**不做位置约束，判据就没有意义。**
        #   实测口径：`log_dummy` 的序言在入口 +8B（`cmp`/`bxls` 之后），故 32B 足够。
        if ta + k - base > VARARG_PROLOGUE_LIMIT:
            continue
        hits.setdefault(nm, ta + k)
    return hits


def has_varargs_epilogue_free(d, S, va, limit=64):
    """重建侧：序言区（前 limit 字节）里是否有「把 {r1,r2,r3} 一起存出去」的指令。

    覆盖三种形状：
      · GCC/原厂：`push {r0, r1, r2, r3}`（STMDB sp!, mask=0xF）
      · GCC/原厂：`push {r1, r2, r3}`     （STMDB sp!, mask=0xE —— r0 是已消费的固定参数）
      · LLVM    ：`sub sp,#12` + `stm rX, {r1, r2, r3}`（Rn 为普通寄存器，mask 含 r1,r2,r3）
    """
    ta, to, ts = S['.text']
    if not (ta <= va < ta + ts):
        return None
    off = to + (va - ta)
    for p in range(off, min(off + limit, to + ts - 4), 4):
        ins = struct.unpack_from('<I', d, p)[0]
        if (ins & STMDB_SP_MASK) == STMDB_SP_OP and (ins & 0xFFFF & VARARG_RLOW) == VARARG_RLOW:
            return True
        # STM/LDM：bits27..25 = 100；L = bit20
        if (ins & 0x0E000000) == 0x08000000:
            L = (ins >> 20) & 1
            mask = ins & 0xFFFF
            if L == 0 and (mask & 0x0E) == 0x0E:      # 存 r1,r2,r3
                return True
    return False


def main():
    global _SYMS_F
    d_f, S_f, syms_f = load(FACTORY)
    d_r, S_r, syms_r = load(REBUILT)
    if d_f is None:
        print('FACTORY 缺失：%s' % FACTORY)
        return 3
    if d_r is None:
        print('REBUILT 缺失：%s' % REBUILT)
        return 3
    _SYMS_F = syms_f

    print('=' * 72)
    print('变参函数保真度门禁')
    print('=' * 72)
    hits = factory_varargs(d_f, S_f)
    print('工厂变参函数（序言含 `STMDB sp!, {…r1,r2,r3}`）：%d 个' % len(hits))
    bad = []
    rows = []
    for nm, va in sorted(hits.items(), key=lambda kv: kv[1]):
        rv = syms_r.get(nm)
        if rv is None:
            rows.append((nm, va, None, None, '★ 重建侧无此符号'))
            bad.append(nm)
            continue
        ok = has_varargs_epilogue_free(d_r, S_r, rv)
        rows.append((nm, va, rv, ok, '' if ok else '★ 重建侧丢了变参序言'))
        if not ok:
            bad.append(nm)
    print('%-18s %-12s %-12s %s' % ('函数', '工厂地址', '重建地址', '判定'))
    for nm, va, rv, ok, note in rows:
        print('%-18s 0x%08x   %-12s %s'
              % (nm, va, ('0x%08x' % rv) if rv is not None else '(缺)',
                 '✓ 变参序言在位' if ok else note))
    print('')
    if bad:
        print('结论 : FAIL —— %d 个函数丢了变参语义：%s' % (len(bad), ', '.join(bad)))
        print('       Ghidra 会把 `f(const char *, ...)` 渲染成单参数；重建时必须按原形还原')
        print('       （`void f(char *fmt, ...) { va_list ap; va_start(ap, fmt); ... }`）。')
        return 2
    print('结论 : PASS（%d/%d 个变参函数的序言全部保真）' % (len(rows), len(rows)))
    return 0


_SYMS_F = {}

if __name__ == '__main__':
    sys.exit(main())
