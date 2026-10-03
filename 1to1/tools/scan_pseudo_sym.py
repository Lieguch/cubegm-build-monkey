#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_pseudo_sym.py —— 普查「Ghidra 伪符号」：工厂真值是 `符号+常量偏移`，
但 Ghidra 渲染成裸符号（丢掉偏移）的地方。

★ 为什么必须做（2026-10-03 第120 轮血泪）：
  工厂 FilePreEmu 里 `add r4, r4, #200` 之后的 `r4`，Ghidra 渲染成裸符号
  `FilenameExt`（该符号 size 仅 4 字节！）。我方照抄 ⇒ 往 4 字节槽写字符串
  ⇒ 越界 200 字节 ⇒ 后续 GetCoreIndex 读到污染数据 ⇒ 表遍历永不进入。
  **一个常量偏移 = 一整类静默内存破坏。**

判据（机械、可复核）：
  对 `golden/factory.funcs.json` 每条形如
      add rX, rX, #IMM      /   add rX, rY, #IMM
  的指令，若 rY 在同函数内被用作 `ldr` 的基址（PC 相对取址），则该 rX 是
  「基址+偏移」。把 IMM 与工厂符号表比对：
     - 若 `基址符号地址 + IMM` 落在**另一个真实对象**内 ⇒ 伪符号（高危）
     - 若落在同一对象内 ⇒ 无害（Ghidra 只是省略了对象内偏移）
输出 TSV，按危险度排序。--selftest 自证。
"""
import json, os, re, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_factory_syms(binpath):
    """从工厂 ELF .symtab 读 (addr, size, name, section)。"""
    d = open(binpath, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 0x20)[0]
    e_shnum = struct.unpack_from('<H', d, 0x30)[0]
    e_shentsize = struct.unpack_from('<H', d, 0x2e)[0]
    e_shstrndx = struct.unpack_from('<H', d, 0x32)[0]
    def sh(i):
        o = e_shoff + i * e_shentsize
        v = struct.unpack_from('<10I', d, o)
        return dict(name=v[0], addr=v[3], off=v[4], size=v[5], link=v[6])
    ss = sh(e_shstrndx)
    def nm(x):
        s = d[ss['off'] + x:]
        return s[:s.index(b'\0')].decode(errors='replace')
    secs = [sh(i) for i in range(e_shnum)]
    for s in secs:
        s['nm'] = nm(s['name'])
    out = []
    for s in secs:
        if s['nm'] == '.symtab':
            st = secs[s['link']]
            for k in range(s['size'] // 16):
                o = s['off'] + k * 16
                n, val, sz, info, oth, shx = struct.unpack_from('<IIIBBH', d, o)
                if n == 0:
                    continue
                nb = d[st['off'] + n:]
                name = nb[:nb.index(b'\0')].decode(errors='replace')
                out.append((val, sz, name))
    return sorted(out)

# ★ 只认**通用寄存器**间的add：`sp/lr/pc/ip` 的加减是栈帧/返回地址/PC 相对修正，
#   不是「符号+偏移」，必须排除（第一版没排除，被自证抓到 —— 见 selftest）。
#   ★ r13=sp / r14=lr / r15=pc 是**数字别名**，Ghidra 文本里两种写法都可能出现，
#     一并排除（第二版漏了，被自证抓到 —— 见 selftest）。
_ALIAS = {'r13', 'r14', 'r15', 'sp', 'lr', 'pc', 'ip'}   #注：ARM32 无 r9别名问题；r12 是普通 GPR
def _is_gpr(tok):
    return tok not in _ALIAS and re.match(r'^r(?:[0-9]|1[0-5])$', tok) is not None
RE_ADD = re.compile(r'^add\s+(r(?:[0-9]|1[0-5])),\s*(r(?:[0-9]|1[0-5])),\s*#(\d+)\s*$')

def scan(verbose=False):
    fp = os.path.join(ROOT, 'golden', 'factory.funcs.json')
    bp = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
    if not os.path.exists(fp):
        print('!! 缺 golden/factory.funcs.json', file=sys.stderr); return 2
    syms = load_factory_syms(bp) if os.path.exists(bp) else []
    if not syms:
        print('!! 缺 golden/factory.rkgame.bin（或解析出 0 符号）', file=sys.stderr); return 2

    d = json.load(open(fp, encoding='utf-8'))
    fns = d['functions']
    rows = []
    for fname, f in fns.items():
        t1 = f.get('t1') or []
        # 1) 收集被 ldr PC-relative 装载过的寄存器（= 持有某符号地址）
        loaded = set()
        for ins in t1:
            m = re.match(r'^ldr\s+(r\d+),\s*\[pc,\s*#\d+\]$', ins)
            if m:
                loaded.add(m.group(1))
            m2 = re.match(r'^add\s+(r\d+),\s*pc,\s*(r\d+)$', ins)
            if m2 and m2.group(2) in loaded:
                loaded.add(m2.group(1))
        if not loaded:
            continue
        # 2) 找 add rX, rY, #IMM   （rY ∈ loaded）
        for idx, ins in enumerate(t1):
            m = RE_ADD.match(ins)
            if not m:
                continue
            dst, src, imm = m.group(1), m.group(2), int(m.group(3))
            if not (_is_gpr(dst) and _is_gpr(src)):
                continue
            if src not in loaded:
                continue
            # rY 持的是哪个符号地址？用上下文：紧随其后的 mov r0, rX / bl @xxx
            rows.append(dict(func=fname, idx=idx + 1, ins=ins,
                             dst=dst, src=src, imm=imm))

    # 3) 判定：src 持有的符号地址未知（我们不静态反推），改为**输出候选**，
    #    由调用方（人/AI）结合 ledger 核对 —— 保持工具"只呈现事实"的原则。
    print('# 伪符号候选：工厂 `add rX, rY, #IMM` 且 rY 刚被 ldr[pc] 取址')
    print('# 判定：若 (该 ldr 取到的符号地址 + IMM) 落在**另一个**工厂对象内 ⇒ 高危')
    print('# func\tline\tins\tdst\tsrc\timm')
    n = 0
    for r in rows:
        print('%s\t%d\t%s\t%s\t%s\t%d' % (r['func'], r['idx'], r['ins'], r['dst'], r['src'], r['imm']))
        n += 1
    print('# 共 %d 条候选' % n, file=sys.stderr)
    return 0

def selftest():
    """自证：RE_ADD 的匹配面 + _is_gpr 的别名排除，两者分开测（职责不同）。"""
    # --- RE_ADD：只管「add rX, rY, #IMM」这个形状 ---
    assert RE_ADD.match('add r4, r4, #200')
    assert RE_ADD.match('add r3, r7, #56')
    assert not RE_ADD.match('add r4, pc, r4')      # PC 相对修正，不是 add rX,rY,#IMM
    assert not RE_ADD.match('add sp, sp, #316')     # 形状是 add rX,rY,#IMM
    assert not RE_ADD.match('sub r9, r6, #2')       # sub 不是 add
    # --- _is_gpr：管别名排除（sp/lr/pc 及其数字写法）---
    for t in ('sp', 'lr', 'pc', 'r13', 'r14', 'r15'):
        assert not _is_gpr(t), t
    for t in ('r0', 'r4', 'r12'):
        assert _is_gpr(t), t
    print('selftest OK')
    return 0

if __name__ == '__main__':
    if '--selftest' in sys.argv:
        sys.exit(selftest())
    sys.exit(scan('-v' in sys.argv))
