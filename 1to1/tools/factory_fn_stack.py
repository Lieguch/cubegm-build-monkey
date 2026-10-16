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

★★ R182 增补：被调函数间接读（块读）识别 —— R178/R179/R180 三轮判据盲区的根修
--------------------------------------------------------------------------
上面这条判据有一个**真实的盲区**（GAP 18.01，代价 = 三轮误判、12 条 UB-DCE 漏判）：
原厂把「连续 12 个 int 参数槽」的**首元素地址**传给
`blockcopy`/`blockadaptive`/`mui_blockcopy`/`popwindows`/`popoffwindows`，
被调函数按 `int*` 用 `ldmib r6,{r0,ip}` / `ldr r8,[r4,#0x14]` **间接读**后续槽。
本函数自身对这些槽只有 `str`、没有 `ldr` ⇒ 旧判据报「写了从不读（合法 DCE）」，
**实际是活的** ⇒ 我方 -Os 删掉它就是真缺陷。

工厂真实取值形态（R182 云机实测 `mui_load_state` @0x2eac8）：
    0x2eb28  add ip, sp, #0x4c      ; ip = &参数槽首元素
    0x2eb34  str ip, [sp, #0x18]    ; ★ 地址经**栈槽中转**
    0x2eb50  add r1, sp, #0x64
    0x2eb54  str r1, [sp, #0x1c]
    …
    0x2ec44  ldr r1, [sp, #0x18]    ; 调用前从栈槽取回
    0x2ec4c  ldr r0, [sp, #0x1c]
    0x2ec64  bl  blockcopy           ; blockcopy(param_1=sp+0x64, param_2=sp+0x4c)
⇒ 必须同时支持：① 地址经栈槽中转；② 被调函数把参数搬到 r4/r6/r7 再用
   （`mov r6,r0` → `ldmib r6,{r0,ip}`）。二者都实现了。

本版新增（默认开，`--no-indirect` 可关，供 A/B）：
  1. 扫描本函数的 `bl <callee>` 调用点，**势精度**跟踪 r0–r3 是否持**帧地址**
     （`add rX, sp|fp|r11, #imm` / `mov rX, sp` / `mov rX, rY` 传播 /
       **`str rX,[sp,#S]`→`ldr rX,[sp,#S]` 栈槽中转** / `add rX,rY,#imm` 指针偏移）；
  2. 对每个持帧地址的实参，反汇编被调函数，用同一套跟踪（初值 = 参数基址）找出它
     经**任何**已知指针寄存器做的块读：`ldm{ia,ib,da,db} rn,{list}`（按变体算准槽位）
     与 `ldr rd,[rn,#imm]`（常量位移算准槽位）；
  3. 这些槽标为「被调函数间接读」——**写了但不直接读的槽若落在这里，判定翻转为
     「不是死槽」**，报告给出调用点地址 / 被调函数名 / 具体指令；
  4. 被调函数存在 `ldr rd,[rn,ri]`（寄存器索引，跨度不可静态确定）时**不给槽位结论**，
     只发警告：该帧区不得判死（保守方向，与纪律 62 同向）。

已知限制（诚实声明）
------------------
* 指针经**两个以上**栈槽中转 / 经运算（非 add 立即数）派生时，本工具保守"杀死"
  ⇒ 漏报（不会误报）。
* 被调函数边界取自 symtab；不在 symtab 的目标用「扫到第一条 bx lr / pop{pc}」的
  启发式跨度，并在输出里标注 `size 启发式`。
* 只做**一层**被调函数分析（块读函数自身不再传帧地址出去；要分析它时直接 --fn 它）。

自证（`--self-test`）在旧四项之外新增（全部手算过答案）：
  · 正例：`str [sp,#0x44]` 写入的槽被 callee 的 `ldmib r6,{r1,r2}` + `ldr r7,[r6,#0x14]`
    间接读 ⇒ 判"不是死槽"；
  · 正例：地址经**栈槽中转**（`add r0,sp,#0x40`→`str r0,[sp,#8]`→`ldr r1,[sp,#8]`→`bl`）也能抓到；
  · 正例：callee 内 `mov r6,r0` 后用 r6 索引能抓到（工厂 blockcopy 真形态）；
  · 反例：同一次调用里未被间接读覆盖的槽（0x40）仍判"写了从不读"（不滥翻）；
  · 反例：实参不是帧地址（`mov r0,r5`，r5 未知）⇒ 不产生任何间接读结论；
  · 反例：callee 用 `ldr r3,[r0,r1]` 索引读 ⇒ 只警告、不给槽位（不假装确定）；
  · 反例：`ldmia` / `ldmda` / `ldmdb` 变体的槽位算法分别验算。

用法
----
    python tools/factory_fn_stack.py --fn mui_load_state
    python tools/factory_fn_stack.py --fn mui_load_state --no-indirect    # 旧行为（A/B）
    python tools/factory_fn_stack.py --addr 0x2eac8 --size 0x858
    python tools/factory_fn_stack.py --fn mui_load_state --slots 0xb8,0xb4
    python tools/factory_fn_stack.py --self-test

依赖：capstone。工厂 ELF 默认取 golden/factory.rkgame.bin；函数地址/大小取自
objdump -t 格式 symtab（`FACTORY_SYMTAB` 可覆盖）。缺 symtab 时 `--fn` 不可用，
但 `--addr/--size` 与 `--self-test` 仍可跑；**此时间接读检测自动关闭并告警**
（无法解析被调函数边界 ⇒ "写了从不读"的结论不可信）。
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
PARAM_REGS = ('r0', 'r1', 'r2', 'r3')

# 已知「块读函数族」：按 int* 索引 param[0..5] 的五个函数（R173/R179/R180 定案）。
BLOCKREAD_FAMILY = ('blockcopy', 'blockadaptive', 'mui_blockcopy',
                    'popwindows', 'popoffwindows')


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
    """objdump -t 格式：`0002eac8 g     F .text\t00000858              mui_load_state`"""
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


def by_addr(syms):
    """addr -> (name, size)，用于把 bl 目标解析成函数。"""
    out = {}
    for name, (addr, size) in syms.items():
        out.setdefault(addr, (name, size))
    return out


# ------------------------------------------------------------------ 栈访问
def stack_slots(code, base_addr, mode_thumb=False):
    """返回 {offset: {'r': n, 'w': n, 'w_at': [...]}}，只统计常量位移的 sp/fp 访存。"""
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


# ------------------------------------------------------- 指针/帧地址势精度跟踪（R182）
def disasm_all(code, addr, thumb=False):
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM,
                     capstone.CS_MODE_THUMB if thumb else capstone.CS_MODE_ARM)
    md.detail = True
    return list(md.disasm(code, addr))


def _norm_slot(imm):
    """与 stack_slots 同一约定：负位移按绝对值归并。"""
    return -imm if imm < 0 else imm


# capstone 的 op_str **不含**助记符、立即数打成 `#0x40` 十六进制、bl 目标已是绝对地址、
# ldmia 被归一成 `ldm` —— 四条都是 R182 自证阶段实测踩过的坑，正则按事实写。
RE_LDM = re.compile(r'^ldm(ia|ib|da|db|fa|ed|ea)?\s+(r\d+)\s*!?\s*,\s*\{([^}]*)\}\s*\^?\s*$')
RE_ADD_FRAME = re.compile(r'^(add|sub)\s+(r\d+)\s*,\s*(sp|fp|r11|r7|r13)\s*,\s*#(-?0x[0-9a-fA-F]+|-?\d+)$')
RE_MOV_FRAME = re.compile(r'^mov\s+(r\d+)\s*,\s*(sp|fp|r11|r7|r13)$')
RE_MOV_REG = re.compile(r'^mov\s+(r\d+)\s*,\s*(r\d+)$')
RE_BL = re.compile(r'^bl\s+#(-?0x[0-9a-fA-F]+|-?\d+)$')
# add/sub rX, rY, rZ, #imm 与 add/sub rX, rY, #imm（rY 已知是指针）⇒ 指针偏移传播
RE_ADD_PTR3 = re.compile(r'^(add|sub)\s+(r\d+)\s*,\s*(r\d+)\s*,\s*(r\d+)\s*,\s*#(-?0x[0-9a-fA-F]+|-?\d+)$')
RE_ADD_PTR2 = re.compile(r'^(add|sub)\s+(r\d+)\s*,\s*(r\d+)\s*,\s*#(-?0x[0-9a-fA-F]+|-?\d+)$')
# 访存：str/ldr rX, [base(#imm)]
RE_STR_MEM = re.compile(r'^(str|strb|strh|strd)\s+(r\d+)\s*,\s*\[(sp|fp|r11|r7|r13)(?:\s*,\s*#(-?0x[0-9a-fA-F]+|-?\d+))?\]$')
RE_LDR_MEM = re.compile(r'^(ldr|ldrb|ldrh|ldrd)\s+(r\d+)\s*,\s*\[(sp|fp|r11|r7|r13)(?:\s*,\s*#(-?0x[0-9a-fA-F]+|-?\d+))?\]$')
# 任何其它写目标寄存器的指令 ⇒ 杀死该寄存器的帧地址知识（保守：漏报不误报）
RE_KILL = re.compile(
    r'^(mov|movs|movw|movt|mvn|ldr|ldrb|ldrh|ldrd|add|adds|sub|subs|orr|orrs|and|ands|bic|bics'
    r'|eor|eors|mul|mla|smull|umull|smlal|lsl|lsr|asr|ror|rrx|rsb|rsbs|adc|adcs|sbc|sbcs|clz'
    r'|qadd|qdadd|sdiv|udiv|uxtb|uxth|sxtb|sxth|rev)\w*\s+(r\d+)\s*,')
RE_LDM_LIST = re.compile(r'^ldm\w*\s+(r\d+)\s*!?\s*,\s*\{([^}]*)\}')
RE_STM_LIST = re.compile(r'^stm\w*\s+(r\d+)\s*!?\s*,\s*\{([^}]*)\}')

# ★ capstone 按 APCS 别名打印寄存器：ip=r12 / sb=r9 / sl=r10 / fp=r11 / sp=r13 / lr=r14 / pc=r15
#   （工厂代码里 `add ip, sp, #0x4c` 是真实形态）⇒ 匹配前必须规范化，否则正则只认 `r\d+`
#   会把这类指令**静默漏判**（R182 实测：mui_load_state 的 blockcopy 实参因此漏掉一半）。
REG_ALIAS = {'sp': 'r13', 'ip': 'r12', 'lr': 'r14', 'pc': 'r15',
             'sb': 'r9', 'sl': 'r10', 'fp': 'r11',
             'a1': 'r0', 'a2': 'r1', 'a3': 'r2', 'a4': 'r3',
             'v1': 'r4', 'v2': 'r5', 'v3': 'r6', 'v4': 'r7',
             'v5': 'r8', 'v6': 'r9', 'v7': 'r10', 'v8': 'r11'}
RE_ALIAS = re.compile(r'\b(sp|ip|lr|pc|sb|sl|fp|a[1-4]|v[1-8])\b')


def canon(s):
    """把 APCS 别名寄存器名规范成 rN（供正则匹配）。"""
    return RE_ALIAS.sub(lambda m: REG_ALIAS[m.group(1)], s)


def full_text(ins):
    """capstone 的 op_str 不含助记符 ⇒ 拼起来，并做寄存器名规范化。"""
    return canon(ins.mnemonic.split('.')[0] + ' ' + ins.op_str)


def reg_of(ins, idx):
    """取第 idx 个操作数的寄存器名（已规范化）。"""
    return canon(ins.reg_name(ins.operands[idx].reg)) if ins.operands[idx].type == 1 else ''


def _kill_list(off, liststr):
    for r in [x.strip() for x in liststr.split(',') if x.strip()]:
        if r in off:
            off[r] = None


def walk_ptr(insns, init=None, callee=False):
    """势精度跟踪「寄存器 -> 调用方帧内槽偏移」，逐指令 yield (ins, off快照, mem快照)。

    * callee=False（调用方模式）：`add rX, sp|fp|r11, #imm` 建立帧地址；
      支持 `str rX,[sp,#S]` → `ldr rX,[sp,#S]` 的**栈槽中转**（mem 映射）。
    * callee=True（被调函数模式）：init = {参数寄存器: 基址}；`add rX, sp, #imm`
      是**被调函数自己的帧** ⇒ 杀死（不能混为一谈）；`mov rX,rY` / `add rX,rY,#imm`
      做指针传播。
    """
    off = dict(init or {})
    mem = {}                      # 槽偏移 -> 该槽内容（= 某个帧地址的偏移）
    for ins in insns:
        mn = ins.mnemonic.split('.')[0]
        full = full_text(ins)
        # ---- 帧基址建立（仅调用方模式）
        if not callee and mn in ('add', 'sub'):
            m = RE_ADD_FRAME.match(full)
            if m:
                kind, dst, imm = m.group(1), m.group(2), int(m.group(4), 0)
                off[dst] = _norm_slot(imm) if kind == 'add' else None
                yield ins, off, mem
                continue
        # ---- mov rX, sp/fp（帧基址，偏移 0）/ mov rX, rY（传播）
        if mn == 'mov':
            m = RE_MOV_FRAME.match(full)
            if m:
                off[m.group(1)] = 0
                yield ins, off, mem
                continue
            m = RE_MOV_REG.match(full)
            if m:
                off[m.group(1)] = off.get(m.group(2))
                yield ins, off, mem
                continue
        # ---- 指针偏移传播：add/sub rX, rY, rZ, #imm / add rX, rY, #imm
        if mn in ('add', 'sub'):
            m = RE_ADD_PTR3.match(full)
            if m:
                kind, dst, ya, yb, imm = m.group(1), m.group(2), m.group(3), m.group(4), int(m.group(5), 0)
                base = off.get(ya) if off.get(ya) is not None else off.get(yb)
                off[dst] = (base + (imm if kind == 'add' else -imm)) if base is not None else None
                yield ins, off, mem
                continue
            m = RE_ADD_PTR2.match(full)
            if m:
                kind, dst, src, imm = m.group(1), m.group(2), m.group(3), int(m.group(4), 0)
                off[dst] = (off[src] + (imm if kind == 'add' else -imm)) if off.get(src) is not None else None
                yield ins, off, mem
                continue
        # ---- 栈槽中转（仅调用方模式）：str rX,[sp,#S] / ldr rX,[sp,#S]
        if not callee and mn in ('str', 'strb', 'strh', 'strd', 'ldr', 'ldrb', 'ldrh', 'ldrd'):
            m = RE_STR_MEM.match(full)
            if m:
                src, disp = m.group(2), (int(m.group(4), 0) if m.group(4) else 0)
                S = _norm_slot(disp)
                if off.get(src) is not None:
                    mem[S] = off[src]          # 槽里存的是「帧地址 sp+off[src]」
                else:
                    mem.pop(S, None)           # 被数据值覆写 ⇒ 中转失效
                if mn == 'strd':
                    mem.pop(S + 4, None)
                yield ins, off, mem
                continue
            m = RE_LDR_MEM.match(full)
            if m:
                dst, disp = m.group(2), (int(m.group(4), 0) if m.group(4) else 0)
                S = _norm_slot(disp)
                off[dst] = mem.get(S)          # 取回帧地址；否则是数据值 ⇒ 杀死
                yield ins, off, mem
                continue
        # ---- ldm/stm 写寄存器列表 ⇒ 全杀
        m = RE_LDM_LIST.match(full) or RE_STM_LIST.match(full)
        if m:
            _kill_list(off, m.group(2))
            yield ins, off, mem
            continue
        # ---- 其它写寄存器的指令 ⇒ 杀
        m = RE_KILL.match(full)
        if m:
            off[m.group(2)] = None
        yield ins, off, mem


def frame_arg_map(insns):
    """调用方模式：返回 [(call_addr, target_addr, {reg: slot_offset})]。"""
    sites = []
    for ins, off, _mem in walk_ptr(insns, callee=False):
        if ins.mnemonic.split('.')[0] != 'bl':
            continue
        m = RE_BL.match('bl ' + canon(ins.op_str))
        if not m:
            continue
        snap = {r: off[r] for r in PARAM_REGS if off.get(r) is not None}
        sites.append((ins.address, int(m.group(1), 0), snap))
    return sites


def callee_reads(code, addr, param_regs, thumb=False):
    """被调函数模式：返回它经 param_regs（{reg: 基址}）做的间接读。

    返回 (slots:set, indexed:bool, evidence:list[str])
      slots   —— 能算准槽位的读（ldm 变体 + 常量位移 ldr）
      indexed —— 存在 `ldr rd,[rn,ri]` 寄存器索引读 ⇒ 跨度不可静态确定
    """
    import capstone
    from capstone.arm import ARM_OP_MEM
    slots = set()
    indexed = False
    ev = []
    for ins, off, _mem in walk_ptr(disasm_all(code, addr, thumb), init=dict(param_regs), callee=True):
        mn = ins.mnemonic.split('.')[0]
        full = full_text(ins)
        # ---- ldm{ia,ib,da,db} rn, {r0,r1,...}（capstone 把 ia 归一成 "ldm"）
        m = RE_LDM.match(full)
        if m and mn in ('ldm', 'ldmia', 'ldmib', 'ldmda', 'ldmdb', 'ldmfa', 'ldmed', 'ldmea'):
            variant = m.group(1) or 'ia'
            base_reg = m.group(2)
            if off.get(base_reg) is not None:
                regs = [x.strip() for x in m.group(3).split(',') if x.strip()]
                n = len(regs)
                b = off[base_reg]
                for k in range(n):
                    if variant in ('ia', 'fa'):
                        slots.add(b + 4 * k)
                    elif variant in ('ib', 'ed'):
                        slots.add(b + 4 * (k + 1))
                    elif variant == 'da':
                        slots.add(b - 4 * (n - k))
                    else:                       # db / ea
                        slots.add(b - 4 * (k + 1))
                ev.append('0x%x ldm%s %s,{%s} ⇒ %d 槽（基址 sp+0x%x）'
                          % (ins.address, variant, base_reg, m.group(3), n, b))
            continue
        # ---- ldr/ldrd 族（常量位移算准槽位；寄存器索引只警告）
        if mn in READ_MNEMONICS:
            for o in ins.operands:
                if o.type == ARM_OP_MEM:
                    memd = o.mem
                    base = canon(ins.reg_name(memd.base)) if memd.base else ''
                    if off.get(base) is not None:
                        b = off[base]
                        if memd.index:
                            indexed = True
                            ev.append('0x%x %s ⇒ **寄存器索引读，跨度不可静态确定**'
                                      % (ins.address, full))
                        else:
                            slots.add(b + _norm_slot(memd.disp))
                            ev.append('0x%x %s ⇒ 槽 sp%+d'
                                      % (ins.address, full, _norm_slot(memd.disp)))
                    break
    return slots, indexed, ev


def analyse_indirect(caller_code, caller_addr, resolve, fetch, thumb=False, max_callee=0x800):
    """把「被调函数间接读」分析装配成一个可测的纯函数。

    resolve(target_addr) -> (name, size) 或 None；fetch(addr, size) -> bytes。
    返回 [{call, target, name, args, slots, indexed, ev, size_heuristic, unresolved}]。
    """
    sites = frame_arg_map(disasm_all(caller_code, caller_addr, thumb))
    out = []
    for call_addr, target, snap in sites:
        if not snap:
            continue
        name, size = (None, None)
        r = resolve(target)
        heuristic = False
        if r:
            name, size = r
        if size is None or size <= 0 or size > max_callee:
            size = _scan_to_return(fetch, target, max_callee)
            heuristic = True
            if size is None:
                out.append(dict(call=call_addr, target=target, name=name or '?',
                                args=snap, slots=set(), indexed=False, ev=[],
                                size_heuristic=True, unresolved=True))
                continue
        code = fetch(target, size)
        slots, indexed, ev = callee_reads(code, target, snap, thumb)
        out.append(dict(call=call_addr, target=target, name=name or ('sub_%x' % target),
                        args=snap, slots=slots, indexed=indexed, ev=ev,
                        size_heuristic=heuristic, unresolved=False))
    return out


def _scan_to_return(fetch, addr, cap):
    """启发式：从 addr 起找第一条 `bx lr` / `pop {...,pc}`，返回跨度。"""
    code = fetch(addr, cap)
    if not code:
        return None
    try:
        insns = disasm_all(code, addr)
    except Exception:
        return None
    for ins in insns:
        op = ins.op_str
        mn = ins.mnemonic.split('.')[0]
        if mn == 'bx' and op.startswith('lr'):
            return ins.address + ins.size - addr
        if mn in ('pop', 'ldmia', 'ldm') and 'pc' in op:
            return ins.address + ins.size - addr
    return None


def report(fn=None, addr=None, size=None, only=None, thumb=False, indirect=True):
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

    # ---- 被调函数间接读（R182）----
    ind_slots = {}          # slot -> [证据 dict, ...]
    warnings = []
    if indirect:
        if not syms:
            print('  ★ 无 symtab（FACTORY_SYMTAB=%r 不存在）⇒ 间接读检测关闭；'
                  '「写了从不读」的结论**不可信**（R178 盲区）' % SYMTAB)
        else:
            a2 = by_addr(syms)

            def resolve(t):
                return a2.get(t)

            def fetch(a, s):
                o = e.v2f(a)
                if o is None:
                    return b''
                return e.b[o:o + s]

            try:
                res = analyse_indirect(code, addr, resolve, fetch, thumb)
            except Exception as ex:
                print('  ★ 间接读分析异常（%s）⇒ 本条结论退回旧判据' % ex)
                res = []
            for r in res:
                argstr = ','.join('%s=sp+0x%x' % (k, v) for k, v in sorted(r['args'].items()))
                if r.get('unresolved'):
                    warnings.append('调用@0x%x → %s：帧地址实参 %s，但被调函数边界不可解析'
                                    '（PLT/thunk？）⇒ 该帧区不得判死'
                                    % (r['call'], r['name'], argstr))
                    continue
                for s in r['slots']:
                    ind_slots.setdefault(s, []).append(r)
                if r['indexed']:
                    warnings.append('调用@0x%x → %s：实参 %s 被**寄存器索引读**'
                                    '（ldr rd,[rn,ri]）⇒ 跨度不可静态确定 ⇒ 该帧区不得判死'
                                    % (r['call'], r['name'], argstr))
                elif r['slots']:
                    print('  ─ 调用@0x%x → %s（%s）实参 %s ⇒ 间接读槽 %s'
                          % (r['call'], r['name'],
                             'size 启发式' if r['size_heuristic'] else 'symtab',
                             argstr,
                             ' '.join('sp+0x%x' % s for s in sorted(r['slots']))))

    keys = sorted(slots)
    if only:
        want = set(int(x, 16) for x in only.split(','))
        keys = [k for k in keys if k in want]
    print('  %-10s %6s %6s   %s' % ('偏移', '读', '写', '判定'))
    n_dead = 0
    for k in keys:
        s = slots[k]
        if s['w'] and not s['r']:
            if k in ind_slots:
                who = ind_slots[k][0]
                verdict = ('★ 被 %s@0x%x 经 ldm/ldr[rn+off] 间接读 ⇒ **不是死槽**'
                           '（R178 盲区已补）' % (who['name'], who['target']))
            else:
                verdict = '★ 写了从不读（原厂也是死槽）'
                n_dead += 1
        elif s['r'] and not s['w']:
            verdict = '只读（可能是入参拷贝区）'
        else:
            verdict = '既写又读 ⇒ 有意义'
        print('  0x%-8x %6d %6d   %s' % (k, s['r'], s['w'], verdict))
    n_live = sum(1 for k in slots if slots[k]['r'])
    print()
    for w in warnings:
        print('  %s' % w)
    if warnings:
        print()
    print('  小结：%d 个槽有常量位移访存；其中「写但从不读」%d 个（已排除被调函数间接读）；'
          '「被读」%d 个；间接读覆盖 %d 个槽'
          % (len(slots), n_dead, n_live, len(ind_slots)))
    return 0


# --------------------------------------------------------------- 自证
def _bl_bytes(target, at):
    imm24 = (target - (at + 8)) >> 2
    return bytes([imm24 & 0xFF, (imm24 >> 8) & 0xFF, (imm24 >> 16) & 0xFF, 0xEB])


def self_test():
    """用**手算过答案**的指令流验仪器（旧四项 + R182 间接读三正/四反）。"""
    import capstone
    print('=' * 96)
    print('自证：用手算过答案的指令流验仪器')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-56s got=%-22s %s' % (tag, got, '✓' if good else '★ FAIL'))

    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)

    # ================= 旧四项（原样保留）=================
    code = (b'\xb8\x30\x8d\xe5' + b'\xb4\x30\x9d\xe5' + b'\xb4\x20\x8d\xe5' + b'\x04\x10\x90\xe5')
    txt = '\n'.join('     %s' % i.mnemonic + ' ' + i.op_str for i in md.disasm(code, 0x1000))
    print(txt)
    s = stack_slots(code, 0x1000)
    chk('sp+0xb8 写 1 读 0', (s.get(0xb8, {}).get('w'), s.get(0xb8, {}).get('r')), (1, 0))
    chk('sp+0xb4 写 1 读 1', (s.get(0xb4, {}).get('w'), s.get(0xb4, {}).get('r')), (1, 1))
    chk('bas=r0 不计入', 4 in s, False)
    chk('槽数 = 2', len(s), 2)
    chk('寄存器索引寻址 → 跳过', len(stack_slots(b'\x02\x10\x90\xe7', 0x2000)), 0)
    chk('fp 负位移归并到 0x20', sorted(stack_slots(b'\x20\x30\x1b\xe5', 0x3000)), [0x20])

    # ================= R182：被调函数间接读 =================
    # 合成 callee @0x2000（工厂 blockcopy 真形态：mov r6,r0 / mov r4,r1 后用 r6/r4）：
    #   mov  r6, r0          param_1 → r6
    #   mov  r4, r1          param_2 → r4
    #   ldmib r6, {r1, r2}   读 [r6+4],[r6+8]
    #   ldr  r8, [r4, #0x14] 读 [r4+0x14]
    #   ldr  r7, [r6, #0x14] 读 [r6+0x14]
    #   bx lr
    callee = (b'\x00\x60\xa0\xe1'      # mov r6, r0        (0xE1A00600)
              b'\x01\x40\xa0\xe1'      # mov r4, r1        (0xE1A00401)
              b'\x06\x00\x96\xe9'      # ldmib r6, {r1, r2}(0xE9960006，小端 06 00 96 E9)
              b'\x14\x80\x94\xe5'      # ldr r8, [r4,#0x14](0xE5948014)
              b'\x14\x70\x96\xe5'      # ldr r7, [r6,#0x14](0xE5967014)
              b'\x1e\xff\x2f\xe1')     # bx lr
    l_txt = ['%s %s' % (i.mnemonic, i.op_str) for i in md.disasm(callee, 0x2000)]
    print('   合成 callee: ' + ' | '.join(l_txt))
    chk('callee[0] = mov r6, r0', l_txt[0], 'mov r6, r0')
    chk('callee[1] = mov r4, r1', l_txt[1], 'mov r4, r1')
    chk('callee[2] = ldmib r6, {r1, r2}', l_txt[2], 'ldmib r6, {r1, r2}')
    chk('callee[3] = ldr r8, [r4, #0x14]', l_txt[3], 'ldr r8, [r4, #0x14]')

    # 合成 caller A @0x1000（地址直接在调用点算出）：
    #   str r2,[sp,#0x40] / str r2,[sp,#0x44] / add r0,sp,#0x40 / bl 0x2000
    callerA = (b'\x40\x20\x8d\xe5' + b'\x44\x20\x8d\xe5' + b'\x40\x00\x8d\xe2'
               + _bl_bytes(0x2000, 0x100c))
    cA = ['%s %s' % (i.mnemonic, i.op_str) for i in md.disasm(callerA, 0x1000)]
    print('   合成 callerA: ' + ' | '.join(cA))
    chk('callerA[3] = bl #0x2000', cA[3], 'bl #0x2000')

    def fake_resolve(t):
        return ('fake_callee', len(callee)) if t == 0x2000 else None

    def fake_fetch(a, s):
        return callee if a == 0x2000 else b''

    res = analyse_indirect(callerA, 0x1000, fake_resolve, fake_fetch)
    chk('A：检测到 1 个持帧地址调用点', len(res), 1)
    if res:
        r = res[0]
        chk('A：调用点地址 0x100c', r['call'], 0x100c)
        chk('A：实参 r0=sp+0x40', r['args'].get('r0'), 0x40)
        # r6=r0 ⇒ 基址 0x40：ldmib 读 0x44/0x48；ldr [r6,#0x14] 读 0x54
        chk('A：间接读槽 = {0x44,0x48,0x54}', sorted(r['slots']), [0x44, 0x48, 0x54])
        chk('A：无寄存器索引读', r['indexed'], False)
        direct = stack_slots(callerA, 0x1000)
        chk('A：0x44 写但不直接读', (direct.get(0x44, {}).get('w'), direct.get(0x44, {}).get('r')), (1, 0))
        chk('A：0x44 被间接读覆盖 ⇒ 判据翻转', 0x44 in r['slots'], True)
        chk('A：0x40 **不**被覆盖（不滥翻）', 0x40 in r['slots'], False)

    # 合成 caller B @0x1000（工厂 mui_load_state 真形态：地址经**栈槽中转**）：
    #   add r0, sp, #0x40 / str r0, [sp, #8] / ldr r1, [sp, #8] / bl 0x2000
    callerB = (b'\x40\x00\x8d\xe2'      # add r0, sp, #0x40
               b'\x08\x00\x8d\xe5'      # str r0, [sp, #8]   (0xE58D0008)
               b'\x08\x10\x9d\xe5'      # ldr r1, [sp, #8]   (0xE59D1008)
               + _bl_bytes(0x2000, 0x100c))
    cB = ['%s %s' % (i.mnemonic, i.op_str) for i in md.disasm(callerB, 0x1000)]
    print('   合成 callerB: ' + ' | '.join(cB))
    chk('callerB[1] = str r0, [sp, #8]', cB[1], 'str r0, [sp, #8]')
    chk('callerB[2] = ldr r1, [sp, #8]', cB[2], 'ldr r1, [sp, #8]')
    resB = analyse_indirect(callerB, 0x1000, fake_resolve, fake_fetch)
    chk('B：栈槽中转也能检测到', len(resB), 1)
    if resB:
        chk('B：实参 r1=sp+0x40', resB[0]['args'].get('r1'), 0x40)
        chk('B：间接读槽 = {0x44,0x48,0x54}', sorted(resB[0]['slots']), [0x44, 0x48, 0x54])

    # 反例：实参不是帧地址（mov r0,r5，r5 未知）⇒ 0 个间接读结论
    caller_neg = (b'\x40\x20\x8d\xe5'      # str r2,[sp,#0x40]
                  b'\x05\x00\xa0\xe1'      # mov r0, r5
                  + _bl_bytes(0x2000, 0x1008))
    chk('反例 caller[1] = mov r0, r5',
        ['%s %s' % (i.mnemonic, i.op_str) for i in md.disasm(caller_neg, 0x1000)][1],
        'mov r0, r5')
    chk('非帧地址实参 ⇒ 0 个间接读结论',
        len(analyse_indirect(caller_neg, 0x1000, fake_resolve, fake_fetch)), 0)

    # 反例：callee 用寄存器索引读 ⇒ 只警告、不给槽位
    callee_idx = (b'\x01\x30\x90\xe7'      # ldr r3,[r0,r1]  (0xE7903001)
                  b'\x1e\xff\x2f\xe1')     # bx lr
    chk('索引读样本编码正确',
        ['%s %s' % (i.mnemonic, i.op_str) for i in md.disasm(callee_idx, 0x2000)][0],
        'ldr r3, [r0, r1]')
    s_idx, indexed, _ = callee_reads(callee_idx, 0x2000, {'r0': 0x40})
    chk('索引读 ⇒ slots 空', sorted(s_idx), [])
    chk('索引读 ⇒ indexed=True', indexed, True)

    # 反例：ldm 变体的槽位算法（ia 归一成 "ldm"；da/db 减计数）
    s_ia, _, _ = callee_reads(b'\x06\x00\x90\xe8', 0x2000, {'r0': 0x40})   # ldmia r0,{r1,r2}
    chk('ldmia r0,{r1,r2} ⇒ 0x40,0x44', sorted(s_ia), [0x40, 0x44])
    s_ib, _, _ = callee_reads(b'\x06\x00\x90\xe9', 0x2000, {'r0': 0x40})   # ldmib r0,{r1,r2}
    chk('ldmib r0,{r1,r2} ⇒ 0x44,0x48', sorted(s_ib), [0x44, 0x48])
    s_da, _, _ = callee_reads(b'\x06\x00\x10\xe8', 0x2000, {'r0': 0x40})   # ldmda r0,{r1,r2}
    chk('ldmda r0,{r1,r2} ⇒ 0x38,0x3c', sorted(s_da), [0x38, 0x3c])
    s_db, _, _ = callee_reads(b'\x06\x00\x10\xe9', 0x2000, {'r0': 0x40})   # ldmdb r0,{r1,r2}
    chk('ldmdb r0,{r1,r2} ⇒ 0x38,0x3c', sorted(s_db), [0x38, 0x3c])

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
    ap.add_argument('--no-indirect', action='store_true',
                    help='关闭被调函数间接读识别（旧行为，A/B 用）')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return 0 if self_test() else 2
    return report(a.fn, int(a.addr, 16) if a.addr else None,
                  int(a.size, 16) if a.size else None, a.slots, a.thumb,
                  indirect=not a.no_indirect)


if __name__ == '__main__':
    sys.exit(main())
