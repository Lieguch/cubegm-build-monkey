#!/usr/bin/env python3
"""忠实度审计 —— 回答「我们离 1:1 复刻还有多远」，而不是「产物能不能跑」。

为什么需要它（2026-09-22 用户质疑的直接产物）
    ``rkgame-rebuild`` 那条被放弃的路，判据是「造一个能跑的程序」。
    本项目是 **1:1 复刻**，判据应当是「**产物与原厂的差异收敛**」。
    此前我用的判据（PT_LOAD 几何是否合法、ELF 是否规范、能不能 exec）都是
    「通用 ELF 合法性」或「可用性」，**不是忠实度** ⇒ 方向跑偏。

两条主刻度（都可机械复现、且单调收敛）
    A. **工厂镜像引用数**：自有 `.text` 里指向 `.fimg_*`（工厂机器码/数据镜像）的
       地址常量个数。**目标 0**。
       · 为什么这是忠实度的核心：引用 = 仍依赖工厂的机器码/数据 ⇒ 不是复刻。
       · 收敛路径：补齐未重建函数 + 把「跳工厂机器码」的调用改为调用自有实现。
       · 归零后：`.fimg_*` 可整体移除 ⇒ 只读区/可写区自然连续
         ⇒ **段结构与原厂的 2 段形态自然对齐**（不必再为「让它能加载」做任何适配）。
    B. **与原厂的结构差异清单**：PT_LOAD 段数/权限序列、GNU_STACK、DT_* 关键项。
       逐项应等于原厂；不等于就是忠实度缺陷（**不是「嫌疑」，是缺陷**）。

用法
    PY=<python> python3 tools/fidelity_audit.py [产物] [原厂]
"""
import io
import json
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')
FACTORY = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'golden', 'factory.rkgame.bin')


def parse(p):
    d = open(p, 'rb').read()
    ph = struct.unpack_from('<I', d, 28)[0]
    pn = struct.unpack_from('<H', d, 44)[0]
    shoff = struct.unpack_from('<I', d, 32)[0]
    shent = struct.unpack_from('<H', d, 46)[0]
    shnum = struct.unpack_from('<H', d, 48)[0]
    shstr = struct.unpack_from('<H', d, 50)[0]
    P = [struct.unpack_from('<8I', d, ph + i * 32) for i in range(pn)]
    S = [struct.unpack_from('<10I', d, shoff + i * shent) for i in range(shnum)]
    st = S[shstr][4]

    def name(s):
        k = d.index(b'\x00', st + s[0])
        return d[st + s[0]:k].decode('utf-8', 'replace')

    secs = [(name(s), s[3], s[5], s[1]) for s in S]
    loads = [(i, x) for i, x in enumerate(P) if x[0] == 1]
    gstack = [x for x in P if x[0] == 0x6474e551]
    dyn = {}
    for x in P:
        if x[0] == 2:
            j = 0
            while True:
                t, v = struct.unpack_from('<iI', d, x[1] + j); j += 8
                dyn.setdefault(t, []).append(v)
                if t == 0:
                    break
            break
    interp = None
    for x in P:
        if x[0] == 3:
            interp = d[x[1]:x[1] + x[4]].rstrip(b'\x00').decode('utf-8', 'replace')
    # 符号
    syms = []
    for s in S:
        if s[1] != 2:
            continue
        stro = S[s[6]][4]
        ent = s[9] or 16
        for jj in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + jj * ent)
            if nmn == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            syms.append((val, sz, inf & 0xF, d[stro + nmn:k].decode('utf-8', 'replace')))
    return dict(d=d, secs=secs, loads=loads, gstack=gstack, dyn=dyn, interp=interp, syms=syms)


def prot(x):
    return ('R' if x[6] & 4 else '-') + ('W' if x[6] & 2 else '-') + ('X' if x[6] & 1 else '-')


T = parse(TARGET)
F = parse(FACTORY)

print('=' * 104)
print('忠实度审计  target = %s' % os.path.relpath(TARGET, ROOT))
print('            factory = %s' % os.path.relpath(FACTORY, ROOT))
print('=' * 104)

# ---------------- 刻度 A：工厂镜像引用数 ----------------
fimg = [(n, a, z) for n, a, z, t in T['secs'] if n.startswith('.fimg') and z]
own_text = next(((a, a + z) for n, a, z, t in T['secs'] if n == '.text'), None)
print()
print('## 刻度 A —— 工厂镜像引用数（目标 0）')
if not fimg:
    print('   .fimg_* 不存在 ⇒ 刻度 A 已达成（产物不含工厂镜像）')
    refs_total = 0
elif own_text:
    lo = min(a for _, a, _ in fimg)
    hi = max(a + z for _, a, z in fimg)
    refs = {}
    a0, a1 = own_text
    for off in range(a0, a1 - 3, 4):
        w = struct.unpack_from('<I', T['d'], off)[0]
        if lo <= w < hi:
            for n2, a2, z2 in fimg:
                if a2 <= w < a2 + z2:
                    refs[n2] = refs.get(n2, 0) + 1
                    break
    refs_total = sum(refs.values())
    tot_fimg = sum(z for _, _, z in fimg)
    tot_own = sum(z for n, a, z, t in T['secs']
                  if n in ('.text', '.rodata', '.data', '.bss', '.plt', '.ARM.exidx'))
    print('   .fimg_* 合计 %d B（%.2f MB）' % (tot_fimg, tot_fimg / 1048576.0))
    print('   自有核心节合计 %d B（%.2f MB）' % (tot_own, tot_own / 1048576.0))
    print('   ⇒ ★ **引用数 = %d**  （收敛目标：0）' % refs_total)
    for k, c in sorted(refs.items(), key=lambda kv: -kv[1]):
        print('        %-26s × %d' % (k, c))
    print('   ⇒ 工厂机器码以 OBJECT 形态存在：FUNC 符号 %d 个，OBJECT 符号 %d 个' %
          (len([x for x in T['syms'] if min(a for _, a, _ in fimg) <= x[0] < hi and x[2] == 2 and x[1]]),
           len([x for x in T['syms'] if min(a for _, a, _ in fimg) <= x[0] < hi and x[2] == 1])))
else:
    print('   （找不到 .text）')
    refs_total = -1

# ---------------- 刻度 B：与原厂的结构差异 ----------------
print()
print('## 刻度 B —— 与原厂的结构差异（逐项应等于原厂）')
rows = [
    ('e_type', struct.unpack_from('<H', T['d'], 16)[0], struct.unpack_from('<H', F['d'], 16)[0]),
    ('e_flags', struct.unpack_from('<I', T['d'], 36)[0], struct.unpack_from('<I', F['d'], 36)[0]),
    ('PT_INTERP', T['interp'], F['interp']),
    ('PT_LOAD 段数', len(T['loads']), len(F['loads'])),
    ('NEEDED 数', len(T['dyn'].get(1, [])), len(F['dyn'].get(1, []))),
]
tgs = T['gstack'][0] if T['gstack'] else None
fgs = F['gstack'][0] if F['gstack'] else None
rows.append(('GNU_STACK flags', prot(tgs) if tgs else '缺', prot(fgs) if fgs else '缺'))
rows.append(('GNU_STACK memsz', tgs[5] if tgs else '-', fgs[5] if fgs else '-'))
rows.append(('DT_INIT', hex(T['dyn'].get(12, [0])[0]), hex(F['dyn'].get(12, [0])[0])))
rows.append(('DT_INIT_ARRAYSZ', T['dyn'].get(27, [0])[0], F['dyn'].get(27, [0])[0]))
rows.append(('DT_FINI_ARRAYSZ', T['dyn'].get(28, [0])[0], F['dyn'].get(28, [0])[0]))
rows.append(('DT_FLAGS', hex(T['dyn'].get(30, [0])[0]), hex(F['dyn'].get(30, [0])[0])))
print('   %-22s %-26s %-26s %s' % ('项', '本产物', '原厂', '判定'))
bad = 0
for k, a, b in rows:
    ok = (a == b)
    if not ok:
        bad += 1
    print('   %-22s %-26s %-26s %s' % (k, str(a), str(b), '✓ 一致' if ok else '★ 差异'))
print()
print('   PT_LOAD 权限序列：')
print('     本产物 %s' % [prot(x) for _, x in T['loads']])
print('     原厂   %s' % [prot(x) for _, x in F['loads']])

# ---------------- 工厂函数落位 ----------------
print()
print('## 刻度 C —— 工厂函数落位')
pf = os.path.join(ROOT, 'golden', 'factory.funcs.json')
if os.path.exists(pf):
    Fj = json.load(io.open(pf, encoding='utf-8'))['functions']
    R = {}
    for v, sz, typ, n2 in T['syms']:
        if typ == 2 and sz:
            R.setdefault(n2, (v, sz))
    import collections
    c = collections.Counter()
    for n2 in Fj:
        if n2 not in R:
            c['缺失(未重编)'] += 1
        else:
            v = R[n2][0]
            if own_text and own_text[0] <= v < own_text[1]:
                c['自有 .text'] += 1
            elif fimg and min(a for _, a, _ in fimg) <= v < max(a + z for _, a, z in fimg):
                c['工厂镜像区'] += 1
            else:
                c['其它'] += 1
    for k, v in c.most_common():
        print('   %-16s %d' % (k, v))
    print('   ⇒ 工厂函数总数 %d' % sum(c.values()))

print()
print('=' * 104)
print('判据口诀：**刻度 A 收敛到 0 + 刻度 B 全一致 = 1:1 达成**。')
print('   "产物能不能 exec / 能否跑" 属**可用性**判据，不能当忠实度刻度。')
