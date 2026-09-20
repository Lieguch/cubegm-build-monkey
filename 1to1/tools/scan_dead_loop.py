#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""死循环门禁 —— 产物里出现「没有出口的循环」而源码没有 `for(;;)` ⇒ 必有缺陷。

## 为什么需要这条门禁（本轮的实证来源）

`init_user_joy_key_mask` 的 size 比只有 **0.342**（工厂 316 B / 我们 108 B），
一开始被归为"疑编译器分段"。深挖后（`objdump` 级的原始字 + `.rel.text`）：

    st_size = 108 B（27 槽）
    整个目标文件**只有 1 条重定位：STD_index**
    而源码引用的另外 4 个全局
      user_joy_key_mask / user_joy_key_trubo / joy_key_mask / turbo_delay
    **一次也没被引用** —— 第二段循环 + 函数尾声被删光，
    第一段循环还失去终止测试，变成 `b <loop_head>` 的**死循环**。

根因是 Ghidra 的一个**保真度陷阱**：

    Ghidra 把「数组末尾那个栈槽的**地址**」渲染成一个**独立标量局部变量**
        gh_uint local_88[24];
        gh_uint uStack_28;          ← 其实是 local_88[24] 的位置
        ...
        } while (puVar6 != &uStack_28);

`uStack_28` 作为**独立 C 对象**，地址由编译器自行摆放。放在 `local_88` 之下时
条件 `puVar6 != &uStack_28` **恒真** ⇒ 循环后续全部成为**不可达代码**而被删除。
这不是"体积小一点"，是**函数体被删掉 + 变成死循环**。

修法：把边界改成与数组同源的**下标式**（`local_88 + 24`），使边界不依赖局部变量布局。
修复后：`.text` 348 B、**6 条重定位**（5 个全局全部引用到），比值 **1.10x → OK**。

## 判据（不依赖源码，纯机器码）

1. 取每个 `.o` 里 `SHT_SYMTAB` 的 FUNC 符号区间；
2. 解出每条指令的**函数内后继**（`b` 只走向目标；条件分支走目标+顺序；
   `bl` 视为顺序；`bx lr` / `pop {…,pc}` / `ldr pc,[…]` 视为返回，无后继）；
3. Tarjan 求 SCC；**若某个 SCC（>=2 块）没有任何一条出边指向 SCC 之外 ⇒ 无出口循环**。

## 退出码

    0 = 无命中
    2 = 有命中（**逐项人工核对**：可能是真缺陷，也可能是"线程常驻循环"这类有意为之）
    3 = 无法判定（缺 build/obj 等）

## 为什么要有"逐项核对"这一档

`XintiaoThread` / `ReadJoystickThread` 这类**线程常驻循环**在源码里就是
`for(;;)` 或 `while(1)`，本来就是死循环 ⇒ 命中是**预期**的。
所以本门禁只做"必须有人看一眼"的触发器，而不是自动判罪；
判罪的依据是**源码里有没有 `for(;;)`/`while(1)`** —— 有则是设计，没有则是缺陷。
"""
import glob
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OBJD = os.path.join(ROOT, 'build', 'obj')

# 允许存在"有意为之的死循环"的函数（逐项核对后登记；登记必须带理由）
EXPECTED_DEAD_LOOP = {}

# ★ 更省事也更可靠的一档：**自动判"源码里有没有无限循环构造"**。
#   有 `while(1)`/`while(true)`/`for(;;)` ⇒ 产物里出现无出口循环是**预期**的（设计如此）；
#   没有 ⇒ 就是"编译器把循环后续判为不可达而删除"（本轮 `init_user_joy_key_mask` 的缺陷）。
#   这样门禁**自维护**，不需要人工白名单（白名单会随着新增函数而失效）。
INF_LOOP_RE = re.compile(r'while\s*\(\s*(1|true)\s*\)|for\s*\(\s*;\s*;\s*\)')


def source_has_inf_loop(fn):
    """在 src/proprietary 里找同名源文件，看有没有无限循环构造。返回 (找到?, 有?)"""
    for f in glob.glob(os.path.join(ROOT, 'src', 'proprietary', '*', '*_%s.c' % fn)):
        try:
            txt = open(f, 'rb').read().decode('utf-8', 'replace')
        except OSError:
            continue
        return True, bool(INF_LOOP_RE.search(txt))
    return False, False


def sections(d):
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    return [struct.unpack_from('<10I', d, e_shoff + i * es) for i in range(n)]


def funcs(path):
    """返回 [(name, [(addr, word), ...])]，只取落在节内的 FUNC 区间。"""
    d = open(path, 'rb').read()
    S = sections(d)
    out = []
    for s in S:
        if s[1] != 2:                          # SHT_SYMTAB
            continue
        stro = S[s[6]][4]                      # sh_link -> .strtab
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2 or sz < 16 or shx == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            name = d[stro + nmn:k].decode('utf-8', 'replace')
            sec = S[shx]
            base, off, secsz = sec[3], sec[4], sec[5]
            words = []
            for o in range(0, sz, 4):
                if base <= val + o < base + secsz:
                    words.append((val + o, struct.unpack_from('<I', d, off + (val - base) + o)[0]))
            out.append((name, words))
    return out


def insn_succ(w, addr):
    """函数内后继（返回 (succ_list, 是否返回)）。"""
    cond = (w >> 28) & 0xF
    if cond == 0xF:                            # 无条件指令族（含 SVC/BLX(imm)）——不当作控制流
        return [addr + 4], False
    op = (w >> 25) & 0x7
    if op == 0b101:                            # B / BL
        imm = w & 0xFFFFFF
        if imm & 0x800000:
            imm -= 0x1000000
        tgt = (addr + 8 + imm * 4) & 0xFFFFFFFF
        if (w >> 24) & 1:                      # BL：调用后顺序执行
            return [addr + 4], False
        if cond == 0xE:                        # 无条件 B
            return [tgt], False
        return [tgt, addr + 4], False
    if (w & 0x0FFFFFF0) in (0x012FFF10, 0x012FFF20, 0x012FFF30):   # bx/blx/bxj reg
        return [], True
    if op == 0b100 and ((w >> 20) & 1) and (w & 0x8000):           # pop/ldm {.., pc}
        return [], True
    if op == 0b011 and not ((w >> 4) & 1) and ((w >> 12) & 0xF) == 15 and not ((w >> 20) & 1):
        return [], True                                            # ldr pc, [...]
    return [addr + 4], False


def find_dead_loop(words):
    """返回 (SCC 起点, SCC 块数) 或 None。"""
    if not words:
        return None
    addrs = {a for a, _ in words}
    succ = {}
    for a, w in words:
        t, _ret = insn_succ(w, a)
        succ[a] = [x for x in t if x in addrs]
    idx, low, on, st, cnt, comps = {}, {}, set(), [], [0], []
    sys.setrecursionlimit(200000)

    def strong(v):
        idx[v] = low[v] = cnt[0]
        cnt[0] += 1
        st.append(v)
        on.add(v)
        for w2 in succ[v]:
            if w2 not in idx:
                strong(w2)
                low[v] = min(low[v], low[w2])
            elif w2 in on:
                low[v] = min(low[v], idx[w2])
        if low[v] == idx[v]:
            comp = []
            while True:
                w2 = st.pop()
                on.discard(w2)
                comp.append(w2)
                if w2 == v:
                    break
            comps.append(comp)

    for a, _ in words:
        if a not in idx:
            strong(a)
    # ★★ 可达性（2026-09-20，锚点自证连带发现的必要约束）：
    #   只报告**从函数入口可达**的 SCC。函数尾部/中间的字面量池是**数据**，
    #   把它们当指令解时可能恰好解出 `b .`（自环）⇒ 单块自环规则会把整片数据判成死循环
    #   （实测：不加这条时命中数从 6 暴涨到 34，多出来的全是池里的数据字）。
    #   池数据从入口**不可达** ⇒ 用可达性过滤既保住了真信号，又去掉了假阳性。
    entry = min(a for a, _ in words)
    reach = set()
    stack = [entry]
    while stack:
        v = stack.pop()
        if v in reach:
            continue
        reach.add(v)
        for w2 in succ.get(v, ()):
            if w2 not in reach:
                stack.append(w2)
    for comp in comps:
        if not (set(comp) & reach):
            continue
        cs = set(comp)
        # ★ 口径收敛（2026-09-20，经两轮实测）：**只报 >=2 块的无出口 SCC**。
        #   曾一度放宽到"单块自环"（`b .`），锚点自证能过，但**实跑假阳性爆炸**：
        #   命中从 6 涨到 32，多出来的全是函数里的**字面量池数据字**被解成 `b .`
        #   （可达性过滤也拦不住 —— 条件分支的 fall-through 会正好落进池里）。
        #   而本轮抓到的真缺陷 `init_user_joy_key_mask` 是 **17 条指令的多块 SCC**，
        #   所以"单块"这一档对真实的"函数体被删"没有任何增量价值，只带来噪声。
        #   ⇒ 判据收敛为：**多块 + 无出边 + 从入口可达**。
        if len(comp) < 2:
            continue
        if not any((w2 not in cs) for v in comp for w2 in succ[v]):
            return (min(comp), len(comp))
    return None


def scan(paths=None):
    hits = []
    for p in sorted(paths or glob.glob(os.path.join(OBJD, '*.o'))):
        try:
            fs = funcs(p)
        except Exception:
            continue
        for name, words in fs:
            r = find_dead_loop(words)
            if r:
                hits.append((os.path.basename(p), name, r[0], r[1], len(words)))
    return hits


def selftest():
    """锚点自证：判据自身必须先通过。"""
    # ★ 锚点设计纪律（本轮踩过）：条件分支的**目标地址必须真的落在指令序列里**，
    #   否则"函数内后继"会把它过滤掉，于是"有出口的循环"被误判成无出口。
    #   所有目标都按 addr+8+imm*4 精确算出并落位，下面用注释标出。
    A = [
        # (说明, 指令字序列, 期望是否命中)     基址 0x1000，逐条 +4
        ("单块自环 `b .`（口径外：数据字歧义太大）→ 不命中",
         [0xEAFFFFFE, 0xE1A00000], False),
        ("两块互跳、无出口（真死循环）→ 命中",
         [0xE1A00000, 0xEAFFFFFD, 0xE1A00000], True),
        # cmp(0x1000)→0x1004 ; bne→0x1010(存在)+0x1008 ; b→0x1000 ; …0x1010 后返回
        ("条件分支跳到 SCC 之外（有出口）→ 不命中",
         [0xE3500000, 0x1A000001, 0xEAFFFFFC, 0xE1A00000, 0xE1A00000, 0xE12FFF1E], False),
        ("普通顺序代码 + 返回 → 不命中",
         [0xE1A00000, 0xE12FFF1E], False),
        ("带 pop{pc} 早退的循环 → 不命中",
         [0xE3500000, 0x08BD8000, 0xEAFFFFFC, 0xE8BD8000], False),
    ]
    ok = 0
    for note, words, want in A:
        w = [(0x1000 + i * 4, x) for i, x in enumerate(words)]
        got = find_dead_loop(w) is not None
        mark = '✓' if got == want else '✗'
        if got == want:
            ok += 1
        print("  %s %-44s 期望 %-5s 实得 %s" % (mark, note, want, got))
    print("  锚点通过 %d/%d" % (ok, len(A)))
    return 0 if ok == len(A) else 1


def main():
    if '--selftest' in sys.argv:
        return selftest()
    if not os.path.isdir(OBJD):
        print('!! 缺 %s（先在 CI/本地构建一次）' % OBJD)
        return 3
    print('=' * 84)
    print('死循环门禁（产物里出现「无出口循环」⇒ 复核源码有无 `for(;;)`/`while(1)`）')
    print('=' * 84)
    hits = scan()
    print('  build/obj 目标文件 %d 个；命中 %d 个函数' %
          (len(glob.glob(os.path.join(OBJD, '*.o'))), len(hits)))
    if hits:
        print('  %-46s %-30s %-10s %-8s %s' % ('目标文件', '函数', 'SCC 起点', '块内/共', '判定'))
        unreg = []
        for f, n, a, nb, nt in hits:
            found, inf = source_has_inf_loop(n)
            if inf or n in EXPECTED_DEAD_LOOP:
                tag = '✓ 属设计（源码有 while(1)/for(;;)）' if inf else '✓ 已登记'
            elif not found:
                tag = '★ 无同名源文件 ⇒ 需人工核对'
                unreg.append((f, n, a, nb, nt))
            else:
                tag = '★ 源码无无限循环 ⇒ **循环后续被删**'
                unreg.append((f, n, a, nb, nt))
            print('  %-46s %-30s 0x%-8x %d / %-5d %s' % (f[:46], n[:30], a, nb, nt, tag))
        if unreg:
            print('')
            print('  结论 : FAIL —— %d 个「无出口循环」且源码里没有无限循环构造' % len(unreg))
            print('         请逐个核对源码：有 `for(;;)`/`while(1)` ⇒ 属设计；')
            print('         若源码是普通循环 ⇒ **编译器把循环后续判为不可达而删除**，')
            print('         根因通常是「循环边界取了另一个局部对象的地址」'
                  '（Ghidra 保真度陷阱）⇒ 改成下标式边界。')
            return 2
    print('  结论 : PASS（无未登记的死循环）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
