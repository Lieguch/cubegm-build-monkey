#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diff_exec —— **逐函数差分执行**（differential execution）等价性对拍。

为什么需要它（第 59 轮的根本性转折）
------------------------------------
在此之前，判定「我们重建的 C 是否与工厂二进制语义一致」靠**人读反汇编 + 手工数据流推断**。
这条路**无法收敛**：213 个函数、每次只看到一条线索，而且会把「仪器缺陷」误判成
「源码缺陷」（实测 3 个"发现"里 2 个是仪器错：单代表配对、名字归一化漏下划线形式）。

本工具把这件事换成**机器可判**的形式：
  同一函数名，在**工厂二进制**与**我们的重建产物**里各跑一遍（Unicorn ARM32），
  输入完全相同 ⇒ 比较**可观测状态**。**不需要人读反汇编。**

为什么可行（本项目的两个特殊便利，已实测）
------------------------------------------
1. 两个二进制都是 `ET_EXEC`，且我们的产物把**工厂的 .data/.bss 放在同一批 vaddr**
   （0x3af000 / 0x3b2178）⇒ **全局变量地址两侧一致 ⇒ 内存可逐字节直接对拍**。
2. 工厂二进制**未 strip**（.symtab 完整）⇒ 函数名/大小/数据符号都拿得到。

判据（比什么、不比什么）
------------------------
比（高信号、布局无关）：
  * 返回值 r0
  * **外部（PLT）调用序列** —— 直接回答"是不是少实现 / 多调了什么"
  * **数据区访存指纹**：`[符号名, 宽度, 读/写]` 多重集 —— 宽度窄化（真机 SIGBUS 那类）在此现形
  * **数据区最终内容**（按符号名逐项）
不比（低信号、布局相关）：机器码字节、指令数、栈帧布局、内部函数调用序列。
  ⇒ 工厂 GCC 6.2 与我们 clang/zig 必然在这些量上发散，**它们不是判据**。

设计要点（踩过的坑，都已固化）
------------------------------
* **PLT 布局两侧不同**（实测：工厂 PLT0=20 B / 条目 12 B；我们 PLT0=32 B / 条目 16 B）
  ⇒ **绝不假设固定偏移**。用 capstone 在 `.plt` 里找 `ldr pc, [...]`（它是每个 stub 的
  倒数第二条指令），条目起点 = 该地址 - 8，**按 `.rel.plt` 顺序配名**。
* **数据区不能取"最后一个可写段"**（我们的产物有多个可写段）⇒ 取**含有最多数据符号**的可写段。
* 外部调用**拦截在 PLT 入口**（不执行 stub，否则会经未重定位的 GOT 跳到野地址），
  返回一个**两侧相同**的确定性桩值 ⇒ 差异只可能来自被测代码本身。

用法
----
    python tools/diff_exec.py --self-test                  # 正/反双向自证（必须全过）
    python tools/diff_exec.py --list                       # 列出可对拍的函数
    python tools/diff_exec.py --fn FBA_Load                # 单函数对拍
    python tools/diff_exec.py --batch --limit 40 --out report/diff_exec.txt

退出码：0 = 无发散 / 1 = 有发散 / 2 = 自证失败 / 11 = 前置不可用
"""
import argparse
import bisect
import gc
from collections import Counter
import hashlib
import os
import re
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTORY = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
OURS = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

try:
    from unicorn import (UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                         UC_MODE_ARM, UC_MODE_THUMB, Uc, UcError)
    import unicorn.arm_const as ac
    from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
    from elftools.elf.elffile import ELFFile
except ImportError as e:  # pragma: no cover
    sys.stderr.write('缺少依赖：%s\n请先：python -m pip install unicorn capstone pyelftools\n' % e)
    sys.exit(11)

SENTINEL = 0x7FFFF000
STACK_BASE = 0x7E000000
STACK_SIZE = 0x00040000
SCRATCH = 0x7D000000
SCRATCH_SIZE = 0x00010000
MAX_TRACE = 3000
_MD = Cs(CS_ARCH_ARM, CS_MODE_ARM)
_MD.detail = False


# --------------------------------------------------------------------------- #
class Bin(object):
    def __init__(self, path):
        self.path = path
        self.raw = open(path, 'rb').read()
        self.elf = ELFFile(open(path, 'rb'))
        self.segs = []
        for s in self.elf.iter_segments():
            if s['p_type'] == 'PT_LOAD':
                self.segs.append((s['p_vaddr'], s['p_filesz'], s['p_memsz'], s['p_flags'], s['p_offset']))
        self.segs.sort()
        self.funcs, self.data_syms, self.sym_list = {}, {}, []
        # ★ 同名数据符号（LOCAL + GLOBAL 同名是**合法 ELF**）：实测工厂里
        #   `ArchivePath` 有一个 LOCAL 0x3AE610(size=64, .data) **和** 一个 GLOBAL 0x3E18D4(size=28)，
        #   而工厂的代码引用的是 **LOCAL** 那个（intra-object 引用优先绑定本地符号）。
        #   以名字为键的字典会**静默折叠**成后者 ⇒ 归因错误 ⇒ 可能产出**假 PASS**。
        self.dup_objs = {}
        self.sym_names = set()        # 全部符号名（判"这个名字在不在"）
        self.sym_bind = {}            # (addr, name) -> bind（用于"私有副本"判定）
        self.name_bind = {}           # name -> bind（同名多份时**优先 LOCAL**）
        st = self.elf.get_section_by_name('.symtab')
        if st is not None:
            for s in st.iter_symbols():
                # ★ 必须用 s.name（字符串）；s['st_name'] 是 .strtab 的**偏移量(整数)**，
                #   用它会把符号表建成 {offset: (addr,size)} ⇒ 永远匹配不上函数名。
                a, sz, n, ty = s['st_value'], s['st_size'], s.name, s['st_info']['type']
                if a == 0 or not n:
                    continue
                self.sym_list.append((a, sz, n, ty))
                self.sym_names.add(n)
                self.sym_bind[(a, n)] = s['st_info']['bind']
                b = self.name_bind.get(n)
                if b is None or s['st_info']['bind'] == 'STB_LOCAL':
                    self.name_bind[n] = s['st_info']['bind']
                if ty == 'STT_FUNC':
                    if n not in self.funcs or sz > self.funcs[n][1]:
                        self.funcs[n] = (a, sz)
                elif ty == 'STT_OBJECT':
                    self.dup_objs.setdefault(n, []).append((a, sz, s['st_shndx']))
                    self.data_syms[n] = (a, sz)
        self.sym_list.sort()
        self._addr_col = [x[0] for x in self.sym_list]
        self._dregion = self._pick_dregion()
        self.plt_map, self.plt_lo, self.plt_hi = self._build_plt()

    # --- 地址 → 最近前驱符号（与尺寸无关；见 GAP 17.15 的"尺寸继承"陷阱）---
    def nearest_sym(self, addr):
        """→ (符号名, 符号地址) 或 None。取**最近的前驱** OBJECT/FUNC。

        ★ 为什么用"最近前驱"而不是"最小覆盖尺寸"：我方镜像段别名的 st_size 曾全部等于
          整段大小（`.set A, B + off` 继承 B 的 `.size`），那种符号表里"最小尺寸"退化成
          任意选择。最近前驱这条规则与尺寸无关，对两种符号表都给同一个正确答案。
        ★ 为什么**跳过 Ghidra 合成名**（`DAT_<hex>` / `UNK_<hex>`）：它们是我们自己造的名字，
          工厂里没有 ⇒ 一旦命中就配不上对，会把真正的语义名（如 `m_ui`）盖掉。
          实测（GAP 17.14）：`m_ui+80` 被盖成裸地址 `0x003af2b4` ⇒ 15+ 个函数凭空多了
          "仅O" 差异。合成名**把地址编进了名字**，对"跨侧配对"零信息量 ⇒ 归因时优先用真名。
        """
        i = bisect.bisect_right(self._addr_col, addr)
        fallback = None
        for j in range(i - 1, max(-1, i - 400), -1):
            a, sz, n, ty = self.sym_list[j]
            if ty not in ('STT_OBJECT', 'STT_FUNC') or a > addr:
                continue
            if fallback is None:
                fallback = (n, a)
            if not RE_SYNTH.match(n):
                return n, a
        return fallback

    def bind_of(self, name):
        """该名字在**本**二进制里的绑定：'STB_LOCAL' / 'STB_GLOBAL' / None（有多个则优先 LOCAL）。"""
        return self.name_bind.get(name)

    def pure_private(self):
        """→ "地址是实现细节"的名字集合：在本二进制里**唯一**且绑定为 `STB_LOCAL` 的数据对象。

        ★ 三个条件缺一不可（GAP 17.14，两次自我纠错后的定论）：
          ① **唯一**：`handle` 在工厂里有**两份**（0x3B21C8 / 0x3CF988，都是 LOCAL）
             —— 两份是**不同对象**，"某函数用了哪一份"是语义（一份被写、另一份被读就是 bug）
             ⇒ 必须按**地址**配对。
          ② **LOCAL**：`key2` 是 GLOBAL ⇒ 外部可见 ⇒ 地址就是契约 ⇒ 必须按地址。
          ③ 我方即便另持同名私有副本，也按**名字**配对（`_mxml_key` / `m_ui`）。
        ★ 最初我用"名字级优先 LOCAL"的绑定表 ⇒ 把 `handle` 的 GLOBAL 那份也判成私有
          ⇒ 同一地址在两侧配不上 ⇒ 凭空造出 6 个假发散（`FBA_Load`/`Load_Proc2`/…）。
          第二次我把规则写成"LOCAL 且无同名 GLOBAL"，但工厂的 `handle` **两份都是 LOCAL**
          ⇒ 仍然判成私有 ⇒ 假发散照旧。**"唯一"这一条才是关键。**
        """
        cnt, loc = {}, set()
        for a, sz, n, ty in self.sym_list:
            if ty != 'STT_OBJECT':
                continue
            cnt[n] = cnt.get(n, 0) + 1
            if self.sym_bind.get((a, n)) == 'STB_LOCAL':
                loc.add(n)
        return {n for n in loc if cnt.get(n, 0) == 1}

    # --- 数据区：含最多数据符号的可写段（两侧因此指向同一批 vaddr）---
    def _pick_dregion(self):
        best, bestn = None, -1
        for va, fsz, msz, fl, off in self.segs:
            if not (fl & 2):
                continue
            lo, hi = va, va + msz
            n = sum(1 for nm, (a, sz) in self.data_syms.items() if lo <= a < hi)
            if n > bestn:
                best, bestn = (lo, hi), n
        return best

    # --- PLT：用 capstone 找 `ldr pc, [...]`，按 .rel.plt 顺序配名 ---
    def _build_plt(self):
        plt = self.elf.get_section_by_name('.plt')
        rel = self.elf.get_section_by_name('.rel.plt')
        if plt is None or rel is None:
            return {}, None, None
        dynsym = self.elf.get_section_by_name('.dynsym')
        names = []
        for r in rel.iter_relocations():
            try:
                names.append(dynsym.get_symbol(r['r_info_sym']).name)
            except Exception:
                names.append('?')
        a0, off, size = plt['sh_addr'], plt['sh_offset'], plt['sh_size']
        body = self.raw[off:off + size]
        ldrpc = []
        for ins in _MD.disasm(body, a0):
            if ins.mnemonic == 'ldr' and ins.op_str.replace(' ', '').startswith('pc,['):
                ldrpc.append(ins.address)
        m = {}
        for k, a in enumerate(ldrpc):
            if k == 0:            # PLT0 不配名
                continue
            if k - 1 < len(names):
                m[a - 8] = names[k - 1]
        return m, (ldrpc[0] - 4 if ldrpc else None), (ldrpc[-1] + 4 if ldrpc else None)

    def plt_name(self, pc):
        return self.plt_map.get(pc)

    def seg_of(self, addr):
        for va, fsz, msz, fl, off in self.segs:
            if va <= addr < va + msz:
                return (va, fsz, msz, fl, off)
        return None

    def addr2file(self, addr):
        s = self.seg_of(addr)
        if not s:
            return None
        va, fsz, msz, fl, off = s
        d = addr - va
        return off + d if d < fsz else None

    def name_of(self, addr):
        best = None
        for a, sz, nm, ty in self.sym_list:
            if a <= addr and (sz == 0 or addr < a + sz):
                best = nm
            if a > addr:
                break
        return best

    @property
    def dregion(self):
        return self._dregion


# --------------------------------------------------------------------------- #
def _linkmeta_ranges(b):
    """link 元数据段（GOT/.dynamic/...）—— 两侧各自的都要排除。"""
    out = []
    for sname in ('.got', '.got.plt', '.dynamic', '.dynsym', '.dynstr', '.hash',
                  '.plt', '.rel.plt', '.rel.dyn'):
        sec = b.elf.get_section_by_name(sname)
        if sec is not None and sec['sh_size']:
            out.append((sec['sh_addr'], sec['sh_addr'] + sec['sh_size']))
    return out


def _build_spans(*bins):
    """可比访问区 = **两侧**具名数据对象的地址区间并集（排除 link 元数据段）。

    ★ 为什么不是"只取工厂"（第 59 轮）→ 为什么必须改成"两侧取并集"（GAP 17.14）
      只取工厂的后果：**我方自己的数据对象整体在区外被过滤**。实测 `mxml` 的 file-static
      `_mxml_key` 我方编译后落在我们自己的 `.bss`（0x4E32C4，工厂的在 0x3B1E34）
      ⇒ 工厂侧"读了 `_mxml_key`"被记成 `仅F`，而我方读自己那份**根本没被记录**
      ⇒ **20 个 mxml 函数被判 DIVERGE**，其实只是"双方各自访问私有副本"（语义等价）。
      ⇒ 并集既保留"排除 GOT/link 元数据"的原意，又不再盲掉我方自己的数据。
      ★ 与 §"按符号名归一对 LOCAL 私有副本"配套使用；两者必须一起改，否则会从
        "盲掉我方" 变成 "我方多出"（同一个假发散的另一个方向）。
    ★ 用 `sym_list`（**保留同名多份**）而不是 `data_syms`（以名字为键会折叠掉同名）。
    """
    spans, bad = [], []
    for b in bins:
        bad += _linkmeta_ranges(b)
        for a, sz, n, ty in b.sym_list:
            if ty != 'STT_OBJECT' or not sz or sz > 1 << 20:
                continue
            lo, hi = a, a + sz
            if any(not (hi <= b0 or lo >= b1) for b0, b1 in bad):
                continue
            spans.append((lo, hi))
    spans.sort()
    merged = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            p_lo, p_hi = merged[-1]
            merged[-1] = (p_lo, max(p_hi, hi))
        else:
            merged.append((lo, hi))
    return merged


def _in_spans(sp, addr):
    if not sp:
        return False
    i = bisect.bisect_right(sp, (addr, 1 << 32)) - 1
    return i >= 0 and sp[i][0] <= addr < sp[i][1]


def run_func(b, fname, args, steps=20000, stub_ret=None, spans=None, syms_for_final=None,
             mode=None, _retry=True):
    """执行 fname(args)。mode=None 时自动判 ARM/Thumb（先 ARM，遇 INSN_INVALID 再试 Thumb）。

    ★ ARM/Thumb 自动判定（第 59 轮实测）：我们的产物里有个别函数是 **Thumb**，
      在 ARM 模式下执行会以 `UC_ERR_INSN_INVALID` 停下 ⇒ 与工厂的差异全是**假发散**。
      判据：ARM 模式仅在**头几条指令内**就 INSN_INVALID 时，改用 Thumb 重试。
    """
    if mode is None:
        mode = UC_MODE_ARM
    """在 b 里执行 fname(args)。region=(lo,hi) 限定"可比数据区"（两侧交集）。

    ★ 为什么按**地址**而不是按符号名记访存指纹（第 59 轮实测暴露）
      同一个 vaddr 在两个二进制里可能挂着**不同的符号名**：工厂侧叫 `m_ui`，
      我们的产物因为额外嵌入了 `factory_image.S` 的 `DAT_*` 别名，同一地址上会解析成
      `DAT_003af2b4`。首版按名字比较 ⇒ 大量"仅F有 / 仅O有"的**假发散**（实测几十条）。
      地址两侧一致（0x3ae5c4 起）⇒ **按地址比才是正确刻度**，名字只用于人读标注。
    """
    if fname not in b.funcs:
        return {'error': 'no-such-func'}
    addr, _size = b.funcs[fname]
    mu = Uc(UC_ARCH_ARM, mode)
    # ★ 必须开 FPU（CPACR + FPEXC.EN **两个都要**）：我们的产物是
    #   `-mfpu=neon -mfloat-abi=hard` 编的，含 VFP/NEON 指令；Unicorn 默认两者都没开
    #   ⇒ 一执行到 `vpush {d8,d9}` 就 UC_ERR_INSN_INVALID。
    #   最小复现（第 59 轮实测，同 4 条指令）：
    #       不加设置         → 执行 3 条即 INSN_INVALID
    #       CPACR=0xF00000   → 仍然 3 条即 INSN_INVALID（**只设 CPACR 不够**）
    #       +FPEXC=0x40000000→ 正常执行
    try:
        mu.reg_write(ac.UC_ARM_REG_C1_C0_2, 0x00F00000)
        mu.reg_write(ac.UC_ARM_REG_FPEXC, 0x40000000)
    except UcError:
        pass
    # ★ 不能"逐段 mem_map"：Unicorn 的 mem_map 只要与**已映射页**有重叠就整体失败
    #   （我们产物的 9 个 PT_LOAD 里，0x400fd0 / 0x4e00e0 / 0x5630c8 三段都跨进了
    #    前一段的页 ⇒ 整段未映射 ⇒ 后续 mem_write 报 WRITE_UNMAPPED）。
    #   正确做法：先把所有段的页区间**合并成不相交并集**一次映射，再逐段写文件内容。
    # ★ 注意：这里的局部变量**必须叫 pages**，不能叫 spans —— 否则会覆盖上面传入的
    #   `spans`（可比访问区过滤器），让过滤静默失效（第 59 轮踩过：表现为"过滤没生效"）。
    pages = sorted((va & ~0xFFF, (va + msz + 0xFFF) & ~0xFFF) for va, fsz, msz, fl, off in b.segs)
    merged = []
    for lo, hi in pages:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    for lo, hi in merged:
        if hi > lo:
            mu.mem_map(lo, hi - lo, 7)
    for va, fsz, msz, fl, off in b.segs:
        if fsz:
            mu.mem_write(va, b.raw[off:off + fsz])
        if msz > fsz:
            mu.mem_write(va + fsz, b'\x00' * (msz - fsz))
    mu.mem_map(STACK_BASE, STACK_SIZE, 7)
    mu.mem_map(SCRATCH, SCRATCH_SIZE, 7)
    mu.mem_map(SENTINEL & ~0xFFF, 0x1000, 7)
    mu.mem_write(SCRATCH, b'\x00' * SCRATCH_SIZE)
    mu.mem_write(SCRATCH + 0x100, b'A\x00')
    mu.mem_write(SCRATCH + 0x200, b'core\x00')

    sp = spans
    d = b.dregion
    ctx = {'insns': 0, 'calls': [], 'w': [], 'r': []}

    def code_hook(m, address, size_, user):
        ctx['insns'] += 1
        nm = b.plt_name(address)
        if nm is not None:
            if len(ctx['calls']) < MAX_TRACE:
                ctx['calls'].append(nm)
            m.reg_write(ac.UC_ARM_REG_R0, (stub_ret or {}).get(nm, 0))
            m.reg_write(ac.UC_ARM_REG_PC, m.reg_read(ac.UC_ARM_REG_LR))
            return
        if ctx['insns'] > steps:
            m.emu_stop()

    def mem_hook(m, access, address, size_, value, user):
        # ★ 按 (地址, 宽度, 读/写) 记录，**不带符号名** —— 名字两侧可能不同（见 run_func 头注释）
        # ★ 范围用「工厂具名数据对象的区间并集」（spans）⇒ GOT/link 元数据天然排除
        if sp is not None and not _in_spans(sp, address):
            return
        if sp is None and (d is None or not (d[0] <= address < d[1])):
            return
        if access == 17:
            if len(ctx['w']) < MAX_TRACE:
                ctx['w'].append((address, size_, 'W'))
        elif access == 16:
            if len(ctx['r']) < MAX_TRACE:
                ctx['r'].append((address, size_, 'R'))

    h1 = mu.hook_add(UC_HOOK_CODE, code_hook)
    h2 = mu.hook_add(UC_HOOK_MEM_WRITE, mem_hook)
    h3 = mu.hook_add(UC_HOOK_MEM_READ, mem_hook)

    mu.reg_write(ac.UC_ARM_REG_SP, STACK_BASE + STACK_SIZE - 0x100)
    mu.reg_write(ac.UC_ARM_REG_LR, SENTINEL)
    for i, v in enumerate(list(args)[:4]):
        mu.reg_write(ac.UC_ARM_REG_R0 + i, v & 0xFFFFFFFF)

    stopped = 'return'
    try:
        mu.emu_start(addr, SENTINEL, count=steps)
    except UcError as e:
        stopped = 'uc-error: %s @0x%x' % (e, mu.reg_read(ac.UC_ARM_REG_PC))
    r0 = mu.reg_read(ac.UC_ARM_REG_R0)
    # ★ Thumb 重试：ARM 模式在头几条指令就 INSN_INVALID ⇒ 改用 Thumb
    if (_retry and mode == UC_MODE_ARM and stopped != 'return'
            and 'INSN_INVALID' in stopped and ctx['insns'] <= 8):
        r = run_func(b, fname, args, steps, stub_ret, spans, syms_for_final,
                     mode=UC_MODE_THUMB, _retry=False)
        r['mode'] = 'thumb'
        return r
    # ★ 地址类返回值：把 ret 指向的内容一并带上（两侧各自的映像里比内容，而不是比地址）
    ret_content = ''
    if r0:
        try:
            if b.seg_of(r0 & 0xFFFFFFFF):
                blob = mu.mem_read(r0 & 0xFFFFFFFF, 64)
                # ★ 指向 C 字符串时只比到 NUL（否则会把相邻字符串的差异算进来 ⇒ 假发散）
                z = blob.find(b'\x00')
                ret_content = (blob[:z + 1] if 0 <= z < 64 else blob[:32]).hex()
        except UcError:
            ret_content = ''
    final = {}
    if d is not None:
        blob = mu.mem_read(d[0], d[1] - d[0])
        # ★ 最终内容也**只用一套符号名**（工厂的），两侧同名同址 ⇒ 可直接逐项比
        for nm, (sa, sz) in (syms_for_final or b.data_syms).items():
            if d[0] <= sa < d[1] and 0 < sz <= 64:
                final[nm] = blob[sa - d[0]:sa - d[0] + sz].hex()
    # ★ 显式释放：746 函数 × 2 二进制 ≈ 1500 个 Unicorn 实例（每个映射数 MB）。
    #   实测**大循环下会 MemoryError**（Unicorn C 侧内存未及时回收）。
    #   ⇒ 摘钩子 + 置空 + 交给 gc（批量循环里另有周期 gc.collect()）。
    for _h in (h1, h2, h3):
        try:
            mu.hook_del(_h)
        except Exception:
            pass
    del mu, code_hook, mem_hook
    return {'error': None, 'stopped': stopped, 'insns': ctx['insns'], 'ret': r0 & 0xFFFFFFFF,
            'ret_content': ret_content, 'mode': 'arm',
            'capped': ctx['insns'] >= steps,
            'calls_ext': ctx['calls'], 'writes': ctx['w'], 'reads': ctx['r'], 'final': final}


CORPUS = [
    ('zero', [0, 0, 0, 0]),
    ('strs', [SCRATCH + 0x100, SCRATCH + 0x200, SCRATCH, 0]),
    ('misc', [1, 2, 4, 0x1000]),
]


def norm_stop(s):
    """把停止原因归一化：只有「是否完成 / 以什么错停下」可比，PC 与指令数不可比。

    ★ 这条是被实测逼出来的：FBA_Load 两侧都走完 strcpy→sprintf→dlopen→dlerror
      然后都因读未映射内存而停；PC 不同（0x9e9c vs 0x4e42ac）、指令数不同（99 vs 119），
      但**停止类别相同**。若只比 "stopped" 字符串，这种强等价证据会被误判成发散。
    """
    if s == 'return':
        return 'return'
    if s.startswith('uc-error:'):
        for k in ('UC_ERR_READ_UNMAPPED', 'UC_ERR_WRITE_UNMAPPED', 'UC_ERR_FETCH_UNMAPPED',
                  'UC_ERR_INSN_INVALID', 'UC_ERR_READ_PROT', 'UC_ERR_WRITE_PROT',
                  'UC_ERR_EXCEPTION', 'UC_ERR_MEM_FETCH_PROT'):
            if k in s:
                return k
        return 'uc-error'
    return s


# ★ 外部调用的「等价别名」：只放**已确认同一语义**的项，且必须在报告里同时给出原始名。
#   `_Znwj` = C++ `operator new(unsigned int)` —— 工厂侧走 libstdc++ 的 new，我们侧直接
#   `malloc`。二者在本项目观察到的语义等价（同一分配器、同一失败语义）。归为**等价别名**，
#   而不是当作"多调/少调"。任何新增别名都必须在这里写明依据。
CALL_ALIAS = {
    '_Znwj': 'malloc', '_Znaj': 'malloc', '_Znam': 'malloc', '_Znwm': 'malloc',
    '_ZdlPv': 'free', '_ZdaPv': 'free',
}


def norm_calls(seq):
    return [CALL_ALIAS.get(x, x) for x in seq]


# Ghidra 合成名（把地址编进了名字）——归因时**优先跳过**，因为工厂里没有这些名字 ⇒ 无法跨侧配对
RE_SYNTH = re.compile(r'^(?:DAT|UNK)_[0-9a-fA-F]{6,8}$')


def fp_key(b, t, spec_private):
    """访存指纹归一：`(地址,宽度,读/写)` → **可比键**（GAP 17.14）。

    规则（**以工厂的"是否纯私有"为准**，因为工厂才是规格）：
      * 覆盖该地址的符号名 ∈ 工厂的 `pure_private`（工厂只有 LOCAL 定义、没有同名 GLOBAL）
        ⇒ 该对象的**地址是实现细节** ⇒ 键 = `('LN', 名字, 偏移, 宽度, 读写)`，两侧**按名字配对**
          （我方另持私有副本是合法的：mxml 的 file-static `_mxml_key`、`m_ui` 等）。
      * 否则（工厂里是 GLOBAL，或同名既有 LOCAL 又有 GLOBAL，或工厂根本没有这个名字）
        ⇒ **地址有意义** ⇒ 键 = `('A', 地址, 宽度, 读写)`。
        ★ GLOBAL 对象必须落在工厂地址（其它模块/烧死的绝对地址会引用它）——这正是
          `ArchivePath` 那类"绑错地址"缺陷的信号，**不得**因为名字相同就放行。
    """
    a, w, rw = t
    hit = b.nearest_sym(a)
    if hit:
        nm, sa = hit
        if nm in spec_private:
            # ★ 显示里**必须带上绝对地址**：同名两份时只写 `handle+0` 读者无法判断是哪一份
            #   ⇒ 失去可审计性（本条的实测教训：曾因此把"同址"误读成"异址"）。
            return (('LN', nm, a - sa, w, rw),
                    '%s+%d:%d:%s@0x%x' % (nm, a - sa, w, rw, a))
    return ('A', a, w, rw), '0x%08x:%d:%s' % (a, w, rw)


def _fp_diff(kf, shf, ko, sho):
    """访存指纹的差异展示 —— **按多重集**（计数）而不是按集合。

    ★ 为什么必须按多重集（GAP 17.14 的可审计性修复）：旧写法用集合差集，
      于是"同一地址但**次数不同**"会打印成 `仅F=[] 仅O=[]`（两侧都空）——
      读者完全看不出差异在哪（实测 `TestUSBJoy` 就是这种：写地址相同、次数不同）。
      现在打印 `地址 ×次数差`。
    """
    Cf, Co = Counter(kf), Counter(ko)
    df = {}
    for k, s in zip(kf, shf):
        df.setdefault(k, s)
    do = {}
    for k, s in zip(ko, sho):
        do.setdefault(k, s)
    ex_f = ['%s ×%d' % (df[k], n - Co.get(k, 0)) for k, n in sorted(Cf.items())
            if n > Co.get(k, 0)]
    ex_o = ['%s ×%d' % (do[k], n - Cf.get(k, 0)) for k, n in sorted(Co.items())
            if n > Cf.get(k, 0)]
    return '仅F=%s 仅O=%s' % (ex_f[:6], ex_o[:6])


def norm_fp(b, tuples, spec_private, fspans):
    """→ (可比较的键多重集, 人类可读的展示列表)

    ★ 额外过滤（GAP 17.14）：**按地址配对（'A' 形）的访问必须落在"工厂侧有具名对象的区段"内**。
      理由：我方自己的无名区域（例：我们 `.bss` 头部的填充字节 0x4E3000）在工厂侧**没有对应区段**，
      拿它去比绝对地址必然不对称 —— 实测 `__libc_csu_init` / `_mxml_init` 就因此凭空多出"仅O"。
      我方**有名字**的私有对象不受影响：它们走 'LN' 形按名字配对。
    """
    keys, show = [], []
    for t in tuples:
        k, s = fp_key(b, t, spec_private)
        if k[0] == 'A' and not _in_spans(fspans, k[1]):
            continue
        keys.append(k)
        show.append(s)
    return sorted(keys), sorted(show)


# --------------------------------------------------------------------------- #
# 棘轮台账：格式 + 语义（**纯函数**，可离线自证；见 GAP 17.10）
# --------------------------------------------------------------------------- #
LEDGER_STEPS_RE = re.compile(r'^#\s*steps\s*=\s*(\d+)\s*$')
LEDGER_ESC_RE = re.compile(r'^#\s*escalate\s*=\s*(\d+)\s*$')

# 触到步数上限 ⇒ 以 ESCALATE_FACTOR× 预算**重试一次**。
# 为什么必须有它：被判据忽略的东西会因为"跑不完"落进 TRUNC 桶；若台账在低预算下重写，
# 这些函数就会被**静默删出台账**（GAP 17.10 实证：`libiconvlist` / `xmp3_PolyphaseStereo`
# 在 3000 步是 TRUNC、在 20000 步是 **DIVERGE**）。代价只在"确实截断"的函数上付。
ESCALATE_FACTOR = 20
# 为什么是 20 而不是 10：实测 `AudioProcess` 工厂侧需要 **30,202 条指令**才跑完，而我们只要
# 28,719 条（同一语义，跨编译器的每轮迭代指令数不同）⇒ 10× (=30,000) **刚好卡在边界外**，
# 会把"跑得慢"误判成"不可判"。判据的预算必须留出**合法的编译器抖动余量**。


def void_fns_from_corpus():
    """→ (set(返回类型为 void 的函数名), 说明文本)

    为什么需要（GAP 17.12）：**`void` 函数的 r0 不是输出，只是残留值**。实测 `AudioProcess`
    （两侧 3 组输入、除 ret 外**全部观测量一致**）：
      工厂 r0 = `0xf4240`（= 它最后一次 `__aeabi_idiv(0xf4240, …)` 的被除数）
      我们 r0 = `0x0`
    ⇒ 把残留值当判据会产出**假发散**（本项目第 4 次踩"把非语义量当判据"）。
    语料 `golden/ghidra-perfn.tar.gz`（仓内，253 KB）每个函数文件第 6 行是签名 ⇒ 覆盖全部函数；
    语料缺失时不报错、但**回落到"比 ret"**（更严的一侧，绝不静默放行）。
    """
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import ghidra_corpus
        d, src = ghidra_corpus.resolve_corpus()
    except Exception as e:                                    # pragma: no cover
        return None, '语料不可用（%s）⇒ 回落为「比 ret」' % type(e).__name__
    if not d or not os.path.isdir(d):
        return None, '语料不可用（%s）⇒ 回落为「比 ret」' % (src,)
    out = set()
    for fn in os.listdir(d):
        if not fn.endswith('.c'):
            continue
        try:
            with open(os.path.join(d, fn), encoding='utf-8', errors='replace') as fh:
                head = [next(fh) for _ in range(14)]
        except Exception:
            continue
        for ln in head:
            m = re.match(r'^void\s+([A-Za-z_]\w*)\s*\(', ln)
            if m:
                out.add(m.group(1))
                break
    return out, '语料 %s：void 函数 %d 个' % (os.path.basename(d), len(out))



def read_ledger_text(txt):
    """台账文本 → (declared_steps|None, declared_escalate|None, [名字])。"""
    steps = esc = None
    names = []
    for ln in txt.splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith('#'):
            m = LEDGER_STEPS_RE.match(s)
            if m:
                steps = int(m.group(1))
            m = LEDGER_ESC_RE.match(s)
            if m:
                esc = int(m.group(1))
            continue
        names.append(s)
    return steps, esc, names


def ledger_steps_ok(declared_steps, declared_esc, actual_steps, actual_esc):
    """★ 台账必须在**同一判据强度**下评测：步数预算或放大预算不一致 ⇒ fail-closed。

    为什么必须硬失败而不是告警：`--update-ledger` 在低预算下会把"其实有分歧、只是跑不完"
    的函数判成 TRUNC 并**从台账里删掉** ⇒ 台账静默变弱、CI 照样全绿。
    """
    return (declared_steps is not None and int(declared_steps) == int(actual_steps)
            and declared_esc is not None and int(declared_esc) == int(actual_esc))


def ledger_update(old, diverging, undecidable):
    """棘轮更新语义（纯函数）：

      保留 = 本轮发散 ∪ (旧台账 ∩ 本轮**不可判**)
      移除 = 旧台账里本轮被**明确判为 PASS/INFO** 的项

    ★ 核心不变式：**TRUNC/SKIP ≠ 已收敛**。不可判的项必须留在台账里当债务，
      否则"未知"会被静默改写成"没问题"——这正是台账最容易烂掉的方式。
    """
    keep = set(diverging) | (set(old) & set(undecidable))
    removed = sorted(set(old) - keep)
    kept_undec = sorted((set(old) & set(undecidable)) - set(diverging))
    return sorted(keep), removed, kept_undec


def compare(bf, bo, fname, steps=20000, corpus=None, void_fns=None, out=None):
    rows, verdict = [], 'PASS'
    # ★ 可比访问区 = **两侧**具名数据对象的区间并集（排除 .got/.dynamic 等 link 元数据）
    spans = _build_spans(bf, bo)
    # ★ 访存指纹的归一口径以**工厂的符号绑定**为准（工厂是规格）
    spec_private = bf.pure_private()   # 工厂里"唯一且 LOCAL"的名字（地址是实现细节）
    fspans = _build_spans(bf)          # 工厂侧单独的可比区段（用于"按地址配对"的过滤）
    # ★ 最终内容两侧共用**工厂的符号名**（同址同名才可比）
    kw = dict(steps=steps, spans=spans, syms_for_final=bf.data_syms)
    ret_unjudged = False
    for cname, args in (corpus or CORPUS):
        rf = run_func(bf, fname, args, **kw)
        ro = run_func(bo, fname, args, **kw)
        if rf.get('error') or ro.get('error'):
            rows.append((cname, 'SKIP', rf.get('error'), ro.get('error')))
            continue
        cap_f, cap_o = rf['capped'], ro['capped']
        cap_both = cap_f and cap_o
        cap_asym = cap_f != cap_o
        if cap_both or cap_asym:
            # ★ 只要**任一侧**触到步数上限，本组就**不可判**：
            #   拿"跑完的一侧"与"被截断的一侧"比，差异只反映截断位置，**不是语义差异**。
            #   （实测 `AudioProcess`：工厂 30,202 条才跑完、我们 28,719 条 ⇒ 在 3000 步预算下
            #    会凭空多出 `calls_ext`/`data-reads` 差异 ⇒ **假发散**。）
            why = ('两侧均触步数上限(%d)' % steps) if cap_both else \
                  ('仅一侧触步数上限(%d)（F=%s O=%s）' % (steps, cap_f, cap_o))
            rows.append((cname, 'trunc', rf['ret'], ro['ret'], rf['insns'], ro['insns'],
                         'return', 'return', [],
                         '%s ⇒ 本组不可判（截断的一侧无观测力；需能终止的输入或提高 --steps）' % why))
            continue
        diffs = []
        sf, so = norm_stop(rf['stopped']), norm_stop(ro['stopped'])
        if sf != so:
            diffs.append('stop F=%s O=%s%s' % (sf, so, ' (cap-asym)' if cap_asym else ''))
        # ★ ret 只在**两侧都正常返回**且**都没被截断**时才是判据
        if sf == 'return' and so == 'return' and (not cap_f) and (not cap_o) and rf['ret'] != ro['ret']:
            # ★ 地址类返回值（指向各自映像里的字符串/表）：比**内容**而不是比地址。
            #   实测：`_Z11zlibVersionv` 返回各自的版本串地址（0x2dc7dc vs 0x4da2a3），
            #   内容相同 ⇒ 语义等价；只比数值会误判成发散。
            if rf['ret_content'] and rf['ret_content'] == ro['ret_content']:
                pass
            elif void_fns is not None and fname in void_fns:
                # ★ void 函数的 r0 **不是输出**（实测 AudioProcess：工厂残留 0xf4240、
                #   我们残留 0x0，其余观测量全一致）⇒ 不作判据（GAP 17.12）
                ret_unjudged = True
            else:
                diffs.append('ret F=0x%x O=0x%x' % (rf['ret'], ro['ret']))
        cf, co = norm_calls(rf['calls_ext']), norm_calls(ro['calls_ext'])
        wk_f, wsh_f = norm_fp(bf, rf['writes'], spec_private, fspans)
        wk_o, wsh_o = norm_fp(bo, ro['writes'], spec_private, fspans)
        if wk_f != wk_o:
            diffs.append('data-writes %s' % _fp_diff(wk_f, wsh_f, wk_o, wsh_o))
        rk_f, rsh_f = norm_fp(bf, rf['reads'], spec_private, fspans)
        rk_o, rsh_o = norm_fp(bo, ro['reads'], spec_private, fspans)
        if rk_f != rk_o:
            diffs.append('data-reads %s' % _fp_diff(rk_f, rsh_f, rk_o, rsh_o))
        common = set(rf['final']) & set(ro['final'])
        fd = [k for k in sorted(common) if rf['final'][k] != ro['final'][k]]
        if fd:
            diffs.append('data-final 不同 %d 项 %s' % (len(fd), fd[:6]))
        # ★ 外部调用判据放在最后：区分「内联等价」与「真的少调/多调/顺序变」
        note = ''
        if cf != co:
            only_missing = [x for x in cf if x not in co]
            only_extra = [x for x in co if x not in cf]
            if (not diffs) and only_missing and (not only_extra):
                # 其余观测量**全部一致** + 只是少调了工厂的某些调用 ⇒ 内联/等价实现
                note = '内联等价: 仅工厂侧调用 %s' % (only_missing[:6],)
            else:
                raw = '' if (rf['calls_ext'] == ro['calls_ext']) else ' (原始名不同)'
                diffs.append('calls_ext F=%s O=%s%s' % (cf[:10], co[:10], raw))
        if diffs:
            verdict = 'DIVERGE'
        rows.append((cname, 'DIVERGE' if diffs else ('info' if note else 'ok'),
                     rf['ret'], ro['ret'], rf['insns'], ro['insns'], sf, so, diffs, note))
    # 若**没有任何一组**能给出判定（全是 trunc）⇒ 该函数整体不可判
    if rows and all(r[1] == 'trunc' for r in rows):
        verdict = 'TRUNC'
    if out is not None:
        out['ret_unjudged'] = 1 if ret_unjudged else 0
    return verdict, rows


# --------------------------------------------------------------------------- #
def _zig():
    z = os.environ.get('ZIG')
    if z and os.path.exists(z):
        return z
    cand = os.path.join(os.path.dirname(sys.executable), '..', 'Lib', 'site-packages',
                        'ziglang', 'zig.exe')
    if os.path.exists(cand):
        return os.path.abspath(cand)
    return None


SYN_SRC = '''
unsigned short g_tab[4] = {7, 9, 11, 13};
unsigned g_acc;
unsigned probe(unsigned s) {
    unsigned i, t = 0;
    for (i = 0; i < 10; i++) {
        t += i * %s + s;
        g_tab[i & 3] = (unsigned short)(t + g_tab[i & 3]);
    }
    g_acc = t;
    return t + g_tab[1];
}
void _start(void) { for (;;) probe(1); }
'''


def self_test():
    """正/反双向自证：不只证"能跑"，必须证"能分辨"。

    用一个**独立于本项目数据**的对照：同一份合成源码
      · 编译两次 → 必须 PASS（同时验证构建确定性）
      · 改一个乘数常量 → 必须 DIVERGE（验证判据真的能抓到语义差异）
    再叠加本项目真实函数的可执行性前提检查。
    """
    chk = []

    def c(tag, got, want):
        chk.append((tag, got, want, got == want))

    zig = _zig()
    if not zig:
        c('前置：能找到 zig（设 ZIG=<path>）', '未找到', '<path>')
        return chk
    tmpd = tempfile.mkdtemp(prefix='diffexec_')
    env = dict(os.environ)
    env['ZIG_GLOBAL_CACHE_DIR'] = os.path.join(tmpd, 'zc')

    def build(src, out, srcname=None):
        """srcname 固定时（同源两次）可检验构建确定性。"""
        p = os.path.join(tmpd, srcname or (os.path.basename(out) + '.c'))
        open(p, 'w', encoding='utf-8', newline='\n').write(src)
        r = subprocess.run([zig, 'cc', '-target', 'arm-linux-musleabihf', '-mfloat-abi=hard',
                            '-mfpu=neon', '-static', '-nostdlib', '-Wl,-e,probe', '-O1',
                            p, '-o', out], capture_output=True, env=env)
        return r.returncode, (r.stderr or b'').decode('utf-8', 'replace')[-300:], p

    a1 = os.path.join(tmpd, 'a1.elf')
    a2 = os.path.join(tmpd, 'a2.elf')
    b1 = os.path.join(tmpd, 'b1.elf')
    # ★ 确定性检查必须**同一个源文件名**编两次（否则 STT_FILE/构建 id 会不同 ⇒ 假 FAIL）
    rc1, e1, _ = build(SYN_SRC % '3', a1, srcname='syn3.c')
    rc2, e2, _ = build(SYN_SRC % '3', a2, srcname='syn3.c')
    rc3, e3, _ = build(SYN_SRC % '5', b1, srcname='syn5.c')
    if rc1 or rc2 or rc3:
        c('前置：能用 zig 编出 ARM32 静态 ELF', 'rc=%d/%d/%d %s' % (rc1, rc2, rc3, (e1 or e2 or e3)[:120]), 'rc=0/0/0')
        return chk
    c('前置：合成 ELF 可产出', os.path.getsize(a1) > 0, True)
    h1, h2, h3 = [hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16] for p in (a1, a2, b1)]
    c('正例  同源两次编译 → 逐字节相同（构建确定性）', h1 == h2, True)
    c('反例  改一个常量 → 产物不同（可分辨前提）', h1 != h3, True)

    BA1, BA2, BB1 = Bin(a1), Bin(a2), Bin(b1)
    c('前置：合成 ELF 里能找到 probe 符号', 'probe' in BA1.funcs, True)
    v_ok, _ = compare(BA1, BA2, 'probe', 4000)
    c('正例  同源两产物对拍 → PASS', v_ok, 'PASS')
    v_bad, rows_bad = compare(BA1, BB1, 'probe', 4000)
    c('反例  改常量后对拍 → DIVERGE', v_bad, 'DIVERGE')
    got_ret = [r for r in rows_bad if r[1] == 'DIVERGE' and any('ret' in str(x) for x in (r[8] or []))]
    c('反例  差异定位到 ret（不是"说不清的 divergence"）', bool(got_ret), True)

    # ---- 棘轮台账语义自证（纯函数；不依赖本项目数据）--------------------------
    # 为什么单独证这一段：台账是"只许减少"的棘轮，它自己烂掉会让 CI 全绿而掩盖真分歧。
    # GAP 17.10 的实证：低预算重写台账会**删掉**在高预算下确实发散的函数。
    st, se, nm = read_ledger_text(
        '# c1\n# steps=3000\n# escalate=30000\nfoo\nbar\n\n# tail\nbaz\n')
    c('台账解析  steps 声明读出', st, 3000)
    c('台账解析  escalate 声明读出', se, 30000)
    c('台账解析  名字逐行读出且跳过注释', nm, ['foo', 'bar', 'baz'])
    st2, se2, nm2 = read_ledger_text('foo\nbar\n')
    c('台账解析  缺 steps 声明 ⇒ 读出 None（供 fail-closed 用）', (st2, se2), (None, None))
    c('强度一致性  完全一致 ⇒ ok', ledger_steps_ok(3000, 30000, 3000, 30000), True)
    c('强度一致性  steps 不一致 ⇒ 拒绝', ledger_steps_ok(20000, 30000, 3000, 30000), False)
    c('强度一致性  escalate 不一致 ⇒ 拒绝', ledger_steps_ok(3000, 30000, 3000, 100), False)
    c('强度一致性  台账无声明 ⇒ 拒绝（fail-closed，不放行）',
      ledger_steps_ok(None, None, 3000, 30000), False)
    # ★ 核心不变式：TRUNC/SKIP 不是"已收敛"
    keep, removed, ku = ledger_update(['a', 'b', 'c'], ['a'], {'b'})
    c('台账语义  发散项保留', 'a' in keep, True)
    c('台账语义  **不可判项也必须保留**（不得当已收敛删掉）', 'b' in keep, True)
    c('台账语义  明确判为 PASS/INFO 的项才移除', removed, ['c'])
    c('台账语义  报出"仍不可判"清单（供审计）', ku, ['b'])
    keep2, removed2, _ = ledger_update(['x'], [], set())
    c('台账语义  旧项本轮判 PASS ⇒ 移除', (keep2, removed2), ([], ['x']))
    c('台账语义  新增发散自动进入台账', ledger_update([], ['z'], set())[0], ['z'])

    # 本项目真实函数：可执行性前提（不判等价，只证"两侧都能跑到停止"）
    if os.path.exists(FACTORY) and os.path.exists(OURS):
        BF, BO = Bin(FACTORY), Bin(OURS)
        c('前置：工厂 .symtab 可用（FUNC > 700）', len(BF.funcs) > 700, True)
        c('前置：两侧 PLT 都解析出名字', len(BF.plt_map) > 0 and len(BO.plt_map) > 0, True)
        n = 'FBA_Load'
        if n in BF.funcs and n in BO.funcs:
            rf = run_func(BF, n, [0, 0, 0, 0], 4000)
            ro = run_func(BO, n, [0, 0, 0, 0], 4000)
            # ★ 真实业务函数常需文件系统（FBA_Load 要 dlopen 真实 core）⇒ 允许"同类别停下"。
            #   实测两侧都走完 strcpy→sprintf→dlopen→dlerror 后同类别停 ⇒ 这是等价证据。
            c('正例  真实函数 %s 两侧**停止类别相同**（%s）' % (n, norm_stop(rf['stopped'])),
              norm_stop(rf['stopped']) == norm_stop(ro['stopped']), True)
            c('正例  真实函数 %s 两侧**外部调用序列相同**' % n,
              rf['calls_ext'] == ro['calls_ext'], True)
            c('前提  两侧数据区**起始 vaddr 相同**（内存可直接对拍）',
              BF.dregion is not None and BO.dregion is not None
              and BF.dregion[0] == BO.dregion[0], True)
            # ★ 同名数据符号（LOCAL/GLOBAL 同名）必须被**识别出来**，不能静默折叠
            c('前提  工厂存在同名数据符号（ArchivePath 一例，实测）',
              len(BF.dup_objs.get('ArchivePath', [])) >= 2, True)
            c('前提  我方 ArchivePath 为单一定义（生成器只映射了一个）',
              len(BO.dup_objs.get('ArchivePath', [])) <= 1, True)
            # ---- 访存指纹归一：LOCAL 私有副本 / GLOBAL 必须同址（GAP 17.14）----
            c('前提  工厂里 `_mxml_key` 是 LOCAL（文件私有 ⇒ 私有副本合法）',
              BF.bind_of('_mxml_key'), 'STB_LOCAL')
            c('前提  工厂里 `key2` 是 GLOBAL（必须落在工厂地址）',
              BF.bind_of('key2'), 'STB_GLOBAL')
            sb = BF.pure_private()
            c('前提  工厂里 `_mxml_key` 是纯私有（LOCAL 且无同名 GLOBAL）', '_mxml_key' in sb, True)
            c('前提  工厂里 `m_ui` 是纯私有', 'm_ui' in sb, True)
            c('前提  工厂里 `key2` 不是纯私有（GLOBAL ⇒ 必须同址）', 'key2' not in sb, True)
            c('前提  工厂里 `handle` 不是纯私有（**同名 LOCAL+GLOBAL** ⇒ 必须同址）',
              'handle' not in sb, True)
            # ★ 地址一律**从符号表查**，不手写常量（手写常量曾因我自己算错十六进制而误报）
            f_key = sorted(a for a, sz, n, ty in BF.sym_list if n == '_mxml_key')
            o_key = sorted(a for a, sz, n, ty in BO.sym_list if n == '_mxml_key')
            priv = [a for a in o_key if a not in f_key]
            c('正例  工厂与我方各有 `_mxml_key`；我方另有**私有副本**（地址不同、名字相同）',
              bool(f_key) and bool(priv), True)
            k1, _ = fp_key(BF, (f_key[0], 4, 'R'), sb)
            k2, _ = fp_key(BO, (priv[0], 4, 'R'), sb)
            c('正例  纯私有符号的**私有副本** ⇒ 两侧同一个键（不再假发散）', k1, k2)
            # ★ 同名 LOCAL+GLOBAL（`handle`）⇒ 必须按地址，且**同址必须同键**
            h = sorted(a for a, sz, n, ty in BF.sym_list if n == 'handle')
            c('前提  工厂有两个 `handle`（同名两份，都是 LOCAL ⇒ "唯一"条件不成立）', len(h) >= 2, True)
            kh_f, _ = fp_key(BF, (h[-1], 4, 'R'), sb)
            kh_o, _ = fp_key(BO, (h[-1], 4, 'R'), sb)
            c('正例  `handle` 同址 ⇒ 两侧同键（不得因"名字级 LOCAL 优先"而错配）', kh_f, kh_o)
            f_g = sorted(a for a, sz, n, ty in BF.sym_list if n == 'key2')
            g1, _ = fp_key(BF, (f_g[0], 4, 'R'), sb)
            g2, _ = fp_key(BO, (f_g[0] + 0x40, 4, 'R'), sb)
            c('反例  GLOBAL 符号 ⇒ 按**地址**配对，异址必不同键（ArchivePath 类缺陷的信号）',
              (g1 != g2) and g1[0] == 'A', True)
            c('反例  窄化必须仍被检出（宽度进键）',
              fp_key(BF, (0x3BC40C, 4, 'R'), sb)[0] != fp_key(BF, (0x3BC40C, 1, 'R'), sb)[0], True)
            # ---- 回归锚点：把"非语义量"当判据的两类假发散（GAP 17.12）-------------
            vf, vmsg = void_fns_from_corpus()
            if vf:
                c('正例  void 集合从语料解析出来（AudioProcess 在其中）',
                  'AudioProcess' in vf, True)
                c('正例  void 集合非平凡（>50 个）', len(vf) > 50, True)
                # ★ 只在一侧触上限时**不得**判 DIVERGE（否则把"跑得慢"当成"语义不同"）
                v_a, _ = compare(BF, BO, 'AudioProcess', 3000, void_fns=vf)
                c('反例  一侧触上限（3000 步）⇒ 必须 TRUNC，不得 DIVERGE', v_a, 'TRUNC')
                # ★ void 函数在足够预算下只差 r0 ⇒ 必须 PASS（r0 是残留值，不是输出）
                o2 = {}
                v_b, _ = compare(BF, BO, 'AudioProcess', 60000, void_fns=vf, out=o2)
                c('反例  预算足够时 void 函数只差 r0 ⇒ PASS（r0 不作判据）', v_b, 'PASS')
                c('正例  上述判定确实发生了"r0 未作判据"', o2.get('ret_unjudged'), 1)
    return chk


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fn')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--batch', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--steps', type=int, default=20000)
    ap.add_argument('--out')
    ap.add_argument('--ledger', help='发散棘轮台账：只允许减少，不允许新增')
    ap.add_argument('--update-ledger', action='store_true', help='用当前发散集重写台账')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()

    if a.self_test:
        chk = self_test()
        bad = 0
        for tag, got, want, ok in chk:
            print('   %s  %-56s got=%s' % ('✓' if ok else '★FAIL', tag, got))
            if not ok:
                bad += 1
        print('   合计 %d 条，失败 %d 条' % (len(chk), bad))
        return 2 if bad else 0

    for p in (FACTORY, OURS):
        if not os.path.exists(p):
            sys.stderr.write('缺 %s\n' % p)
            return 11
    BF, BO = Bin(FACTORY), Bin(OURS)
    common = sorted(set(BF.funcs) & set(BO.funcs))

    if a.list:
        print('  两侧共有函数 %d 个（工厂 %d / 我们 %d）；数据区 F=%s O=%s'
              % (len(common), len(BF.funcs), len(BO.funcs), BF.dregion, BO.dregion))
        for n in common[:a.limit or 30]:
            print('   %-46s F@0x%08x(%d) O@0x%08x(%d)'
                  % (n, BF.funcs[n][0], BF.funcs[n][1], BO.funcs[n][0], BO.funcs[n][1]))
        return 0

    if a.fn:
        vf, _vmsg = void_fns_from_corpus()
        o = {}
        v, rows = compare(BF, BO, a.fn, a.steps, void_fns=vf, out=o)
        print('  %s ⇒ %s' % (a.fn, v))
        if o.get('ret_unjudged'):
            print('     [ret] 该函数返回类型为 void ⇒ r0 是残留值，**未作判据**（GAP 17.12）')
        for r in rows:
            if r[1] == 'SKIP':
                print('     [%s] SKIP %s/%s' % (r[0], r[2], r[3]))
            else:
                extra = ('  ' + '; '.join(map(str, r[8]))) if len(r) > 8 and r[8] else ''
                if len(r) > 9 and r[9]:
                    extra += '   [%s]' % r[9]
                print('     [%-7s] F:ret=0x%-8x ins=%-6d stop=%-22s' % (r[0], r[2], r[4], r[6]))
                print('     %-8s  O:ret=0x%-8x ins=%-6d stop=%-22s%s' % ('', r[3], r[5], r[7], extra))
        return 1 if v == 'DIVERGE' else 0

    if a.batch:
        names = common[:a.limit] if a.limit else common
        esc_steps = a.steps * ESCALATE_FACTOR
        void_fns, vmsg = void_fns_from_corpus()
        stats = {'PASS': 0, 'DIVERGE': 0, 'SKIP': 0, 'INFO': 0, 'TRUNC': 0}
        n_esc = 0                      # 靠放大预算才判出来的函数数
        n_voidret = 0                  # r0 因"返回类型 void"而未作判据的函数数
        voidret_names = []
        info_names = []
        det = []
        div_names_all = []
        trunc_names = []
        skip_names = []
        for i, n in enumerate(names):
            o = {}
            v, rows = compare(BF, BO, n, a.steps, void_fns=void_fns, out=o)
            if v == 'TRUNC':
                # ★ 放大重试：只对"确实截断"的函数付费，避免把分歧藏进"不可判"
                o2 = {}
                v2, rows2 = compare(BF, BO, n, esc_steps, void_fns=void_fns, out=o2)
                if v2 != 'TRUNC':
                    v, rows, o = v2, rows2, o2
                    n_esc += 1
            if o.get('ret_unjudged'):
                n_voidret += 1
                if len(voidret_names) < 40:
                    voidret_names.append(n)
            stats[v] += 1
            if (i + 1) % 25 == 0:
                gc.collect()          # ★ 见 run_func 末尾注释：不周期回收会 MemoryError
            if v == 'DIVERGE':
                div_names_all.append(n)
            elif v == 'TRUNC':
                trunc_names.append(n)
            elif v == 'SKIP':
                skip_names.append(n)
            if any(len(r) > 9 and r[9] for r in rows if r[1] in ('ok', 'info')):
                stats['INFO'] += 1
                if len(info_names) < 60:
                    info_names.append('  %-44s %s' % (n,
                                      '; '.join(r[9] for r in rows if len(r) > 9 and r[9])[:110]))
            if v == 'DIVERGE':
                for r in rows:
                    if r[1] == 'DIVERGE' and len(r) > 8 and r[8]:
                        det.append('  %-44s [%s] %s' % (n, r[0], '; '.join(map(str, r[8]))))
            if (i + 1) % 10 == 0:
                sys.stderr.write('   ... %d/%d\n' % (i + 1, len(names)))
        lines = ['=' * 96, 'diff_exec 批量对拍（工厂 vs 重建产物）', '=' * 96,
                 '  共有函数 %d；本轮 %d 个；每函数 3 组输入' % (len(common), len(names)),
                 '  判据强度：--steps %d；触上限者按 %d× 放大重试一次（本轮 %d 个靠放大才判出）'
                 % (a.steps, ESCALATE_FACTOR, n_esc),
                 '  返回类型：%s；r0 未作判据（void）的函数 %d 个'
                 % (vmsg, n_voidret),
                 '  汇总：PASS %d | DIVERGE %d | INFO(内联等价) %d | TRUNC(不可判) %d | SKIP %d'
                 % (stats['PASS'], stats['DIVERGE'], stats['INFO'], stats['TRUNC'], stats['SKIP']),
                 '', '  --- DIVERGE 明细（前 80）---']
        lines.extend(det[:80])
        lines.append('')
        lines.append('  --- INFO：外部调用被内联/等价实现，其余观测量全一致（前 60）---')
        lines.extend(info_names)
        # ★ 不可判 / 跳过必须**列名**：否则"没判"会被读成"没问题"（GAP 17.10）
        lines.append('')
        lines.append('  --- r0 未作判据：返回类型 void ⇒ r0 是残留值（不是"通过"，是"该项不适用"）---')
        lines.extend('  %s' % n for n in (voidret_names[:40] or ['（无）']))
        lines.append('')
        lines.append('  --- TRUNC：两侧均触步数上限，判据对其无观测力（不可判 ≠ 已收敛）---')
        lines.extend('  %s' % n for n in (trunc_names[:40] or ['（无）']))
        lines.append('')
        lines.append('  --- SKIP：一侧执行环境报错，本组无判据 ---')
        lines.extend('  %s' % n for n in (skip_names[:40] or ['（无）']))
        # ★ 同名数据符号冲突必须**列名**：以名字为键会静默折叠 ⇒ 归因错误 ⇒ 可能假 PASS
        dup_f = {k: v for k, v in BF.dup_objs.items() if len(v) > 1}
        dup_o = {k: v for k, v in BO.dup_objs.items() if len(v) > 1}
        both = sorted(set(dup_f) & set(dup_o))
        lines.append('')
        lines.append('  --- 同名数据符号（LOCAL/GLOBAL 同名，合法 ELF）：工厂 %d 个 / 我方 %d 个 '
                     '/ 两侧都有 %d 个 ---' % (len(dup_f), len(dup_o), len(both)))
        for n in both[:20]:
            lines.append('  %-28s 工厂 %s | 我方 %s' % (
                n, ['0x%x(sz=%d)' % (a, s) for a, s, _ in dup_f[n]],
                ['0x%x(sz=%d)' % (a, s) for a, s, _ in dup_o[n]]))
        if not both:
            lines.append('  （无）')
        # ★ 棘轮台账：只允许"发散函数减少"，不允许新增（防"修一个坏一个"）
        div_names = sorted(set(div_names_all))
        undecidable = set(trunc_names) | set(skip_names)
        rc = 1 if stats['DIVERGE'] else 0
        if a.ledger:
            old_steps = old_esc = None
            old = []
            if os.path.exists(a.ledger):
                txt = open(a.ledger, encoding='utf-8', errors='replace').read()
                old_steps, old_esc, old = read_ledger_text(txt)
            if a.update_ledger:
                keep, removed, kept_und = ledger_update(old, div_names, undecidable)
                os.makedirs(os.path.dirname(a.ledger) or '.', exist_ok=True)
                with open(a.ledger, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write('# diff_exec 发散棘轮台账（只允许减少）\n')
                    fh.write('# steps=%d\n' % a.steps)
                    fh.write('# escalate=%d\n' % esc_steps)
                    fh.write('# 生成：python tools/diff_exec.py --batch --steps %d '
                             '--ledger <本文件> --update-ledger\n' % a.steps)
                    fh.write('# ★ 评测时必须用**相同的 steps/escalate**，否则本工具 fail-closed '
                             '(exit 3) —— 见 GAP 17.10\n')
                    for n in keep:
                        fh.write(n + '\n')
                lines.append('')
                lines.append('  台账已重写：%d 项（发散 %d + 旧台账中本轮不可判 %d）-> %s'
                             % (len(keep), len(div_names), len(kept_und), a.ledger))
                lines.append('  收敛移除 %d 项：%s' % (len(removed), removed[:30]))
                if kept_und:
                    lines.append('  ★ 保留的"不可判"债务（TRUNC/SKIP ≠ 已收敛）：%s' % kept_und[:30])
                rc = 0
            else:
                if not ledger_steps_ok(old_steps, old_esc, a.steps, esc_steps):
                    lines.append('')
                    lines.append('  ★★ 判据强度不一致 ⇒ fail-closed（exit 3）')
                    lines.append('     台账声明 ： steps=%s escalate=%s'
                                 % (old_steps, old_esc))
                    lines.append('     本次评测 ： steps=%s escalate=%s' % (a.steps, esc_steps))
                    lines.append('     修法     ： 用同一强度重写台账 ——')
                    lines.append('                python tools/diff_exec.py --batch '
                                 '--steps %d --ledger %s --update-ledger' % (a.steps, a.ledger))
                    lines.append('     为什么   ： 低强度下"其实有分歧只是跑不完"的函数会变成 '
                                 'TRUNC 并被静默删出台账（GAP 17.10 实证 2 例）')
                    txt = '\n'.join(lines)
                    print(txt)
                    if a.out:
                        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
                            fh.write(txt + '\n')
                    return 3
                new = [n for n in div_names if n not in old]
                fixed = [n for n in old if n not in div_names and n not in undecidable]
                still_und = [n for n in old if n in undecidable]
                lines.append('')
                lines.append('  台账棘轮：既有 %d 项 | 本轮发散 %d 项 | ★新增 %d | 已收敛 %d '
                             '| 仍不可判（保留）%d'
                             % (len(old), len(div_names), len(new), len(fixed), len(still_und)))
                if new:
                    lines.append('  ★★ 新增发散（必须修或显式登记）：%s' % new[:20])
                    rc = 2
                else:
                    rc = 0
                if fixed:
                    lines.append('  ✓ 本轮收敛（明确判为 PASS/INFO）：%s' % fixed[:20])
                if still_und:
                    lines.append('  ⏸ 台账内但仍不可判（**不得当作已收敛**）：%s' % still_und[:20])

        txt = '\n'.join(lines)
        print(txt)
        if a.out:
            with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(txt + '\n')
        return rc

    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
