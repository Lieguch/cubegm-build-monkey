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
import hashlib
import os
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
        st = self.elf.get_section_by_name('.symtab')
        if st is not None:
            for s in st.iter_symbols():
                # ★ 必须用 s.name（字符串）；s['st_name'] 是 .strtab 的**偏移量(整数)**，
                #   用它会把符号表建成 {offset: (addr,size)} ⇒ 永远匹配不上函数名。
                a, sz, n, ty = s['st_value'], s['st_size'], s.name, s['st_info']['type']
                if a == 0 or not n:
                    continue
                self.sym_list.append((a, sz, n, ty))
                if ty == 'STT_FUNC':
                    if n not in self.funcs or sz > self.funcs[n][1]:
                        self.funcs[n] = (a, sz)
                elif ty == 'STT_OBJECT':
                    self.data_syms[n] = (a, sz)
        self.sym_list.sort()
        self._dregion = self._pick_dregion()
        self.plt_map, self.plt_lo, self.plt_hi = self._build_plt()

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
def _build_spans(bf):
    """可比访问区 = **工厂具名数据对象**的地址区间并集。

    ★ 为什么不是"数据段整体"（第 59 轮实测暴露）
      工厂的可写段里**包含 `.got`**（0x3b1cfc..），而我们的 `.got` 在 0x4e13c8
      ⇒ 若按"整段"比较，工厂的 GOT 槽读取会被计入、我们的同名读取落在区域外被过滤
      ⇒ 产生"仅F有 (0x3B1D04,4,R)"这类**假发散**（实测 4 个函数全中同一模式）。
      收紧到"具名数据对象"后：GOT/link-time 元数据天然被排除，只剩**真数据访问**可比。
    """
    bad = []
    for sname in ('.got', '.got.plt', '.dynamic', '.dynsym', '.dynstr', '.hash', '.plt', '.rel.plt'):
        sec = bf.elf.get_section_by_name(sname)
        if sec is not None and sec['sh_size']:
            bad.append((sec['sh_addr'], sec['sh_addr'] + sec['sh_size']))
    spans = []
    for nm, (a, sz) in bf.data_syms.items():
        if not sz or sz > 1 << 20:
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

    mu.hook_add(UC_HOOK_CODE, code_hook)
    mu.hook_add(UC_HOOK_MEM_WRITE, mem_hook)
    mu.hook_add(UC_HOOK_MEM_READ, mem_hook)

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
    return {'error': None, 'stopped': stopped, 'insns': ctx['insns'], 'ret': r0 & 0xFFFFFFFF,
            'ret_content': ret_content, 'mode': 'arm',
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


def compare(bf, bo, fname, steps=20000, corpus=None):
    rows, verdict = [], 'PASS'
    # ★ 可比访问区 = 工厂**具名数据对象**的区间并集（排除 .got/.dynamic 等 link 元数据）
    spans = _build_spans(bf)
    # ★ 最终内容两侧共用**工厂的符号名**（同址同名才可比）
    kw = dict(steps=steps, spans=spans, syms_for_final=bf.data_syms)
    for cname, args in (corpus or CORPUS):
        rf = run_func(bf, fname, args, **kw)
        ro = run_func(bo, fname, args, **kw)
        if rf.get('error') or ro.get('error'):
            rows.append((cname, 'SKIP', rf.get('error'), ro.get('error')))
            continue
        diffs = []
        sf, so = norm_stop(rf['stopped']), norm_stop(ro['stopped'])
        if sf != so:
            diffs.append('stop F=%s O=%s' % (sf, so))
        # ★ ret 只在**两侧都正常返回**时才是判据（任一侧因缺文件系统等异常停下时，
        #   r0 是故障瞬间的残留值，拿它比会产生假发散）
        if sf == 'return' and so == 'return' and rf['ret'] != ro['ret']:
            # ★ 地址类返回值（指向各自映像里的字符串/表）：比**内容**而不是比地址。
            #   实测：`_Z11zlibVersionv` 返回各自的版本串地址（0x2dc7dc vs 0x4da2a3），
            #   内容相同 ⇒ 语义等价；只比数值会误判成发散。
            if rf['ret_content'] and rf['ret_content'] == ro['ret_content']:
                pass
            else:
                diffs.append('ret F=0x%x O=0x%x' % (rf['ret'], ro['ret']))
        cf, co = norm_calls(rf['calls_ext']), norm_calls(ro['calls_ext'])
        if cf != co:
            raw = '' if (rf['calls_ext'] == ro['calls_ext']) else ' (原始名不同)'
            diffs.append('calls_ext F=%s O=%s%s' % (cf[:12], co[:12], raw))
        wf, wo = sorted(rf['writes']), sorted(ro['writes'])
        if wf != wo:
            diffs.append('data-writes 仅F=%s 仅O=%s'
                         % ([x for x in wf if x not in wo][:6], [x for x in wo if x not in wf][:6]))
        rf_, ro_ = sorted(rf['reads']), sorted(ro['reads'])
        if rf_ != ro_:
            diffs.append('data-reads 仅F=%s 仅O=%s'
                         % ([x for x in rf_ if x not in ro_][:6], [x for x in ro_ if x not in rf_][:6]))
        common = set(rf['final']) & set(ro['final'])
        fd = [k for k in sorted(common) if rf['final'][k] != ro['final'][k]]
        if fd:
            diffs.append('data-final 不同 %d 项 %s' % (len(fd), fd[:6]))
        if diffs:
            verdict = 'DIVERGE'
        rows.append((cname, 'DIVERGE' if diffs else 'ok', rf['ret'], ro['ret'],
                     rf['insns'], ro['insns'], sf, so, diffs))
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
        v, rows = compare(BF, BO, a.fn, a.steps)
        print('  %s ⇒ %s' % (a.fn, v))
        for r in rows:
            if r[1] == 'SKIP':
                print('     [%s] SKIP %s/%s' % (r[0], r[2], r[3]))
            else:
                extra = ('  ' + '; '.join(map(str, r[8]))) if len(r) > 8 and r[8] else ''
                print('     [%-7s] F:ret=0x%-8x ins=%-6d stop=%-22s' % (r[0], r[2], r[4], r[6]))
                print('     %-8s  O:ret=0x%-8x ins=%-6d stop=%-22s%s' % ('', r[3], r[5], r[7], extra))
        return 1 if v == 'DIVERGE' else 0

    if a.batch:
        names = common[:a.limit] if a.limit else common
        stats = {'PASS': 0, 'DIVERGE': 0, 'SKIP': 0}
        det = []
        for i, n in enumerate(names):
            v, rows = compare(BF, BO, n, a.steps)
            stats[v] += 1
            if v == 'DIVERGE':
                for r in rows:
                    if r[1] == 'DIVERGE' and len(r) > 8 and r[8]:
                        det.append('  %-44s [%s] %s' % (n, r[0], '; '.join(map(str, r[8]))))
            if (i + 1) % 10 == 0:
                sys.stderr.write('   ... %d/%d\n' % (i + 1, len(names)))
        lines = ['=' * 96, 'diff_exec 批量对拍（工厂 vs 重建产物）', '=' * 96,
                 '  共有函数 %d；本轮 %d 个；每函数 3 组输入' % (len(common), len(names)),
                 '  汇总：PASS %d | DIVERGE %d | SKIP %d' % (stats['PASS'], stats['DIVERGE'], stats['SKIP']),
                 '', '  --- DIVERGE 明细（前 80）---']
        lines.extend(det[:80])
        txt = '\n'.join(lines)
        print(txt)
        if a.out:
            with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(txt + '\n')
        return 1 if stats['DIVERGE'] else 0

    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
