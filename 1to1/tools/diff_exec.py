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
import json
import os
import re
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTORY = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
OURS = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')

# ★ 外部调用语义模型（GAP 17.16）。与本文件同目录 ⇒ 显式加 sys.path，
#   保证被 `--self-test` / `import diff_exec` 以任意 cwd 调用时都能找到。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import libc_model                                                    # noqa: E402

try:
    from unicorn import (UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE,
                         UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED,
                         UC_HOOK_MEM_FETCH_UNMAPPED,
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
# ★★★ R294（G1 主体）：**真实状态快照**。`--from-state <file>` 时，两侧都先写入同一份
#   数据区字节（由 guest shim 的 CGM_STATE_DUMP 在真实运行时落盘），再执行目标函数。
#   为什么是"根本解"而不是补丁：它把"每个函数都要手工造合法输入"降级为"一次快照、任意复用"，
#   从而消掉"因状态缺失而不可判"这整类（UI 链至今都卡在这里）。
#   格式：magic "CGMST001"(8B) + u32 lo + u32 hi + raw[lo..hi)。
_STATE_BLOB = None          # (lo, bytes) 或 None

SCRATCH = 0x7D000000
SCRATCH_SIZE = 0x00010000
MAX_TRACE = 3000
_MD = Cs(CS_ARCH_ARM, CS_MODE_ARM)
_MD.detail = False


# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# ★★ 2026-09-30（§0.42）：**块作用域 static 的规范名**。
#   同一个对象，两套工具链给出**不同名字**（都是合法的本地符号命名）：
#     · 工厂 GCC 6.2  ：`name.<NNNN>`        例 `asso_values.9691` / `entities.6989`
#     · 我方 clang/zig：`<函数名>.<name>`     例 `aliases_hash.asso_values` / `_mxml_entity_cb.entities`
#   实测取证（`_r94_cmpdata.py` + 指针感知比对）：两边的对象**逐字节/逐项语义等价**，
#   差别只在"名字"与"它被放在哪个地址"。而 `fp_key` 的私有对象配对是**按名字**的
#   ⇒ 不归一就永远配不上 ⇒ 整类**假发散**（`aliases_hash`/`ConvertCode`/
#   `mxmlEntityGetValue`/`_mxml_entity_cb`）。
#   ★ 归一规则**故意保守**：只吃"整名形如 `X.<纯数字>`"或"整名形如 `X.Y`"两种；
#     其余一律原样返回。归一会让"唯一性"判定变严（两个不同的 `X.a`/`X.b` 归到同一
#     规范名 ⇒ 计数 2 ⇒ 不再判私有 ⇒ 退回按地址配对）—— 方向是**保守**的，不会洗白。
RE_CANON_GCC = re.compile(r'^[A-Za-z_$][\w$]*\.\d+$')
RE_CANON_CLANG = re.compile(r'^[A-Za-z_$][\w$]*\.[A-Za-z_$][\w$]*$')


def canon_obj_name(n):
    """块作用域 static 的**规范名**（两套工具链命名归一）。非上述两种形态 ⇒ 原样返回。"""
    if RE_CANON_GCC.match(n):
        return n.rsplit('.', 1)[0]
    if RE_CANON_CLANG.match(n):
        return n.split('.', 1)[1]
    return n


# --------------------------------------------------------------------------- #
# PLT 名字解析（第 152 轮重写）：**按 GOT 槽地址配名**，与 .rel.plt 的顺序无关。   #
# --------------------------------------------------------------------------- #
# ★★ 为什么换掉「.rel.plt 顺序位置配对」（第 150/151 轮遗留的 P1）
#    旧法：`.plt` 里第 k 个 `ldr pc,[..]` ↔ `.rel.plt` 第 k 个名字。
#    它是**位置**配对：任何一处多数/漏数一个 `ldr pc` ⇒ 其后**全部名字错位**
#    ⇒ `calls_ext` 整体失真（第 150 轮的回归就是这个味道：两侧 `plt_map` 塌掉、
#    `calls_ext` 全空 ⇒ **假 PASS**）。
#
# ★ 新法依据（两种链接器的 stub 形态都唯一确定一个 GOT 地址）：
#    GNU ld（12 B）：add ip,pc,#A ; add ip,ip,#B ; ldr pc,[ip,#C]!
#    lld  （16 B）：同上 + 一个 .word 填充
#    ⇒ GOT = (stub+8) + A + B + C      【ARM 的 `add ip,pc,#A` 里 pc = 本指令地址+8】
#    `.rel.plt` 的每条 R_ARM_JUMP_SLOT 其 r_offset **就是 GOT 槽地址** ⇒ 直接配名。
#    与 stub 计数、与 .rel.plt 顺序**全都无关**。
#
# ★ 验收（tools/_r152_plt_got.py，工厂 + 重建产物）：
#    新法 map 与旧法 map **逐项相同**（工厂 105 槽 / 我方 104 槽，名字与地址全一致）。
#    旧法作为**金丝雀**留在 `_build_plt_positional`，由 `--self-test` 每轮比对。

def _arm_ror(v, r, bits=32):
    r &= bits - 1
    return ((v >> r) | (v << (bits - r))) & ((1 << bits) - 1)


def _arm_imm12(word):
    """ARM 数据处理指令的「imm8 + rotate」立即数真实值。"""
    return _arm_ror(word & 0xFF, ((word >> 8) & 0xF) * 2)


# `add ip, pc, #A`：[27:20]=0x28(ADD,imm) | Rn=15 | Rd=12
_ARM_ADD_PC_IP = 0x028FC000
# `add ip, ip, #B`：[27:20]=0x28(ADD,imm) | Rn=12 | Rd=12
_ARM_ADD_IP_IP = 0x028CC000
# `ldr pc, [ip, #C](!)`：保留 [27:25]=010 / [22]B=0 / [20]L=1 / Rn=12 / Rd=15，
#   忽略 P[24] U[23] W[21]（正负偏移、是否回写都不影响 GOT 地址）。
_ARM_LDR_PC_IP_KEEP = 0x065FF000
_ARM_LDR_PC_IP_WANT = 0x041CF000


def _plt_stub_got(raw, stub_addr):
    """从 stub 的前 3 条字算出它跳的 GOT 地址；形态不认 ⇒ None。"""
    got = None
    for i in range(3):
        (word,) = struct.unpack_from('<I', raw, i * 4)
        if word == 0:
            return None
        if (word & 0x0FFFF000) == _ARM_ADD_PC_IP:
            got = stub_addr + 8 + _arm_imm12(word)
            continue
        if (word & 0x0FFFF000) == _ARM_ADD_IP_IP:
            if got is None:
                return None
            got += _arm_imm12(word)
            continue
        if (word & _ARM_LDR_PC_IP_KEEP) == _ARM_LDR_PC_IP_WANT:
            if got is None:
                return None
            off12 = word & 0xFFF
            if not (word >> 23) & 1:          # U=0 ⇒ 负偏移
                off12 = -off12
            return got + off12
        return None
    return None


def _plt_got_map(elf, raw):
    """→ (stub起始地址 → 符号名, lo, hi)。stub 起始地址 = 旧版 `ldr pc` 地址 - 8，key 口径不变。"""
    plt = elf.get_section_by_name('.plt')
    rel = elf.get_section_by_name('.rel.plt')
    if plt is None or rel is None:
        return {}, None, None
    dynsym = elf.get_section_by_name('.dynsym')
    got2name = {}
    for r in rel.iter_relocations():
        try:
            got2name[int(r['r_offset'])] = dynsym.get_symbol(r['r_info_sym']).name
        except Exception:
            pass
    a0, off, size = plt['sh_addr'], plt['sh_offset'], plt['sh_size']
    body = raw[off:off + size]
    m = {}
    for i in range(0, size - 12 + 1, 4):
        g = _plt_stub_got(body[i:i + 12], a0 + i)
        if g is None:
            continue
        nm = got2name.get(g)
        if nm:
            m[a0 + i] = nm
    if m:
        ks = sorted(m)
        return m, ks[0] - 4, ks[-1] + 4
    return m, None, None


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
        # ★ 口径（2026-09-27 对齐，P0-B）：工厂侧 `st_size==0` 的 STT_FUNC 是**无长度别名**
        #   （实测 10 个：_start/_init/_fini/frame_dummy/register_tm_clones/deregister_tm_clones/
        #    __do_global_dtors_aux/call_weak_fn/__aeabi_idiv/__aeabi_uidiv），
        #   它们由工具链 CRT/libgcc 提供，**不属于重建范围**，且 st_size==0 ⇒ 对"执行范围"
        #   没有定义 ⇒ 拿它们做逐指令对拍无判据价值。
        #   旧版不滤 ⇒ 共有函数集 746（含其中 5 个）⇒ **头条数字的分母被污染**。
        #   权威分母 = 工厂 STT_FUNC ∧ 有名 ∧ st_size>0 = **804**；可对拍交集 = **741**。
        #   排除项一律**列名**（口径差必须可见，GAP 17.10 同族）。
        self.zero_len_funcs = set()
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
                    if sz == 0:
                        # 无长度别名：不参与对拍（口径 = st_size>0），但必须**记录并公示**
                        self.zero_len_funcs.add(n)
                    elif n not in self.funcs or sz > self.funcs[n][1]:
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
        ★★ 2026-09-30 修（真缺陷，见 §0.42）：三个条件全部改为在**规范名**上判定
          （`canon_obj_name`）。理由：**块作用域 static 的命名两套工具链不同** ——
          工厂 GCC 叫 `asso_values.9691`，我方 clang 叫 `aliases_hash.asso_values`，
          两者是**同一个对象**。原实现在**原始名**上判唯一，于是我方的规范名
          `asso_values` 永远不在集合里 ⇒ `fp_key` 退回**按地址**配对 ⇒
          我方读自己的副本（4xxxxx）、工厂读映像里的副本（3axxxx）⇒ **整类假发散**。
        """
        cnt, loc = {}, set()
        for a, sz, n, ty in self.sym_list:
            if ty != 'STT_OBJECT':
                continue
            cn = canon_obj_name(n)
            cnt[cn] = cnt.get(cn, 0) + 1
            if self.sym_bind.get((a, n)) == 'STB_LOCAL':
                loc.add(cn)
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

    # --- PLT：按 **GOT 槽地址** 配名（第 152 轮）；旧的位置配对降级为自证金丝雀 ---
    # ★★★ 第 149/150 轮的血泪（勿再犯）：
    #   ① 第 149 轮我曾以"位置配对在 lld 下会错位"为由改判据，结果**引入回归**
    #      （`plt_map` 塌成 0 ⇒ `calls_ext` 两侧全空 ⇒ 假 PASS）⇒ 当场回滚；
    #   ② 第 152 轮**重新**做这件事，但先写了 `tools/_r152_plt_got.py` 只**探**不改：
    #      在工厂 + 重建产物上证明「GOT 配对 map 与位置配对 map **逐项相同**」，
    #      才把生产路径换过来，并把旧法留作金丝雀（见 `_build_plt_positional`）。
    def _build_plt(self):
        return _plt_got_map(self.elf, self.raw)

    # ★ 旧法（`.plt` 里第 k 个 `ldr pc,[..]` ↔ `.rel.plt` 第 k 个名字）。
    #   **不再是生产路径**；只给 `--self-test` 当金丝雀：一旦与新法逐项不同就 fail-loud。
    def _build_plt_positional(self):
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


# --------------------------------------------------------------------------- #
# ★★★ 2026-09-29：**可复用的执行环境**（几何一次，内容每次重写）
# --------------------------------------------------------------------------- #
_MACHINES = {}
_ZEROS = {}


def _zeros(n):
    """长度 n 的零缓冲**复用**（不要每次 `b'\x00' * n`：那会在 commit 吃紧时
    造成瞬时分配尖峰 —— 2026-09-29 实测 `MemoryError`）。"""
    z = _ZEROS.get(n)
    if z is None:
        z = b'\x00' * n
        _ZEROS[n] = z
    return z


def _machine_for(b, mode):
    """返回 (mu, model, gaps)。同一二进制只建**一次**；几何（段/栈/PRNG区/模型区）只 map 一次。

    ★ 为什么必须复用（可选）：见 run_func 里 2026-09-29 那段注释
      （4700 个实例 ⇒ 本机 commit 吃紧时 `MemoryError`；复用后 2m24s → 33s）。
    ★★ **默认关闭**（`CGM_MACHINE_REUSE=1` 才开），因为它是**行为敏感**改动：
      复用会把"新实例本来是 0"的栈/空洞带进来 ⇒ 实测 737/40 变成 731/46
      （已补 ① VFP/NEON 寄存器清零 ② 栈与映射空洞显式补零 两处，但**尚未在
       有内存的机器上完成回归对账**）。回归判据（必须逐字相同）：
         python tools/diff_exec.py --batch --steps 3000 --ours build/rkgame.rebuilt.elf
         ⇒ 期望 共有 782 ｜ PASS 737 ｜ DIVERGE 40 ｜ TRUNC 5 ｜ REFDEAD 0 ｜ SKIP 0
    ★ 关闭时**每调用新建**（与改造前语义完全一致：新实例的映射区天然为零）——
      下面对寄存器/栈/空洞的复位与补零在"新实例"上都是**幂等的无操作**，所以两条路径
      共用同一段代码体，不存在"两条实现漂移"的风险。
    ★ 缓存键带 `id(b)`，并把 `b` **强引用**存在缓存里 ⇒ 防止 id 复用造成串味。
    """
    reuse = os.environ.get('CGM_MACHINE_REUSE') == '1'
    key = (id(b), mode)
    if reuse:
        hit = _MACHINES.get(key)
        if hit is not None and hit[0] is b:
            return hit[1], hit[2], hit[3]
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
    # ★ 只算"映射了但段内容写不到"的**空洞**（复用实例时唯一需要显式补零的地方）。
    #   段本身（含 bss 的 memsz 段）per-call 都会重写 ⇒ 不必整段补零。
    gaps, cur = [], None
    for lo, hi in merged:
        for va, fsz, msz, fl, off in sorted(b.segs):
            s, e = va, va + msz
            if e <= lo or s >= hi:
                continue
            if cur is None:
                cur = lo
            if s > cur:
                gaps.append((cur, min(s, hi)))
            cur = max(cur, e)
        if cur is None:
            cur = lo
        if cur < hi:
            gaps.append((cur, hi))
        cur = None
    mu.mem_map(STACK_BASE, STACK_SIZE, 7)
    mu.mem_map(SCRATCH, SCRATCH_SIZE, 7)
    mu.mem_map(SENTINEL & ~0xFFF, 0x1000, 7)
    # ★★★ 2026-10-01（第 102 轮）：**观测力扩展**（opt-in，`CGM_MAP_WILD=1`）。
    #   病灶（实测）：这批 UI/状态函数会踩"野指针落点"而 READ/WRITE_UNMAPPED 早死，
    #   于是两侧"死得深浅不同"⇒ 观测窗口不可比 ⇒ 分不清"真差异"与"调度顺序"。
    #   实测落点：`0x0 / 0x40 / 0x78`（NULL 页区）、`0x7e040000`（= STACK_BASE+STACK_SIZE，
    #   **写越过栈顶**）。把这两处也映射成 RW，两侧**同处理** ⇒ 差异仍是代码造成的。
    #   ★ 默认**关**（`CGM_MAP_WILD` 未设 ⇒ 与从前逐位一致）；开它只是"看得更远"，
    #     不改判据、不改默认口径、不进判据指纹。
    #   ★ 只扩两小块（64KB + 256KB）：`_gaps` 的补零成本才可忽略（大块会让每次运行退化成 GB 级写入）。
    # ★★★ 2026-10-01（第 108 轮）：**NULL 链捕获**（opt-in，`CGM_SEED_NULL=1`）。
    #   实测：17 个 DIVERGE 里 12 个是"双方都崩、深度不同"，而未映射访问 **53/64 落在 0x0**。
    #   这些是 NULL 解引用，且来源全局（`m_ui+…` 等运行时状态）"无人写" ⇒ 无法用小规模预热补齐。
    #   做法：把 NULL 页与一个安全区**填成互指的指针图** ⇒ 任意深度解引用都不崩。
    #   ★ 两侧内存内容**完全相同** ⇒ 仍可比；差异只会往更深处显现，不会被抹掉。
    #   ★ 只改执行后端（与 CGM_MAP_WILD 同类）⇒ **不进判据口径指纹**；默认关。
    if os.environ.get('CGM_SEED_NULL') == '1':
        _SAFE = 0x60000000
        _SAFE_SZ = 0x00100000
        # ★★★ 实测（第 108 轮）：**Unicorn 拒绝 `mem_map(0x0, …)`**（`UC_ERR_MAP`，Invalid
        #   memory mapping）⇒ 想"先映射 NULL 页再填值"这条路走不通。
        #   ★ 顺带查出既有缺陷：`CGM_MAP_WILD` 里的"(0x0, 0x10000, 'NULL 页区')"**一直失败**
        #     （被它自己的 `except Exception` 吞掉）⇒ 只有"栈上方"真正生效 —— 这正是上一轮
        #     `CGM_MAP_WILD` 只救活 1 个（栈溢出的 `mui_video_setting`）的原因。
        #   ⇒ 改用**动态映射钩子**：第一次访问未映射的低地址/野地址时，**当场映射该页并填充**，
        #     再让 Unicorn 跳过本次访问（返回 True）。两侧同一套规则 ⇒ 仍可比。
        for _lo, _sz, _why in ((_SAFE, _SAFE_SZ, '安全区'),):
            try:
                mu.mem_map(_lo, _sz, 7)
            except Exception as _e:                                # noqa: BLE001
                sys.stderr.write('  [seed-null] 跳过 0x%x(%s)：%s\n' % (_lo, _why, _e))
        _sp = bytearray()
        for off in range(0, _SAFE_SZ, 4):
            _sp += (_SAFE + (off & 0xFFFF0)).to_bytes(4, 'little')
        try:
            mu.mem_write(_SAFE, bytes(_sp))
        except Exception as _e:                                    # noqa: BLE001
            sys.stderr.write('  [seed-null] 写安全区失败：%s\n' % _e)
        _seeded_pages = set()

        def _seed_hook(_mu, _access, _addr, _size, _val, _user):
            # 只接管"低地址野指针"（NULL / -1 附近），其余未映射访问照旧崩 ——
            # 否则会把**所有**崩溃都吞掉，观测就失去意义。
            if _addr < 0x10000 or _addr >= 0xFFFF0000:
                _pg = _addr & ~0xFFF
                if _pg not in _seeded_pages:
                    try:
                        _mu.mem_map(_pg, 0x1000, 7)
                        _buf = bytearray()
                        for _o in range(0, 0x1000, 4):
                            _buf += (_SAFE + (_o & 0xFF0)).to_bytes(4, 'little')
                        _mu.mem_write(_pg, bytes(_buf))
                        _seeded_pages.add(_pg)
                    except Exception:                              # noqa: BLE001
                        return False
                return True                                        # 跳过本次访问
            return False
        # ★ `ac` 是 `unicorn.arm_const`（只有寄存器常量），hook 常量在 `unicorn` 顶层
        #   ⇒ 必须用已 import 的名字，不能写 `ac.UC_HOOK_*`（AttributeError）。
        for _hk in (UC_HOOK_MEM_READ_UNMAPPED, UC_HOOK_MEM_WRITE_UNMAPPED):
            mu.hook_add(_hk, _seed_hook)

    if os.environ.get('CGM_MAP_WILD') == '1':
        # ★★ 2026-10-01（第 108 轮）**修正**：原表里有 `(0x0, 0x10000, 'NULL 页区')` ——
        #   实测 **Unicorn 拒绝 `mem_map(0x0, …)`**（`UC_ERR_MAP`）⇒ 该项**从来不生效**
        #   （被下面的 `except Exception` 吞掉）⇒ 这正是"开了 MAP_WILD 只救活 1 个"的原因。
        #   NULL 页改由 `CGM_SEED_NULL` 的**动态映射钩子**接管（见上），此处只留"栈上方"。
        for _lo, _sz, _why in ((STACK_BASE + STACK_SIZE, 0x40000, '栈上方'),):
            try:
                mu.mem_map(_lo, _sz, 7)
            except Exception as _e:                                # noqa: BLE001
                sys.stderr.write('  [map-wild] 跳过 0x%x(%s)：%s\n' % (_lo, _why, _e))
    model = libc_model.Model()
    model.map_regions(mu)
    if reuse:
        _MACHINES[key] = (b, mu, model, gaps)
    return mu, model, gaps



class F32(float):
    """typed float 实参：走 VFP 寄存器 s0..s15（hard-float AAPCS）。

    ★ 为什么必须有（R289）：本目标 ABI 是 armv7 **hard-float**；`stbtt_MakeGlyphBitmapSubpixel`
      的 4 个 float 参数按 AAPCS-VFP 进 s0–s3，而旧实现把 `args[4:]` 一律按整数写到 [sp]
      ⇒ float 被塞进栈上整数槽，被调函数读到的 s0 是复用实例残留（失败形态是"结果离谱"而非报错）。
    """


def _arm_write_args(mu, ac, args, sp0):
    """按 AAPCS-VFP 写实参：整数/指针→r0..r3 再 [sp..]；F32→s0..s15。"""
    import struct as _st
    core = [a for a in list(args) if not isinstance(a, F32)]
    vfp = [a for a in list(args) if isinstance(a, F32)]
    for i, v in enumerate(core[:4]):
        mu.reg_write(ac.UC_ARM_REG_R0 + i, int(v) & 0xFFFFFFFF)
    for i, v in enumerate(core[4:]):
        mu.mem_write(sp0 + i * 4, (int(v) & 0xFFFFFFFF).to_bytes(4, 'little'))
    for i, v in enumerate(vfp[:16]):
        reg = getattr(ac, 'UC_ARM_REG_S%d' % i, None)
        if reg is None:
            raise ValueError('本 Unicorn 无 UC_ARM_REG_S%d，无法传递 float 实参' % i)
        mu.reg_write(reg, _st.unpack('<I', _st.pack('<f', float(v)))[0])
    return len(core), len(vfp)


def run_func(b, fname, args, steps=20000, stub_ret=None, spans=None, syms_for_final=None,
             mode=None, _retry=True, stop_at=None, seed=None, out_windows=None, pre=None):
    """执行 fname(args)。mode=None 时自动判 ARM/Thumb（先 ARM，遇 INSN_INVALID 再试 Thumb）。

    ★ 2026-10-01 新增 `stop_at`（**共同视野前缀**用，见 `compare()` 的两侧早死判据）：
      把模拟**硬截断**在 N 条指令处。为什么必须能截断：当两侧都因内存未映射早死、但**深度不同**时，
      较深一侧多出来的观测（`calls_ext`/访存/终值）发生在较浅一侧**根本不存在**的视野里
      ⇒ 直接比全量等于拿"多跑的一段"当差异。正确做法是把两侧都截到 `min(insns)` 再比。
      ★ 截断运行里 `stopped` 会是 `'return'`（`emu_start` 因 count 用尽正常返回，**不抛异常**），
      所以**终值/停止原因不可信** —— 调用方必须显式声明"不许用终值判据"（`allow_terminal=False`）。
      本参数**只提供能力，不改变任何既有行为**（默认 None ⇒ 与从前逐位一致）。

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
    # ★★★ 2026-09-29 结构性修复：**复用执行环境**（几何建一次，内容每次重写）。
    #   病灶（实测）：746 函数 × 2 二进制 × 3 组语料 ≈ **4700 个 Unicorn 实例**，
    #   每个 mem_map 数 MB；Unicorn 的 **C 侧内存归还给 OS 不及时** ⇒ 本机 commit 吃紧时
    #   直接 `MemoryError` / `UC_ERR_NOMEM`（本轮实测：`--limit 5` 就炸，单函数却能过）。
    #   而**同一个二进制**的段几何 + 模型映射是**常量**，每次变的只有**内容** ——
    #   所以正确做法是把 `mem_map` 提出来只做一次，per-call 只重写内容 + 复位寄存器/模型。
    #   ⇒ commit 峰值 ~4700×11 MB → **2×11 MB**；顺带省掉每函数重复的段 mem_write。
    mu, _model, _gaps = _machine_for(b, mode)
    # ★ R291 诊断探针：CGM_DBG_PC=1 时统计热点 PC（只在"被预算砍断"时有意义）。
    #   为什么要它：TRUNC 只说"没跑完"，说不出"卡在哪" —— 没有 PC 现场就只剩猜。
    _pc_hist = {} if os.environ.get('CGM_DBG_PC') == '1' else None
    # ★ 寄存器必须显式复位：复用实例会把上一个函数的 r0/sp/pc 带进来（会伪造 PASS/发散）
    for _r in (ac.UC_ARM_REG_R0, ac.UC_ARM_REG_R1, ac.UC_ARM_REG_R2, ac.UC_ARM_REG_R3,
               ac.UC_ARM_REG_R4, ac.UC_ARM_REG_R5, ac.UC_ARM_REG_R6, ac.UC_ARM_REG_R7,
               ac.UC_ARM_REG_R8, ac.UC_ARM_REG_R9, ac.UC_ARM_REG_R10, ac.UC_ARM_REG_R11,
               ac.UC_ARM_REG_R12, ac.UC_ARM_REG_LR, ac.UC_ARM_REG_CPSR):
        try:
            mu.reg_write(_r, 0)
        except UcError:
            pass
    try:
        mu.reg_write(ac.UC_ARM_REG_SP, STACK_BASE + STACK_SIZE - 0x100)
    except UcError:
        pass
    # ★★ 复用实例必须把 **VFP/NEON 寄存器**也清零（2026-09-29 回归实测抓到的泄漏）：
    #   第一次复用版本只清了 r0~r12/lr/cpsr/sp ⇒ 上一函数残留在 d0~d31/fpscr 的垃圾
    #   会被下一函数的"先读后写"路径吃到 ⇒ 产物侧行为改变 ⇒ 行为尺 737/40 变成 **731/46**。
    #   这正是复用方案的风险点，靠"批量汇总必须逐字相同"这条回归判据当场抓到。
    for _i in range(32):
        _r = getattr(ac, 'UC_ARM_REG_D%d' % _i, None)
        if _r is None:
            continue
        try:
            mu.reg_write(_r, 0)
        except UcError:
            pass
    try:
        mu.reg_write(ac.UC_ARM_REG_FPSCR, 0)
    except (UcError, AttributeError):
        pass
    _model.reset(mu)                 # 堆重新涂 0xa5（**不清零**，见 map_regions 注释）+ 状态清零
    # ★★★ 复用实例的**正确性前提**（2026-09-29 回归实测抓到的第二个泄漏）：
    #   新建实例时 `mem_map` 会把**整段映射区**（含段与段之间的空洞）补零；复用不会
    #   ⇒ 上一函数留在**栈**与**映射空洞**里的残留会被这一函数的"读未初始化"路径吃到
    #   ⇒ 回归实测：737/40 变成 **731/46**，受影响的是 `stbtt_*`（大量局部缓冲）一族。
    #   所以：把"新实例本来会是 0 的地方"**显式清零**，再写段内容。顺序不可颠倒。
    for lo, hi in _gaps:
        if hi > lo:
            mu.mem_write(lo, _zeros(hi - lo))
    mu.mem_write(STACK_BASE, _zeros(STACK_SIZE))
    # ★ 段内容每次重写：**内容才是变量**，几何不是
    for va, fsz, msz, fl, off in b.segs:
        if fsz:
            mu.mem_write(va, b.raw[off:off + fsz])
        if msz > fsz:
            mu.mem_write(va + fsz, b'\x00' * (msz - fsz))
    mu.mem_write(SCRATCH, b'\x00' * SCRATCH_SIZE)
    mu.mem_write(SCRATCH + 0x100, b'A\x00')
    mu.mem_write(SCRATCH + 0x200, b'core\x00')
    # ★★★ 2026-10-07（第 160 轮）：**函数特设输入的内存种子**。
    #   必须在段内容 / SCRATCH 标准重置**之后**写，否则会被上面的重置覆盖。
    #   两侧用同一份 bytes ⇒ 种子本身不构成差异源（判据仍是两侧被测代码）。
    # ★ R294：真实状态快照（在段内容与 SCRATCH 重置之后写，避免被覆盖；两侧同一份字节）。
    if _STATE_BLOB is not None:
        _lo, _bytes = _STATE_BLOB
        mu.mem_write(_lo, _bytes)
    for _va, _bs in (seed or ()):
        mu.mem_write(_va, _bs)
    # ★★ 2026-10-03（第121 轮，判据见 PSEUDOSYM-CORPUS.md）：`core` 组专用入参。
    #   'NES' 是default_core_list（@0x3b0254, stride 0x44）的**第10 项**
    #   ⇒ GetCoreIndex 应做**恰好 11 次 strcmp** 后命中并返回 10。
    #   为什么需要它：`misc` 组 r0=0x1 指向未映射，两侧在进 GetCoreIndex **之前**
    #   就分岔 ⇒ strcmp 永远不可判（纪律：不可判 ≠ 未收敛）。
    #   为什么选 NES（而不是 BKP/CONF）：BKP 只需 1 次信号太弱；CONF 要 33 次，
    #   贴近 100 上限、易引入别的变量；NES 居中且已大写 ⇒ 不引入大小写维度。
    mu.mem_write(SCRATCH + 0x300, b'NES\x00')

    sp = spans
    d = b.dregion
    ctx = {'insns': 0, 'calls': [], 'w': [], 'r': [],
           'unmodelled': [], 'modelled': [],
           # ★ 未映射访问现场（第 98 轮）：`(access, address, size)`；None = 没发生
           'fault': None}
    # ★★ 外部调用**语义模型**（GAP 17.16）：原先所有外部调用一律 `r0 = 0`，
    #   对**指针返回型**函数等于"返回 NULL" ⇒ 调用方一解引用就 UC_ERR_READ_UNMAPPED
    #   ⇒ 4 个函数（strupr/get_from_line/myStrrstr/GetFilenameExt）被**仪器**判成发散。
    #   现在两侧共用同一份模型与同一组地址 ⇒ 差异只可能来自被测代码。
    #   ★ 2026-09-29：映射已由 `_machine_for` 做过**一次**（复用实例），这里**不再** map
    #     —— 重复 mem_map 同址会 `UC_ERR_MAP`（本轮实测踩到）。
    # ★ A/B 开关：`CGM_NO_LIBC_MODEL=1` 时退回"所有外部调用返回 0"的旧行为。
    #   存在意义是**可证伪**：任何"模型只是让尺子变准、没有掩盖差异"的论断，
    #   都必须能靠这个开关做**单变量**对照（同一工具、同一产物、只差这一个开关）。
    _use_model = os.environ.get('CGM_NO_LIBC_MODEL') != '1'

    _dbg = os.environ.get('CGM_DBG_REGS') == '1'
    # ★ 预算：`stop_at` 是"共同视野前缀"的硬截断（见本函数头注释），只可能**收窄**预算
    budget = steps if stop_at is None else max(1, min(int(stop_at), steps))

    def code_hook(m, address, size_, user):
        ctx['insns'] += 1
        if _pc_hist is not None:
            _pc_hist[address] = _pc_hist.get(address, 0) + 1
        # ★ 逐指令探针（CGM_DBG_REGS=1）：打印**前 6 条**指令 + CPSR 的 T 位。
        #   为什么需要它（2026-09-27）：ARM/Thumb **混编**是工厂的真实形态
        #   （804 个函数里 308 个是 Thumb）。任何"两侧行为不同"的结论，
        #   都必须先排除"执行模式/入口约定不同"这一仪器层面的可能 ——
        #   Thumb-2 被当 ARM 解码常常**不报** INSN_INVALID，而是解成一串看似合法的指令。
        if _dbg and ctx['insns'] <= 6:
            try:
                _t = (m.reg_read(ac.UC_ARM_REG_CPSR) >> 5) & 1
            except Exception:
                _t = -1
            sys.stderr.write('     [ins %d] pc=0x%x T=%s r0=0x%x r1=0x%x r2=0x%x r3=0x%x\n'
                             % (ctx['insns'], address, _t,
                                m.reg_read(ac.UC_ARM_REG_R0), m.reg_read(ac.UC_ARM_REG_R1),
                                m.reg_read(ac.UC_ARM_REG_R2), m.reg_read(ac.UC_ARM_REG_R3)))
        nm = b.plt_name(address)
        if nm is not None:
            if len(ctx['calls']) < MAX_TRACE:
                ctx['calls'].append(nm)
            if stub_ret and nm in stub_ret:
                m.reg_write(ac.UC_ARM_REG_R0, stub_ret[nm] & 0xFFFFFFFF)
            elif _use_model and _model.call(m, ac, nm):
                if len(ctx['modelled']) < MAX_TRACE:
                    ctx['modelled'].append(nm)
            else:
                # ★ 兜底：**必须登记**未建模；绝不静默当成"两侧一致"
                #   （纪律 3："没跑"与"跑了但过了"必须可区分）。
                if len(ctx['unmodelled']) < MAX_TRACE:
                    ctx['unmodelled'].append(nm)
                # ★★★ 2026-10-05（第 142 轮）**根修**：兜底不得硬写 0。
                #   簇 A 实测铁证：`FilePreEmu` 里 `strcpy(&FilenameExt,p); strupr(&FilenameExt);`
                #   工厂 gcc 6.2 编出 `bl strcpy@plt` + **`mov r0,r4`（reload）**，
                #   我方 clang -Os 消掉 reload（判定返回值未使用 ⇒ 冗余）——
                #   **两侧都是合法代码，真实硬件上行为一致**。但在 diff_exec 里
                #   src 不可读 ⇒ 模型抛异常 ⇒ 旧兜底 `r0=0` ⇒
                #   工厂 reload 拿到 `&FilenameExt`、我方 `strupr(NULL)` ⇒ 假 DIVERGE。
                #   根因：兜底**违反 libc 的 C 契约**（`strcpy` 恒返回 dst，与数据无关）。
                #   判定表与实现都在 `libc_model.fallback_r0()`（唯一真源，纪律 69），
                #   本处**只调用、不重述**。
                _a = [m.reg_read(ac.UC_ARM_REG_R0 + i) for i in range(4)]
                m.reg_write(ac.UC_ARM_REG_R0,
                            libc_model.fallback_r0(nm, _a) & 0xFFFFFFFF)
            m.reg_write(ac.UC_ARM_REG_PC, m.reg_read(ac.UC_ARM_REG_LR))
            return
        if ctx['insns'] > budget:
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

    def fhook(m, access, address, size_, value, user):
        # ★ 只记**第一个**现场（后续钩子不会再被调用，因为我们要让模拟停下）
        if ctx['fault'] is None:
            ctx['fault'] = (access, address, size_)
        return False          # False ⇒ 保持原行为：停下并抛 UcError

    h1 = mu.hook_add(UC_HOOK_CODE, code_hook)
    h2 = mu.hook_add(UC_HOOK_MEM_WRITE, mem_hook)
    h3 = mu.hook_add(UC_HOOK_MEM_READ, mem_hook)
    # ★ 不许静默退化：装不上就直接抛（第 98 轮实测：上一版把 AttributeError
    #   吞掉 ⇒ 探针恒为 None 却毫无提示 = **假绿**）。
    mu.hook_add(UC_HOOK_MEM_READ_UNMAPPED, fhook)
    mu.hook_add(UC_HOOK_MEM_WRITE_UNMAPPED, fhook)
    mu.hook_add(UC_HOOK_MEM_FETCH_UNMAPPED, fhook)

    _sp0 = STACK_BASE + STACK_SIZE - 0x100
    # ★★★ R289：**前置钩子**（同一 Unicorn 实例内先执行 pre 里的函数，再执行目标）。
    #   用途：有状态函数——`stbtt_MakeGlyphBitmapSubpixel` 必须先 `stbtt_InitFont` 填好
    #   `font` 结构，否则读到的全是 0（表现为"没渲染"而不是"报错"）。
    #   ★ 两侧跑**同一份**前缀 ⇒ 对称；前缀写入的内存保留给目标。
    #   ★ fail-loud：前缀函数在任一侧不存在就抛，不得静默跳过。
    _pre_insns = 0
    if pre:
        for _pf, _pargs in (pre or ()):
            if _pf not in b.funcs:
                raise ValueError('FN_CORPUS 前缀函数 %r 在 %r 中不存在' % (_pf, getattr(b, 'path', '?')))
            _paddr, _ = b.funcs[_pf]
            for _r in (ac.UC_ARM_REG_R0, ac.UC_ARM_REG_R1, ac.UC_ARM_REG_R2, ac.UC_ARM_REG_R3,
                       ac.UC_ARM_REG_R4, ac.UC_ARM_REG_R5, ac.UC_ARM_REG_R6, ac.UC_ARM_REG_R7,
                       ac.UC_ARM_REG_R8, ac.UC_ARM_REG_R9, ac.UC_ARM_REG_R10, ac.UC_ARM_REG_R11,
                       ac.UC_ARM_REG_R12, ac.UC_ARM_REG_LR, ac.UC_ARM_REG_CPSR):
                try:
                    mu.reg_write(_r, 0)
                except UcError:
                    pass
            mu.reg_write(ac.UC_ARM_REG_SP, _sp0)
            mu.reg_write(ac.UC_ARM_REG_LR, SENTINEL)
            _arm_write_args(mu, ac, _pargs, _sp0)
            _ins0 = ctx['insns']
            try:
                mu.emu_start(_paddr, SENTINEL, count=steps)
            except UcError as _pe:
                raise ValueError('前缀 %r 执行失败: %s' % (_pf, _pe))
            _used = ctx['insns'] - _ins0
            _pre_insns += _used
            # ★★★ R292：**前缀未终止 ⇒ fail-loud**。
            #   真实事故（R291）：corpus 漏了字体种子 ⇒ 前缀 `stbtt_InitFont` 把 libiconv 表
            #   当 TTF 解析 ⇒ `stbtt__find_table` 死循环 ⇒ 目标函数被饿死，报告成"目标 TRUNC"。
            #   ⇒ 症状与"产物有缺陷"同形，极易误判。故：前缀吃满预算即报错并指名。
            if _used >= steps:
                raise ValueError(
                    '前缀 %r 在预算 %d 内未终止（很可能缺它需要的种子；'
                    '参考 R291：stbtt_InitFont 需要字体数据种子）' % (_pf, steps))
        for _r in (ac.UC_ARM_REG_R0, ac.UC_ARM_REG_R1, ac.UC_ARM_REG_R2, ac.UC_ARM_REG_R3,
                   ac.UC_ARM_REG_R4, ac.UC_ARM_REG_R5, ac.UC_ARM_REG_R6, ac.UC_ARM_REG_R7,
                   ac.UC_ARM_REG_R8, ac.UC_ARM_REG_R9, ac.UC_ARM_REG_R10, ac.UC_ARM_REG_R11,
                   ac.UC_ARM_REG_R12, ac.UC_ARM_REG_LR, ac.UC_ARM_REG_CPSR):
            try:
                mu.reg_write(_r, 0)
            except UcError:
                pass
    mu.reg_write(ac.UC_ARM_REG_SP, _sp0)
    mu.reg_write(ac.UC_ARM_REG_LR, SENTINEL)
    _arm_write_args(mu, ac, args, _sp0)
    # ★★★ 2026-10-07（第 160 轮）：**AAPCS 栈参数**（第 5 个及以后的参数）。
    #   ARM 过程调用标准：前 4 个参数走 r0-r3，第 5 个起**由调用方压栈**，
    #   被调函数从 [sp], [sp+4], … 读取。
    #   病灶（第 160 轮查 FDCT32 时实测发现）：本函数曾经**只写 r0-r3**，
    #   `args[4:]` 被静默丢弃 ⇒ 被调函数从栈读到的是复用实例的**残留**或零
    #   ⇒ 语料组里写了第 5 个参数等于没写，`gb`（guard bits）恒定走旧分支。
    #   ★ 栈内容已在上方被 `_zeros` 清过（第 108 轮的残留泄漏修复），此处只覆写。

    if os.environ.get('CGM_DBG_REGS') == '1':
        sys.stderr.write('   [entry] %-30s mode=%s addr=0x%x (lowbit=%d) r0=0x%x r1=0x%x r2=0x%x r3=0x%x\n'
                         % (fname, 'THUMB' if mode == UC_MODE_THUMB else 'ARM', addr,
                            addr & 1, *[mu.reg_read(ac.UC_ARM_REG_R0 + i) for i in range(4)]))
    stopped = 'return'
    try:
        mu.emu_start(addr, SENTINEL, count=budget)
    except UcError as e:
        stopped = 'uc-error: %s @0x%x' % (e, mu.reg_read(ac.UC_ARM_REG_PC))
    if _pc_hist and ctx['insns'] >= budget:
        _top = sorted(_pc_hist.items(), key=lambda kv: -kv[1])[:6]
        sys.stderr.write('   [dbg-pc] %-32s 热点 PC: %s\n'
                         % (fname, ', '.join('0x%x×%d' % (a, c) for a, c in _top)))
    r0 = mu.reg_read(ac.UC_ARM_REG_R0)
    # ★ 截断运行若把预算用尽，`stopped` 仍是 'return'（无异常）⇒ 必须显式标记，
    #   否则调用方会把"被砍断"误读成"跑完了"（那是把仪器限制当成程序行为）。
    prefix_hit = (stop_at is not None and ctx['insns'] >= budget)
    # ★ Thumb 重试：ARM 模式在头几条指令就 INSN_INVALID ⇒ 改用 Thumb
    if (_retry and mode == UC_MODE_ARM and stopped != 'return'
            and 'INSN_INVALID' in stopped and ctx['insns'] <= 8):
        r = run_func(b, fname, args, steps, stub_ret, spans, syms_for_final,
                     mode=UC_MODE_THUMB, _retry=False, stop_at=stop_at)
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
    # ★★★ 2026-10-07（第 160 轮）：**输出窗字节**（判据③的直接实现，见 FN_CORPUS）。
    #   必须在摘钩子 / 释放机器**之前**读——此时 emu_start 已结束，最终内存在机器里。
    #   `out_windows` = [(名字, vaddr, size), ...]；读不到 ⇒ None（调用方按 fail-loud 处理）。
    #   ★ 与 `final` 的区别：`final` 只吃 dregion 内 size<=64 的具名符号（覆盖不到
    #     `items` 这种 0x3e80 的大对象）；输出窗**显式声明**要验哪一段，且不限大小。
    out_bytes = {}
    if out_windows:
        for _nm, _va, _sz in out_windows:
            try:
                out_bytes[_nm] = bytes(mu.mem_read(_va, _sz))
            except UcError:
                out_bytes[_nm] = None
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
            # ★ 被 `stop_at` 砍断（不是被 `steps` 预算砍断）—— 见本函数头注释
            'prefix_hit': prefix_hit,
            'calls_ext': ctx['calls'], 'writes': ctx['w'], 'reads': ctx['r'], 'final': final,
            # ★ 未建模/已建模的外部调用（报告里单列；未建模**不得**被静默当成一致）
            'unmodelled': sorted(set(ctx['unmodelled'])),
            'modelled': sorted(set(ctx['modelled'])),
            # ★ 未映射访问现场：(access, address, size) 或 None（第 98 轮）
            'fault': ctx['fault'],
            # ★ 输出窗字节（第 160 轮）：{名字: bytes} 或 {名字: None}（读不到）
            'out_bytes': out_bytes}


CORPUS = [
    ('zero', [0, 0, 0, 0]),
    ('strs', [SCRATCH + 0x100, SCRATCH + 0x200, SCRATCH, 0]),
    # ★ 2026-10-03（第 121 轮）：`core` 组= 让 GetCoreIndex 的 strcmp 循环**可判**。
    #   r0 = &"NES"（default_core_list 第 10 项）⇒ 期望 11 次 strcmp、返回 10。
    #   判据与设计依据见 PSEUDOSYM-CORPUS.md（**先写死判据、后改代码**）。
    ('core', [SCRATCH + 0x300, SCRATCH + 0x300, SCRATCH, 0]),
    ('misc', [1, 2, 4, 0x1000]),
]


def _unpack_cps(items):
    """语料条目归一为 `(组名, args, seed, out_windows)`。

    · 2 元组 ⇒ seed=None, out_windows=None（全局 CORPUS 的老格式，向后兼容）
    · 3 元组 ⇒ out_windows=None
    · 4 元组 ⇒ (组名, args, seed, out_windows)；out_windows = [(名字, vaddr, size), ...]
    """
    for it in items:
        if len(it) == 2:
            yield it[0], it[1], None, None, None
        elif len(it) == 3:
            yield it[0], it[1], it[2], None, None
        elif len(it) == 4:
            yield it[0], it[1], it[2], it[3], None
        elif len(it) == 5:
            # R289：(组名, args, seed, out_windows, pre)
            yield it[0], it[1], it[2], it[3], it[4]
        else:
            raise ValueError('语料条目必须是 2/3/4 元组'
                             '（名字, args[, seed[, out_windows]]）：%r' % (it,))


# ★★★ 2026-10-07（第 160 轮）：**函数特设合法输入组**（不污染全局 CORPUS）。
#
#   病灶（第 156.1 轮实证）：`xmp3_FDCT32` 这类**纯计算**函数在全局 CORPUS 下
#   必然撞未映射早死——CORPUS 的 r0/r1 指向 SCRATCH 假数据、r2/r3 是被当索引的
#   大整数 ⇒ FDCT32 用 `offset*4 + 0x400*4` 算出的写址飞出 SCRATCH ⇒ 两侧
#   双双 WRITE_UNMAPPED，判据③（两侧输出比对）**根本没有观测窗**。
#
#   依据（先查官方上游，不猜）：`src/upstream/mp3/real/dct32.c` 的权威签名是
#       void FDCT32(int *buf, int *dest, int offset, int oddBlock, int gb);
#     · buf    ：32 个定点样本，**原地变换**（写回 buf[0..0x1f]）
#     · dest   ：输出缓冲区，写址 = dest + 64*16 + ((offset-oddBlock)&7)
#                + VBUF_LENGTH*(oddBlock?0:1) … 最远 ≈ dest + 0x1510
#     · offset ：真实调用方 `xmp3_Subband` 传的是 0..7 的环索引
#     · oddBlock：0 或 1
#     · gb     ：guard bits；`gb < 6` 时先把 buf 整体右移 (6-gb)
#   ⇒ 给它配**合法**入参：buf/dest 落在真实具名数据对象里，offset/oddBlock/gb
#      取真实取值范围内的值。
#
#   ★★ 为什么 buf/dest **必须落在具名数据对象**（而不是 SCRATCH）：
#     访存指纹只在 `spans`（两侧 STT_OBJECT 区间并集）内被记录，终值 `final`
#     只覆盖 dregion 内的具名符号。若用 SCRATCH，两侧都"看不见输出"⇒ **假 PASS**
#     （这正是本仪器从头到尾在防的那一类）。落在具名对象里 ⇒ 写入进指纹、
#     两侧同址可比 ⇒ 差异只会来自被测代码。
#   ★★ 种子内容两侧**逐位相同**（同一份 bytes）⇒ 不构成差异源。
#   ★★ 地址一律**从符号表查**（第 152 轮纪律：不手写常量）。已核对两侧同址：
#        corecfg  @0x3cfac8 size 0x3e80（buf，原地写 128B 足够）
#        items    @0x3d3948 size 0x3e80（dest，最远写 +0x1510 足够，且与 corecfg 相邻不重叠）
#        dcttab   @0x2e428c size 0xc0（只读查表，两侧同址 —— 第 134 轮已修绑定）
def _fdct32_buf_seed():
    """32 个定点样本（|x| < 2^18 ⇒ ≥6 guard bits，依据 dct32.c 头注释的溢出前提）。

    确定性 LCG：同一份代码在任何机器上给出同一序列（不依赖 RNG 状态/时序）。
    """
    v = 0x12345678
    vals = []
    for _ in range(32):
        v = (v * 1103515245 + 12345) & 0x7fffffff
        vals.append(((v >> 11) - 0x40000) & 0xffffffff)     # [-2^18, 2^18) → uint32
    return b''.join(x.to_bytes(4, 'little') for x in vals)


FDCT32_BUF_SEED = _fdct32_buf_seed()

# ★★★ 2026-10-07（第 160 轮取证后追加）：**输出窗**（判据③的直接实现）。
#
#   取证结论（云工作区 `_r160b_probe.py`，两侧 unicorn 跑同一组合法输入）：
#     · buf  [0x3cfac8, +0x80)  最终字节**逐位相同**（原地变换的完整输出）
#     · dest [0x3d3948, +0x1000) 最终字节**逐位相同**（覆盖最远写址 dest+0xC27）
#   而 `data-reads` 分歧的**全部**来源已被逐项钉死（见下方「新发现与决策」）：
#     ① dcttab+0..+116（stage-1 的 30 个系数）：工厂 GCC 把 `static const`
#        数组**常量折叠成立即数**（Ghidra 里是 `* 0x4013c251` 这类立即乘），
#        我方因第 134 轮把 `dcttab` 改成 `extern`（绑定镜像地址）⇒ clang
#        **无法**折叠外部数组 ⇒ 老老实实查表。**值相同（镜像逐字节一致）**。
#     ② buf[0..7] 多读一次：clang -Os 的寄存器压力 ⇒ reload；工厂留在寄存器里。
#     ③ 8B 读 = clang 把相邻两个 32 位载入合并成 `ldm rN!, {rA,rB}`（工厂 2×LDR）。
#   ⇒ 访问模式是编译策略，**不是语义**；函数的真实输出（buf/dest 字节）才是。
#
#   ★★ 判据设计（纪律：先写死判据、后改代码、不得直接放宽）：
#     声明输出窗的组，**直接比窗口字节**。窗口逐位相同 ⇒ 本组的 `data-reads`
#     差异被**证明**不影响输出（对该输入）⇒ 降级为 note 留痕。
#     这**不是**放宽 `read_width_only`——它换成了**更强**的判据（直接验输出）。
#   ★★ 两道反向约束（防这次降级被滥用）：
#     · 窗口读不到 / 内容不同 ⇒ 照样进 `diffs` 判 DIVERGE（fail-loud）；
#     · 存在 `data-writes` 差异时**不得**降级——写覆盖不同说明有落在窗口之外
#       的写，窗口不能代表完整输出。
#   ★ 窗口的**完备性是声明者的责任**：buf 覆盖原地变换的全部 32 样本，
#     dest 覆盖源码里全部 d[0]/d[8] 写址（dct32.c:207-264，最远 dest+0xC27 < 0x1000）。
FDCT32_OUT = [('buf', 0x3cfac8, 0x80), ('dest', 0x3d3948, 0x1000)]

# ★★★ R288：`outputxy1`（8×16 ASCII 字形扫描 = 文字渲染核心）的**直接等价测试**。
#
#   取证（两侧符号表逐项核对，全部 SAME）：
#     scr_data   0x3b218c ｜ scr_h_size 0x3e1a94 ｜ scr_v_size 0x3e1a98
#     output_x   0x3e1a6c ｜ output_y   0x3e1a70 ｜ Rowspacing 0x3af01c
#   帧缓冲借用**具名对象** `items` @0x3d3948（size 0x3e80 = 16000 B）；
#   需要的写窗 320×16×2 = 10240 B (0x2800)，'A\0' 串放 +0x3000 与之不重叠。
#   ★ 为什么必须落在具名对象：访存指纹与输出窗只认 PT_LOAD 内地址；
#     用 SCRATCH（0x7D000000，工具自己 map 的）会让 `_validate_fn_corpus` 直接抛错。
#   ★ 判据：两侧把 'A' 画到同一帧缓冲后，**输出窗字节逐位比较**。
#     这正是 B6A 差异（245×51 文字块）的最小可判单元。
def _le32(x):
    return int(x).to_bytes(4, 'little', signed=False)


OUTPUTXY1_OUT = [('scr', 0x3d3948, 0x2800)]
OUTPUTXY1_SEED = [
    (0x3b218c, _le32(0x3d3948)),   # scr_data   = items（帧缓冲）
    (0x3e1a94, _le32(320)),        # scr_h_size = 320
    (0x3e1a98, _le32(240)),        # scr_v_size = 240
    (0x3e1a6c, _le32(0)),          # output_x   = 0
    (0x3e1a70, _le32(0)),          # output_y   = 0
    (0x3af01c, _le32(16)),         # Rowspacing = 16
    (0x3d6948, b'A\x00'),         # 待绘字符串（NUL 结尾 ⇒ 循环必然终止）
]

# ★★★ R288：`stbtt_InitFont` —— **stb 解析行为**的直接等价测试（B6A 的关键一环）。
#
#   取证：真机字体 `golden/sdcard_min/font.ttf` 共 1,840,376 B；表目录 + head/hhea/maxp/
#   cmap/loca/OS2 全部落在前 166,326 B 内（glyf 在 0x185bc、name/post/GPOS 更后）；
#   `stbtt_InitFont` 只读表目录与 head/maxp（ghlyf 仅记录偏移，不读内容）⇒ 前 166 KB 足够。
#   目标缓冲借用**具名大对象** `cns11643_inv_2charset` @0x33231c（166,326 B，两侧同址）——
#   它在本函数执行期间不被读取，且两侧种子逐位相同 ⇒ 不构成差异源。
#   判据：输出窗 `font`（124 B 结构，@0x3bc41c，两侧同址）**逐位比较**。
#   若两侧 `font` 相同 ⇒ 表解析/glyph 数/定位一致；不同 ⇒ 版本或实现差异（B6A 候选）。
def _font_head_bytes(n=166326):
    import os as _os
    p = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                      '..', 'golden', 'sdcard_min', 'font.ttf')
    with open(p, 'rb') as f:
        return f.read(n)


FONT_HEAD = _font_head_bytes()
STBTT_INITFONT_OUT = [('font', 0x3bc41c, 124)]

# ★★★ R289：`stbtt_MakeGlyphBitmapSubpixel` —— **字形光栅化**的直接等价判据
#   （B6A 差异块 245×51 文字行的最小可判单元）。
#
#   依赖链：必须先 `stbtt_InitFont(font, data, 0)` 把 `font` 结构填好（前置钩子 pre），
#   否则目标函数读到的 info 全 0 ⇒ 表现为"没渲染"而非报错。
#   参数（权威签名 `src/upstream/stb/stb_truetype.h:885`）：
#     (info, output, out_w, out_h, out_stride, scale_x, scale_y, shift_x, shift_y, glyph)
#   ① hard-float ABI：4 个 float 走 **s0–s3**（`F32` 类型化实参），
#      整数参数里第 5 个（out_stride）与第 6 个 core 参（glyph）走 [sp]/[sp+4]。
#   ② glyph 选 **8**：loca 实测其数据 [99,772+484, +176) 完全落在已播种的 166 KB 内
#      （glyf@0x185bc 之后的数据无法播种 —— 二进制里没有第二个 16 KB 以上的可写对象）。
#   ③ scale 取 `16 / unitsPerEm` ⇒ 与 UI 实际 16 px 字号同量级；输出窗 32×32。
_UNITS_PER_EM = struct.unpack('>H', FONT_HEAD[18:20])[0]
GLYPH_SCALE = 16.0 / _UNITS_PER_EM
GLYPH_W = 32
GLYPH_OUT = [('bmp', 0x3d3948, GLYPH_W * GLYPH_W)]

# ★★★ R290：`stbtt_GetGlyphBitmapBoxSubpixel` —— **字形落点 bbox** 的等价判据。
#   为什么它比光栅化更接近 B6A：位图已证等价（R289），若文字块仍偏移，机制只可能在
#   "字形画到屏幕的哪个位置" —— 即 bbox（+ advance）。
#   权威签名（本仓 stb_truetype.h）：(font, glyph, sx, sy, shx, shy, *ix0, *iy0, *ix1, *iy1)
#   ⇒ core 参 6 个（r0/r1/r2/r3 + [sp]/[sp+4]），float 4 个（s0–s3）。
#   输出窗 = 4 个 int（16 B），落在 items 内偏移 0x800（与帧缓冲 0x0..0x400 不重叠）。
GLYPH_BOX_ADDR = 0x3d3948 + 0x800
GLYPH_BOX_OUT = [('box', GLYPH_BOX_ADDR, 16)]

# ★★★ R291：`mui_outputxy_t` —— **UI 文字绘制本体**（坐标 + 颜色混合 + 裁剪）的等价判据。
#
#   这是 B6A 最后一个"文字侧"候选：字形位图/前宽度/bbox 已证逐位相同（R288–R290），
#   若绘制与混合也相同，则文字像素必相同 ⇒ B6A 只能来自 UI 几何（画什么、画在哪）或非文字元素。
#   事实（两侧同址，符号表核对）：OutRect@0x3bc4a4(24B) ｜ fontbitmap@0x3bc4bc(4096B 静态数组)。
#   OutRect 字段（由源码用法反推）：
#     +0  = 行 stride（像素）  ｜ +8 = clip top ｜ +12 = clip left ｜ +16 = clip bottom ｜ +20 = clip right
#   参数（源码定义）：(scr, x, y, 字号代码→height=(code+4)&0xff, 前景 RGB565, 字符串)
#   输出窗 = 帧缓冲 32×32×2 = 2048 B（混合后的最终像素）。
OUTRECT_OUT = [('scr', 0x3d3948, 2048)]
OUTRECT_SEED = [
    (0x33231c, FONT_HEAD),                     # 字体数据（前缀 InitFont 使用）
    (0x3bc4a4, _le32(32) + _le32(0) + _le32(0) + _le32(0) + _le32(32) + _le32(32)),
    (0x3d6948, b'A\x00'),                     # 待绘字符
]

FN_CORPUS = {
    # ★ R291：UI 文字绘制（'A'，16px，白字，32×32 帧缓冲，clip 全开）。
    'mui_outputxy_t': [
        ('A-16px-white', [0x3d3948, 0, 0, 12, 0xFFFF, 0x3d6948],
         OUTRECT_SEED, OUTRECT_OUT,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
        # 反例对照组：颜色取反（若两侧绘制等价，两个组的差异应只体现在颜色上）
        ('A-16px-red', [0x3d3948, 0, 0, 12, 0xF800, 0x3d6948],
         OUTRECT_SEED, OUTRECT_OUT,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
    ],
    # ★ R290：**字形前进宽度**（hmtx 读表 + 单位换算）—— 决定文字行总宽与后续元素落点。
    #   签名（本仓 stb_truetype.h）：(info, codepoint, int *advanceWidth, int *leftSideBearing)
    #   ⇒ 4 个 core 参全在 r0–r3；输出窗 = 8 B（两个 int）。
    'stbtt_GetCodepointHMetrics': [
        ('A', [0x3bc41c, 0x41, 0x3d3948 + 0x900, 0x3d3948 + 0x904],
         [(0x33231c, FONT_HEAD)], [('hm', 0x3d3948 + 0x900, 8)],
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
        ('U+4E00', [0x3bc41c, 0x4E00, 0x3d3948 + 0x900, 0x3d3948 + 0x904],
         [(0x33231c, FONT_HEAD)], [('hm', 0x3d3948 + 0x900, 8)],
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
    ],
    # ★ R290：文本宽度累加（决定后续元素布局）；返回 int ⇒ **返回值即判据**。
    #   args = (x=0, 字号代码 12 ⇒ 16px, 字符串)；OutRect.clip 播 300 允许两字符。
    'mui_outputxy_length.isra.19': [
        # 隔离组：空串 ⇒ 必须立刻返回 0（自证"字符串指针/种子确实生效"）
        ('empty-str', [0, 12, 0x3d6948],
         [(0x33231c, FONT_HEAD), (0x3d6948, b'\x00'),
          (0x3bc4a4 + 16, _le32(300))], None,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
        # 隔离组：clip=0 ⇒ 首字符后必停（自证"循环终止条件可被观测"）
        ('clip0', [0, 12, 0x3d6948],
         [(0x33231c, FONT_HEAD), (0x3d6948, b'AB\x00'),
          (0x3bc4a4 + 16, _le32(0))], None,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
        ('ascii-AB', [0, 12, 0x3d6948],
         [(0x33231c, FONT_HEAD), (0x3d6948, b'AB\x00'),
          (0x3bc4a4 + 16, _le32(300))], None,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
    ],
    # ★ R290：字形落点 bbox（glyph 8，16px）。
    'stbtt_GetGlyphBitmapBoxSubpixel': [
        ('g8-16px', [0x3bc41c, 8,
                     GLYPH_BOX_ADDR, GLYPH_BOX_ADDR + 4,
                     GLYPH_BOX_ADDR + 8, GLYPH_BOX_ADDR + 12,
                     F32(GLYPH_SCALE), F32(GLYPH_SCALE), F32(0.0), F32(0.0)],
         [(0x33231c, FONT_HEAD)], GLYPH_BOX_OUT,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
    ],
    # ★ R289：字形光栅化（真机字体 glyph 8，scale=16px）。只有 --fn stbtt_MakeGlyphBitmapSubpixel 时启用。
    'stbtt_MakeGlyphBitmapSubpixel': [
        # 组名自带 glyph 号；空字形（0）是"harness 自证"：无轮廓 ⇒ 必须极快返回。
        ('g0-empty', [0x3bc41c, 0x3d3948, GLYPH_W, GLYPH_W, GLYPH_W,
                      F32(GLYPH_SCALE), F32(GLYPH_SCALE), F32(0.0), F32(0.0), 0],
         [(0x33231c, FONT_HEAD)], GLYPH_OUT,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
        ('g3', [0x3bc41c, 0x3d3948, GLYPH_W, GLYPH_W, GLYPH_W,
                F32(GLYPH_SCALE), F32(GLYPH_SCALE), F32(0.0), F32(0.0), 3],
         [(0x33231c, FONT_HEAD)], GLYPH_OUT,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
        ('g4', [0x3bc41c, 0x3d3948, GLYPH_W, GLYPH_W, GLYPH_W,
                F32(GLYPH_SCALE), F32(GLYPH_SCALE), F32(0.0), F32(0.0), 4],
         [(0x33231c, FONT_HEAD)], GLYPH_OUT,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
        ('g8', [0x3bc41c, 0x3d3948, GLYPH_W, GLYPH_W, GLYPH_W,
                F32(GLYPH_SCALE), F32(GLYPH_SCALE), F32(0.0), F32(0.0), 8],
         [(0x33231c, FONT_HEAD)], GLYPH_OUT,
         [('stbtt_InitFont', [0x3bc41c, 0x33231c, 0])]),
    ],
    # ★ R288：stb 解析行为（真机字体前 166 KB）。只有 --fn stbtt_InitFont 时启用。
    'stbtt_InitFont': [
        ('ttf-head', [0x3bc41c, 0x33231c, 0], [(0x33231c, FONT_HEAD)], STBTT_INITFONT_OUT),
    ],
    # ★ R288：文字渲染核心（ASCII 8×16 路径）。只有 --fn outputxy1 时启用。
    'outputxy1': [
        ('ascii-A', [0x3d6948], OUTPUTXY1_SEED, OUTPUTXY1_OUT),
    ],
    # ★ 只在 `--fn xmp3_FDCT32` 时启用；`--fn` 不写棘轮台账（只有 --batch 写）。
    'xmp3_FDCT32': [
        # (组名, [buf, dest, offset, oddBlock, gb], [(vaddr, bytes)...], out_windows)
        ('legal-even', [0x3cfac8, 0x3d3948, 0, 0, 6],
         [(0x3cfac8, FDCT32_BUF_SEED)], FDCT32_OUT),
        ('legal-odd', [0x3cfac8, 0x3d3948, 0, 1, 6],
         [(0x3cfac8, FDCT32_BUF_SEED)], FDCT32_OUT),
        ('legal-shift', [0x3cfac8, 0x3d3948, 3, 0, 0],
         [(0x3cfac8, FDCT32_BUF_SEED)], FDCT32_OUT),
        ('legal-hi-off', [0x3cfac8, 0x3d3948, 7, 1, 3],
         [(0x3cfac8, FDCT32_BUF_SEED)], FDCT32_OUT),
    ],
}


def _validate_fn_corpus(bf, bo, fname):
    """FN_CORPUS 条目的**机械门禁**：种子地址与输出窗必须落在**两侧**都映射的段内。

    ★ 为什么必须查而不信手写常量：手写地址一旦因布局变动而失效，种子会写到
      未映射页 ⇒ `mem_write` 抛 UcError ⇒ 表现成"函数崩了"而不是"配置错了"。
      输出窗同理：窗口半截在段外 ⇒ `mem_read` 拿不到完整字节 ⇒ 本该判
      「输出不同」却报「读不到」，判据被悄悄换成更弱的那条。
    ★ fail-loud（第 98 轮纪律：装不上/不对就抛，绝不静默退化）。
    """
    # ★ R289：元组形状由 `_unpack_cps` 单一真源解析（此前这里手写 4 元解包 ⇒ 加 pre 后崩）
    for cname, _args, seed, outs, _pre in _unpack_cps(FN_CORPUS.get(fname, ())):
        for va, _bs in (seed or ()):
            for tag, b in (('工厂', bf), ('我方', bo)):
                if b.seg_of(va) is None:
                    raise ValueError(
                        'FN_CORPUS[%s] 组 %r 的种子地址 0x%x 不落在%s的任何 PT_LOAD 内'
                        % (fname, cname, va, tag))
        for _nm, va, sz in (outs or ()):
            for tag, b in (('工厂', bf), ('我方', bo)):
                if b.seg_of(va) is None or b.seg_of(va + sz - 1) is None:
                    raise ValueError(
                        'FN_CORPUS[%s] 组 %r 的输出窗 %s [0x%x,+0x%x) 不完整落在%s的任何 PT_LOAD 内'
                        % (fname, cname, _nm, va, sz, tag))


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
CALL_ALIAS = dict(libc_model.ALIASES)
# ★ 唯一真源 = `libc_model.ALIASES`。本条曾**真的踩过坑**：`__strdup` 加进了报告侧的
#   `CALL_ALIAS` 却漏加进模型的别名表，于是工厂侧"未建模 ⇒ 返回 NULL"、我们侧真执行
#   ⇒ 凭空造出 mxml 家族假发散；`_Znwj` 漏掉则一次造出 18 个假发散。
#   ⇒ 纪律 6/7 的重演：**两份硬编清单必然漂移**。现在报告侧直接派生自模型侧，
#     并由 `--self-test` 断言两者相等（`CALL_ALIAS == libc_model.ALIASES`）。


def coalesce_writes(seq):
    """写访问归一到**字节覆盖区间**（GAP 17.17）。

    ★ 为什么只对**写**做、不对读做（这个不对称是刻意的）：
      · 写：`两个相邻 4 字节写` 与 `一个 8 字节写` **写入的字节完全相同** ⇒ 语义等价。
        实测 `main`：工厂 `0x3e1298:4:W ×1` + `0x3e129c:4:W ×1`，我们 `0x3e1298:8:W ×1`
        —— 同一区间、同一内容，只是 clang 把两次相邻 32 位存合并成一次 64 位存。
        把"存储粒度"当判据 ⇒ 假发散（这是本项目第 N 次踩"把非语义量当判据"）。
      · 读：`读 1 字节` 与 `读 4 字节` **得到的值不同**（高位字节不一样）⇒ 粒度**是**语义。
        实测 `mui_search` 等：工厂读 `DisplayThumbnailflag+0:4`、我们读 `+0:1`
        —— 那是**真实的声明宽度缺陷**，必须继续报出来。
    ⇒ 归一化必须**方向敏感**：写合并、读不合并。
    """
    if not seq:
        return seq
    out = []
    for a, w, rw in sorted(seq):
        if out and out[-1][2] == rw == 'W' and out[-1][0] + out[-1][1] >= a:
            pa, pw, prw = out[-1]
            out[-1] = (pa, max(pa + pw, a + w) - pa, prw)
        else:
            out.append((a, w, rw))
    return out


def norm_calls(seq):
    return [CALL_ALIAS.get(x, x) for x in seq]


# ★ 外部调用的「**机制等价**族」（GAP 17.16）：**同一个操作的两种实现路径**。
#   实测背景：`strupr` 工厂侧调 `islower`（函数），我方调 `__ctype_b_loc`（表宏）——
#   两者都是"测试该字符是否小写"，只是 glibc 头版本/编译器把宏展开成了不同形态。
#
#   ★ 与 `CALL_ALIAS` 的区别（很重要，别混用）：
#     `CALL_ALIAS` 是"**名字不同、同一个函数**"（`_Znwj` 就是 `operator new`）；
#     `CALL_MECH`  是"**实现路径不同、同一个操作**"，因此它**只在其余观测量全部一致时**
#                   才把该差异降级为 INFO，并且**报告里同时打印两侧原始调用名**。
#   依据：`libc_model` 的 ctype 表与谓词函数**按位一致**（自证 29 条），
#         否则"函数式"与"表式"两条路径会给出不同答案 ⇒ 归一化就不成立。
CALL_MECH = {
    'islower': 'ctype:predicate', 'isupper': 'ctype:predicate',
    'isalpha': 'ctype:predicate', 'isdigit': 'ctype:predicate',
    'isspace': 'ctype:predicate', 'isalnum': 'ctype:predicate',
    'ispunct': 'ctype:predicate', 'isxdigit': 'ctype:predicate',
    'isprint': 'ctype:predicate', 'isgraph': 'ctype:predicate',
    'isblank': 'ctype:predicate', 'iscntrl': 'ctype:predicate',
    '__ctype_b_loc': 'ctype:predicate',
    'toupper': 'ctype:map', 'tolower': 'ctype:map',
    '__ctype_toupper_loc': 'ctype:map', '__ctype_tolower_loc': 'ctype:map',
}


def norm_mech(seq):
    """→ 机制归一后的调用序列（**仅供"是否同一操作"的判定**；报告仍打印原始名）。"""
    return [CALL_MECH.get(x, x) for x in seq]


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
        cn = canon_obj_name(nm)
        # ★★ 2026-09-30（§0.42）：**用规范名做集合判定，也用规范名做键**。
        #   只用规范名判集合、键里仍留原始名 ⇒ 两侧键还是不一样，等于没修。
        if cn in spec_private:
            # ★ 显示里**必须带上绝对地址**：同名两份时只写 `handle+0` 读者无法判断是哪一份
            #   ⇒ 失去可审计性（本条的实测教训：曾因此把"同址"误读成"异址"）。
            # ★★ 2026-10-20（R218）：**越界前驱**修正（locale_charset 假发散的根因）。
            #   `nearest_sym` 语义是"最近前驱"，**不保证** addr 落在 `[sa, sa+sz)` 内。
            #   实测铁证：工厂 locale_charset 读的空串字面量 0x3acff0（内容 00 00 00 00）
            #   紧贴在 `asso_values.9691`（LOCAL，`[0x3acef0, 0x3acff0)`，sz=256）之后
            #   恰好 1 字节 ⇒ 被 nearest_sym 归因成 `asso_values+256`（偏移==size，越界）⇒
            #   错按私有名字配对（'LN' 形）⇒ 我方读自己链接的空串（'A' 形，被 fspans 过滤）
            #   ⇒ 凭空造出「仅F 读 asso_values+256」的假发散。
            #   修复：纯私有配对**必须**确认 addr 在区间内；越界 ⇒ 退回按地址 'A' 形，
            #   交给 norm_fp 的 fspans 过滤，与对侧同样处理。
            #   保守默认：size 未知（0 / 缺失）时**不做**越界排除，保持旧行为（不碰未知）。
            _ds = b.data_syms.get(nm)
            _sz = _ds[1] if _ds else 0
            if _sz == 0 or a < sa + _sz:
                return (('LN', cn, a - sa, w, rw),
                        '%s+%d:%d:%s@0x%x' % (cn, a - sa, w, rw, a))
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


def read_width_only(kf, ko):
    """→ (是否"仅访存宽度不同", 粒度差异描述列表)。

    ★ 精确定义：两侧读的**对象与地址完全一致**，唯一差别是**每次读的宽度**。

    为什么这类要单独摘出来（GAP 17.18，**证据驱动的自我更正**）：
      我最初把"同址不同宽"直接写成"读到的值不同 ⇒ 真实声明缺陷"。**那是错的。**
      实证 `DisplayThumbnailflag`：源码声明是 `unsigned int`（`globals.h` 4 字节），
      而所有用法只触及低字节（`& 8` / `& 0xfe` / `| 2` / `| 0xc`）⇒ clang 做
      **load-narrowing**（只用到低字节 ⇒ 合法地把 4B 载入窄化成 1B）。
      GCC 6.2 没做 ⇒ 工厂读 4B、我们读 1B。**同址、低位值相同 ⇒ 语义等价**，
      与"写被合并成 8B"（`coalesce_writes`）是同一类**访问粒度**差异。
      ⇒ 它对"值"无影响，因此只在**其余观测量全部一致**时才降级为 INFO 并留痕。

    反向约束（防这次放宽被滥用）：若地址集合不同（一侧少读/多读某对象），
    仍然照旧报 `data-reads` 发散 —— 那条路径（R-SET）才可能对应真缺失。
    """
    if not kf or not ko:
        return False, []
    # ★★ 2026-09-28 修（键布局缺陷）：两种键形的宽度下标**不同**。
    #   'LN' 形 = ('LN', name, off, w, rw)  ⇒ 宽度 k[3]、偏移 k[2]
    #   'A'  形 = ('A',  addr, w, rw)       ⇒ 宽度 k[2]
    #   旧实现一律取 k[2] ⇒ 对 'LN' 取到的是**偏移**（两侧通常都是 0）⇒ 差值恒空
    #   ⇒ `rw_only` 恒 False ⇒ "合法窄化降级 INFO"对具名全局从未生效。
    #   自证盲区的原因：旧锚点只用 'A' 形。
    def width_of(k):
        return k[3] if k[0] == 'LN' else k[2]

    # 对象标识（**去掉宽度、保留偏移**）：
    #   'LN' → (kind, name, off, rw)；'A' → (kind, addr, rw)
    #   ★ 保留 off 是关键：否则"同一对象不同偏移"会被合并，
    #     一侧**少读一次**也会被当成"仅宽度不同"放过（放宽滥用）。
    def ident(k):
        return (k[0], k[1], k[2], k[4]) if k[0] == 'LN' else (k[0], k[1], k[3])

    mf, mo = {}, {}
    for k in kf:
        mf.setdefault(ident(k), []).append(width_of(k))
    for k in ko:
        mo.setdefault(ident(k), []).append(width_of(k))
    if set(mf) != set(mo):
        return False, []
    diff = []
    for i in mf:
        # ★★ 2026-09-28 收紧：**次数必须相同**才谈"仅宽度不同"。
        #   实测（新锚点）：同（对象,偏移,方向）下"读 2 次 vs 读 1 次"会被旧实现
        #   当成宽度差异而放过 —— 那是"少读/多读"，必须照旧报发散。
        if len(mf[i]) != len(mo[i]):
            return False, []
        if sorted(mf[i]) != sorted(mo[i]):
            diff.append('%s 宽 F=%s O=%s' % (i, sorted(set(mf[i])), sorted(set(mo[i]))))
    return bool(diff), diff[:6]


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
# ★★★ 2026-09-29（纪律 73/74）：台账必须自带**尺子口径指纹 + 被测产物 sha**。
#   病灶（CI s36 实测，见 §0.36）：台账只记 `steps`/`escalate`，**不记判据口径**。
#   §0.26 把行为尺升到 v2（机械实现 §2.3：参照侧早死 ⇒ 新桶 REFDEAD）之后，
#   同一份产物、同一份台账，"DIVERGE 集合"**已不可比** —— 于是 CI 报
#   「★新增 9」时，**分不清是"我们改坏了"还是"尺子换了"**（这正是本项目反复出现的
#   "假绿/假红同源"问题）。实测该次 CI：既有 81 项 / 本轮发散 36 / 新增 9 / 收敛 49。
#   修法：指纹**从事实机械推导**（`compare()`/`partition_ok()` 的源码 + 判据常量取值），
#   不手填版本号 ⇒ 任何改动判据核心的编辑都会改变指纹 ⇒ 台账立刻失效 ⇒ fail-closed，
#   必须显式 `--rebaseline --reason "..."` 才能重新记账。**不得静默沿用旧账。**
LEDGER_RULER_RE = re.compile(r'^#\s*ruler\s*=\s*([0-9a-fA-F]{8,64})\s*$')
LEDGER_OURS_RE = re.compile(r'^#\s*ours\s*=\s*([0-9a-fA-F]{4,64})\s*$')
LEDGER_WHY_RE = re.compile(r'^#\s*rebaseline\s*:\s*(.+?)\s*$')
# 判据口径的"常量面"：新增/修改**任何影响分桶的开关或常量**时，必须登记到这里
# （登记后指纹自动变化 ⇒ 旧台账自动失效 ⇒ 不会静默沿用）。
RULER_CONSTANT_NAMES = ('ESCALATE_FACTOR',)
# ★ 开关分两类，**必须区别对待**（否则指纹会把"后端等价"误判成"判据变更"）：
#   · 判据开关：**改变分桶语义** ⇒ 必须把**生效值**纳入指纹
#     （如 `CGM_REFDEAD_OFF=1` 会取消 REFDEAD 桶 ⇒ "DIVERGE 集合"随之改变）。
#   · 执行后端开关：只换实现、**不改判据** ⇒ 只记**名字**，不记值
#     （`CGM_MACHINE_REUSE` 已在 §0.28 用 sha256 逐字节证明与默认路径等价；
#      记值会让"本地带 reuse、CI 不带"这种无关差异把台账判废）。
RULER_PROTOCOL_SWITCHES = ('CGM_REFDEAD_OFF', 'CGM_INLINE_MOVE_OFF', 'CGM_DEADEQ2_OFF')
RULER_BACKEND_SWITCH_NAMES = ('CGM_MACHINE_REUSE', 'CGM_NO_LIBC_MODEL')

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


def itanium_base(name):
    """Itanium C++ ABI mangled 名 → **基础函数名**（最内层那一节）。非 mangled 原样返回。

    ★ 为什么必须有它（2026-09-27，尺子缺陷实证）：
      `void_fns_from_corpus()` 从 Ghidra 语料取的是**反编译后的名字**（demangle 形态）：
          void inflate_blocks_reset(inflate_blocks_state *param_1, ...)
          void unzlocal_DosDateToTmuDate(ulong param_1, tm_unz_s *param_2)
      而 `compare()` 收到的 `fname` 是 **ELF 符号表里的 mangled 名**：
          _Z20inflate_blocks_resetP20inflate_blocks_stateP10z_stream_sPm
          _Z25unzlocal_DosDateToTmuDatemP8tm_unz_s
      ⇒ `fname in void_fns` **永远 False** ⇒ 所有 C++ 函数的 void 判定失效
      ⇒ 拿 void 函数的 **r0 残留值**当返回值比 ⇒ **假发散**（实测两条：
         `_Z20inflate_blocks_reset` 的 `ret F=0x7d000100 O=0x0`、
         `_Z25unzlocal_DosDateToTmuDate` 的 `ret F=0x8 O=0x7`）。

    规则（Itanium ABI）：`_Z` 之后若为 `N` 则是嵌套名，逐节 `<长度><标识符>` 直到 `E`；
    否则是单节 `<长度><标识符>`。函数名 = **最后一节**。
    """
    if not name or not name.startswith('_Z') or len(name) < 3:
        return name
    i = 2
    last = None
    nested = name[2:3] == 'N'
    if nested:
        i = 3
    while i < len(name):
        j = i
        while j < len(name) and name[j].isdigit():
            j += 1
        if j == i or j >= len(name):
            break                      # 没有长度前缀 ⇒ 不是合法的节
        ln = int(name[i:j])
        if ln <= 0 or j + ln > len(name):
            break
        last = name[j:j + ln]
        i = j + ln
        if not nested:
            break
    return last or name


_VOID_SRC_CACHE = None


def void_fns_from_sources(root=None):
    """从**上游库源码**机械提取 `void` 返回的函数名（唯一真源的第二个来源）。

    ★ 为什么需要第二个来源（本轮实测）：
      `void_fns_from_corpus()` 只从 **Ghidra 语料**取名，而上游单头库（stb/mxml/mp3/
      libiconv …）**根本不在语料里** ⇒ 它们的 `static void` 函数不在表里
      ⇒ `r0` 残留被当成返回值 ⇒ 假发散。
      实测：`stbtt__csctx_rccurve_to`（源码 `static void`）在 `-Os` 下报
      `ret F=0x7d000100 O=0x1`，而它在 `-O2` 下被内联 ⇒ 残留恰好相同 ⇒ 一直没暴露。

    ★ 方向保守：**只扫 `src/upstream/**`**（原版源码，签名可信）。
      `src/proprietary/**` 是 Ghidra 重建，签名本身可能是推测 ——
      把"其实有返回值"的函数误判成 void 会**掩盖真差异**。
      本项目口径：宁可多发散，不可漏发散。

    正则覆盖 `static void f(` / `void f(` / `inline void f(` / `STBTT_DEF void f(`。
    """
    import glob as _g
    import re as _re

    global _VOID_SRC_CACHE
    if _VOID_SRC_CACHE is not None and root is None:
        return _VOID_SRC_CACHE
    base = root or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'upstream')
    pat = _re.compile(
        r'^[ \t]*(?:static[ \t]+|inline[ \t]+|STBTT_DEF[ \t]+|STBTT_DEF\s+|extern[ \t]+)*'
        r'void[ \t]+([A-Za-z_]\w*)[ \t]*\(', _re.M)
    out = set()
    for f in (_g.glob(os.path.join(base, '**', '*.h'), recursive=True)
              + _g.glob(os.path.join(base, '**', '*.c'), recursive=True)):
        try:
            txt = open(f, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        out.update(pat.findall(txt))
    if root is None:
        _VOID_SRC_CACHE = out
    return out


def void_fns_all():
    """void 表的**唯一真源** = Ghidra 语料 ∪ 上游源码签名。"""
    vf, _ = void_fns_from_corpus()
    return set(vf) | void_fns_from_sources()


def is_void_fn(void_fns, fname):
    """→ 该函数是否为 void（**同时按原名与 demangle 后的基础名查**）。"""
    if not void_fns:
        return False
    return fname in void_fns or itanium_base(fname) in void_fns



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


def read_ledger_meta(txt):
    """台账头部元信息 → {'ruler':.., 'ours':.., 'rebaseline':..}（缺失记 None）。

    ★ 与 `read_ledger_text` 分开：后者是既有**纯函数接口**（自证锚点在用），
      不动它可保证"台账内容语义"零回归；元信息是本次新增的**第二类**信息。
    """
    meta = {'ruler': None, 'ours': None, 'rebaseline': None}
    for ln in txt.splitlines():
        s = ln.strip()
        if not s.startswith('#'):
            continue
        for key, rx in (('ruler', LEDGER_RULER_RE), ('ours', LEDGER_OURS_RE),
                        ('rebaseline', LEDGER_WHY_RE)):
            m = rx.match(s)
            if m and meta[key] is None:
                meta[key] = m.group(1)
    return meta


def ledger_protocol_guard(ledger_path, cur_ruler, will_write, steps=3000):
    """台账**口径门禁**（fail-closed）。返回 `(ok, lines)`。

    ★ 必须在**批量对拍之前**调用：否则会先白跑一整轮（本机 ≈2.5 min / 云上更贵）
      才报"台账口径不一致"—— 那既浪费算力，也鼓励"把门禁绕过去"。
    ★ 为什么必须是硬失败而不是告警：口径一变，"DIVERGE 集合"就**不可比**；
      沿用旧账会把"尺子换了"报成「★新增发散」（CI s36 实测：既有 81 / 发散 36 / 新增 9），
      于是**真回归与口径漂移混在一起**，两个方向都读不出来。
    """
    if not ledger_path or will_write or not os.path.exists(ledger_path):
        return True, []
    txt = open(ledger_path, encoding='utf-8', errors='replace').read()
    meta = read_ledger_meta(txt)
    if meta['ruler'] == cur_ruler:
        return True, []
    lines = [
        '',
        '  ★★ 台账的**判据口径**与当前尺子不一致 ⇒ fail-closed（exit 3）',
        '     台账 ruler = %s' % (meta['ruler'] or '（缺 —— 旧台账未记口径）'),
        '     当前 ruler = %s' % cur_ruler,
        '     为什么   ： 口径一变，"DIVERGE 集合"就**不可比**；沿用旧账会把"尺子换了"'
        '误报成「★新增发散」',
        '     修法     ： **显式重新记账**（留痕；新台账会记下 ruler / 被测产物 sha / 原因）——',
        '                python tools/diff_exec.py --batch --steps %d --ledger %s '
        '--rebaseline --reason "口径变更原因"' % (steps, ledger_path),
    ]
    return False, lines


def ledger_steps_ok(declared_steps, declared_esc, actual_steps, actual_esc):
    """★ 台账必须在**同一判据强度**下评测：步数预算或放大预算不一致 ⇒ fail-closed。

    为什么必须硬失败而不是告警：`--update-ledger` 在低预算下会把"其实有分歧、只是跑不完"
    的函数判成 TRUNC 并**从台账里删掉** ⇒ 台账静默变弱、CI 照样全绿。
    """
    return (declared_steps is not None and int(declared_steps) == int(actual_steps)
            and declared_esc is not None and int(declared_esc) == int(actual_esc))


def ledger_update(old, diverging, undecidable):
    """棘轮更新语义（纯函数）：

      保留 = 本轮**发散** ∪ 本轮**不可判**
      移除 = 旧台账里本轮被**明确判为 PASS/INFO** 的项

    ★ 核心不变式：**"没有被证明等价" 就留在台账里**。
      发散（DIVERGE）与不可判（TRUNC/SKIP）**都**属于"未证明等价"，必须**同等**保留 ——
      否则"未知"会被静默改写成"没问题"，这正是台账最容易烂掉的方式（GAP 17.10）。

    ★★ 第 64 轮实测到的**真实缺陷（本条被修的原因）**：
      旧实现写的是 `keep = diverging ∪ (old ∩ undecidable)` —— 那个 `∩ old` 让
      **本轮新出现的不可判项永远进不了台账**（它们只可能出现在 `undecidable` 里，
      还没机会成为 `old`）。实测：`MP3InitDecoder` / `TestRun` / `WaitNMI` /
      `xmp3_AllocateBuffers` 连续多轮 TRUNC，而台账里**一个都没有** ⇒
      台账表面上"只剩 77 项在收敛"，其实**把 4 项不可判债务藏在了台账之外**。
      ⇒ 修法：直接取 `diverging ∪ undecidable`，不再与旧台账求交。
    """
    keep = set(diverging) | set(undecidable)
    removed = sorted(set(old) - keep)
    kept_undec = sorted(set(undecidable) - set(diverging))
    return sorted(keep), removed, kept_undec


def _fault_str(f):
    """未映射访问现场 → 人读字符串。

    ★ 为什么单独成函数（纪律 69）：报告、明细、此处都要用同一种展示，
      各写一份必然漂移。`access` 是 Unicorn 的整数取值
      （`UC_MEM_READ=16` / `UC_MEM_WRITE=17` / `UC_MEM_FETCH=18`）。
    """
    if not f:
        return '无'
    acc, addr, size = f
    # ★ 2026-10-01 修：**UNMAPPED 事件用的是自己的访问码**，不是 UC_MEM_READ/WRITE/FETCH。
    #   Unicorn 约定：READ=16 / WRITE=17 / FETCH=18，而
    #                 READ_UNMAPPED=19 / WRITE_UNMAPPED=20 / FETCH_UNMAPPED=21。
    #   本函数原来只映射了 16/17/18 ⇒ 每次现场都被打成裸数字 "19@"（报告里真实出现过），
    #   读者看不出是"读未映射"还是"写未映射" ⇒ 证据力打折。
    kind = {16: 'R', 17: 'W', 18: 'X',
            19: 'R!', 20: 'W!', 21: 'X!'}.get(acc, str(acc))
    return '%s@0x%x sz=%d' % (kind, addr, size)


def _fault_out_of_segments(addr, *bins):
    """死亡地址是否落在**所有**产物的 PT_LOAD 段**之外**。

    ★ 用途（DEADEQ-v2，第 153 轮）：只有落在所有段之外的死亡地址才是
      「野指针 / NULL 解引用」——它两侧的语义同为「解引用了一个未初始化的
      指针」，**与数据布局无关，因此可比**。落在段内的死亡地址是绝对地址，
      两侧段布局不同 ⇒ 不可比（§0.46 的实测结论）。
    ★ 只读探针先行：见 `build/_r153_probe.py`（在现有 batch 数据上模拟过，
      5 个 UNDECIDABLE 的死亡地址全部落在段外：0x0 / 0x1 / 0x40）。
    """
    if addr is None:
        return False
    for b in bins:
        for seg in b.segs:
            va, fsz, msz = seg[0], seg[1], seg[2]
            if va <= addr < va + msz:
                return False
    return True


def trace_diffs(rf, ro, bf, bo, fname, spec_private, fspans, void_fns=None,
                allow_terminal=True, cap_f=False, cap_o=False, cap_asym=False):
    """两条轨迹的**观测差异** —— 唯一真源（全量路径与「共同视野前缀」路径共用）。

    ★ 为什么必须抽出来（2026-10-01）：两侧**同类早死**时要把共同视野前缀拿来比，
      若在那里再写一份比对逻辑 ⇒ 必然与全量路径漂移交（纪律 69：同一规则禁止写两处）。
    ★ `allow_terminal=False`：轨迹被**硬截断**时，`ret`/`stopped` **没有观测力**
      （截断处不是程序的终点）⇒ 不作判据。其余（调用/访存/终值内容）仍可比，
      因为两侧被截到**同一条指令数**，视野相同。
    返回 `(diffs, note, ret_unjudged, fps)`；`fps` 供 `--dump-rows` 留痕。
    """
    diffs, note, ret_unjudged = [], '', False
    sf, so = norm_stop(rf['stopped']), norm_stop(ro['stopped'])
    if allow_terminal:
        if sf != so:
            diffs.append('stop F=%s O=%s%s' % (sf, so, ' (cap-asym)' if cap_asym else ''))
        # ★ ret 只在**两侧都正常返回**且**都没被截断**时才是判据
        if sf == 'return' and so == 'return' and (not cap_f) and (not cap_o) and rf['ret'] != ro['ret']:
            # ★ 地址类返回值（指向各自映像里的字符串/表）：比**内容**而不是比地址。
            #   实测：`_Z11zlibVersionv` 返回各自的版本串地址（0x2dc7dc vs 0x4da2a3），
            #   内容相同 ⇒ 语义等价；只比数值会误判成发散。
            if rf['ret_content'] and rf['ret_content'] == ro['ret_content']:
                pass
            elif is_void_fn(void_fns, fname):
                # ★ void 函数的 r0 **不是输出**（实测 AudioProcess：工厂残留 0xf4240、
                #   我们残留 0x0，其余观测量全一致）⇒ 不作判据（GAP 17.12）
                # ★ 2026-09-27 修：查表必须走 `is_void_fn`（含 Itanium demangle），
                #   否则所有 C++ mangled 函数都漏判 ⇒ 假发散（见 itanium_base 注释）。
                ret_unjudged = True
            else:
                diffs.append('ret F=0x%x O=0x%x' % (rf['ret'], ro['ret']))
    cf, co = norm_calls(rf['calls_ext']), norm_calls(ro['calls_ext'])
    wk_f, wsh_f = norm_fp(bf, coalesce_writes(rf['writes']), spec_private, fspans)
    wk_o, wsh_o = norm_fp(bo, coalesce_writes(ro['writes']), spec_private, fspans)
    if wk_f != wk_o:
        diffs.append('data-writes %s' % _fp_diff(wk_f, wsh_f, wk_o, wsh_o))
    rk_f, rsh_f = norm_fp(bf, rf['reads'], spec_private, fspans)
    rk_o, rsh_o = norm_fp(bo, ro['reads'], spec_private, fspans)
    rw_only, rw_why = (False, [])
    if rk_f != rk_o:
        rw_only, rw_why = read_width_only(rk_f, rk_o)
        if os.environ.get('CGM_DBG_RW') == '1':
            # ★ 调试钩子（2026-09-28）：宽度降级为什么没生效？打印**原始键**。
            sys.stderr.write('  [rw] %s rw_only=%s\n      F=%s\n      O=%s\n'
                             % (fname, rw_only, rk_f, rk_o))
        if not rw_only:
            diffs.append('data-reads %s' % _fp_diff(rk_f, rsh_f, rk_o, rsh_o))
    common = set(rf['final']) & set(ro['final'])
    fd = [k for k in sorted(common) if rf['final'][k] != ro['final'][k]]
    if fd:
        diffs.append('data-final 不同 %d 项 %s' % (len(fd), fd[:6]))
    # ★ 外部调用判据放在最后：区分「内联等价」「机制等价」与「真的少调/多调/顺序变」
    if rw_only and not diffs:
        # 仅"访存粒度"不同（同址、同对象、仅宽度）⇒ 降级为 INFO 并**列名留痕**
        note = '粒度等价（仅访存宽度不同、同址同对象）: %s' % '; '.join(rw_why)
    if cf != co:
        only_missing = [x for x in cf if x not in co]
        only_extra = [x for x in co if x not in cf]
        plain = [d for d in diffs if not d.startswith('calls_ext')]
        if (not plain) and norm_mech(cf) == norm_mech(co):
            # ★ 同一操作的两种实现路径（CALL_MECH）：**必须**其余观测量全一致才降级，
            #   且 note 里同时打印两侧原始名 ⇒ 读者可自行复核，不是"抹掉差异"。
            note = ('机制等价（同一操作、不同实现路径）: F=%s O=%s'
                    % (sorted(set(cf))[:6], sorted(set(co))[:6]))
        elif (not plain) and only_missing and (not only_extra):
            # 其余观测量**全部一致** + 只是少调了工厂的某些调用 ⇒ 内联/等价实现
            note = '内联等价: 仅工厂侧调用 %s' % (only_missing[:6],)
        else:
            raw = '' if (rf['calls_ext'] == ro['calls_ext']) else ' (原始名不同)'
            diffs.append('calls_ext F=%s O=%s%s' % (cf[:10], co[:10], raw))
    # ★ 仪器可见性（GAP 17.16）：未建模的外部调用在两侧**不同**时，说明有一条路径
    #   我们其实"没真跑" ⇒ 必须留痕（不作为发散，但也不许静默）。它只影响 note。
    um_f, um_o = set(rf.get('unmodelled') or ()), set(ro.get('unmodelled') or ())
    if um_f != um_o:
        note = (note + ' ;; ' if note else '') + \
            '仪器：未建模外部调用不同 F=%s O=%s' % (sorted(um_f)[:5], sorted(um_o)[:5])
    fps = dict(wr_f=[list(x) for x in sorted(wk_f)], wr_o=[list(x) for x in sorted(wk_o)],
               rd_f=[list(x) for x in sorted(rk_f)], rd_o=[list(x) for x in sorted(rk_o)],
               ca_f=list(cf), ca_o=list(co))
    return diffs, note, ret_unjudged, fps


def _out_window_diffs(rf, ro, outs):
    """输出窗逐位比对（第 160 轮，判据③的直接实现）。

    → (差异数据, 全部窗口是否逐位相同, 相同窗口的描述列表)。

    ★ **纯函数**：只读 `rf`/`ro` 的 `out_bytes` 字段 ⇒ 可离线自证（--self-test）。
    ★ `out_bytes` 由 `run_func(out_windows=...)` 在执行结束后从机器里读出；
      读不到（窗口落在段外）记 `None` ⇒ 这里报「不可读」⇒ fail-loud。
    """
    if not outs:
        return [], False, []
    ob_f, ob_o = rf.get('out_bytes') or {}, ro.get('out_bytes') or {}
    diffs, ok_names = [], []
    for nm, va, sz in outs:
        bf_b, of_b = ob_f.get(nm), ob_o.get(nm)
        if bf_b is None or of_b is None:
            diffs.append('data-out %s 不可读（窗口落在段外？）' % nm)
            continue
        if bf_b != of_b:
            n = sum(1 for i in range(sz) if bf_b[i] != of_b[i])
            first = next(i for i in range(sz) if bf_b[i] != of_b[i])
            diffs.append('data-out %s 不同 %d/%dB @0x%x F=%s O=%s'
                         % (nm, n, sz, va + first,
                            bf_b[first:first + 8].hex(), of_b[first:first + 8].hex()))
        else:
            ok_names.append('%s[0x%x+0x%x]' % (nm, va, sz))
    all_ok = bool(ok_names) and len(ok_names) == len(outs)
    return diffs, all_ok, ok_names


def _apply_out_equiv(diffs, note, out_ok, out_names_ok):
    """输出等价降级（第 160 轮）。→ (diffs, note, 被降级掉的 data-reads 列表)。

    前提（由调用方在前面机械检查）：`out_ok` = 输出窗**全部**逐位相同。
    ★ **反向约束**：存在 `data-writes` 差异时**不得**降级——写覆盖不同说明有
      落在窗口之外的写，窗口不能代表完整输出。
    ★ 降级**只动 `data-reads`**：stop/ret/calls_ext/data-final/data-writes
      一律保留——它们不是"访问模式"，照旧是判据。
    """
    if not out_ok or any(d.startswith('data-writes') for d in diffs):
        return diffs, note, []
    kept, suppressed = [], []
    for d in diffs:
        if d.startswith('data-reads'):
            suppressed.append(d)
        else:
            kept.append(d)
    if suppressed:
        note = (note + ' ;; ' if note else '') + \
            '输出等价（输出窗 %s 逐位相同）⇒ data-reads 差异被证明不影响输出' \
            % ','.join(out_names_ok)
    return kept, note, suppressed


# ★★★ R290：**克隆函数配对归一**（判据先行）
#
#   问题（实测）：工厂 `mui_outputxy_length.isra.19` vs 我方 `mui_outputxy_length_isra_19`，
#   名字不同 ⇒ 旧实现 `set(BF.funcs) & set(BO.funcs)` 里根本不存在这一对 ⇒
#   **从未被比较**。工厂共 12 个 `.isra/.part/.constprop` 克隆，其中 9 个属于这种情况。
#
#   判据（保守，宁可"不配对并公示"也不猜）：
#     ① 完全同名 ⇒ 直接配对（原行为）；
#     ② 否则按"去克隆后缀"的键配对，且**仅当两侧在该键上都恰好 1 个**；
#     ③ 两侧同键多候选（歧义）⇒ **不配对**，记入 `ambiguous` 并在报告里逐条公示；
#     ④ `_pair_key` 只剥离**尾部** `.{isra,part,constprop}.N` 或 `_{isra,part,constprop}_N`。
CLONE_RE = re.compile(r'(?:[._])(isra|part|constprop)(?:[._])(\d+)$')


def _pair_key(name):
    """去克隆后缀的配对键（幂等）。"""
    return CLONE_RE.sub('', name)


def build_pairs(BF, BO):
    """→ (pairs: {工厂名: (工厂名, 我方名)}, ambiguous: [(键, 工厂候选, 我方候选)])"""
    exact = set(BF.funcs) & set(BO.funcs)
    pairs = {n: (n, n) for n in exact}
    fk, ok = {}, {}
    for n in BF.funcs:
        if n not in exact:
            fk.setdefault(_pair_key(n), []).append(n)
    for n in BO.funcs:
        if n not in exact:
            ok.setdefault(_pair_key(n), []).append(n)
    ambiguous = []
    for k in sorted(set(fk) & set(ok)):
        if len(fk[k]) == 1 and len(ok[k]) == 1:
            pairs[fk[k][0]] = (fk[k][0], ok[k][0])
        else:
            ambiguous.append((k, sorted(fk[k]), sorted(ok[k])))
    return pairs, ambiguous


def compare(bf, bo, fname, steps=20000, corpus=None, void_fns=None, out=None, o_name=None):
    """★ R290：`o_name` —— 我方侧函数名（配对归一后可能与工厂侧不同）：

    工厂 GCC 的克隆名是 `X.isra.16`，我方 clang 是 `X` 或 `X_isra_16`；
    旧实现只按**完全同名**配对 ⇒ 这类函数**从未被比较**（覆盖漏洞，实测 12 个克隆里 9 个未配对）。
    显示名一律用工厂侧（读者按工厂符号定位），执行时才使用各自的真实符号名。
    """
    rows, verdict = [], 'PASS'
    # ★★★ 2026-09-29 新增：**逐组机器可读明细**（`--dump-rows`）。
    #   为什么必须（否则归类只能看人类的"前 80 行"截断）：
    #   收敛的单位是**差异类别**（§0.2），而类别只能从**完整**的逐组指纹里聚出来。
    #   报告里的 "前 80" 是给人看的摘要，**不是**可统计的数据源 ——
    #   拿它做分类等于抽样，会直接导致"逐函数打补丁"式的绕圈。
    xr = []

    def _x(kind, sf_, so_, **kw):
        d = dict(fn=fname, grp=cname, kind=kind, sf=sf_, so=so_)
        d.update(kw)
        xr.append(d)
    # ★ 可比访问区 = **两侧**具名数据对象的区间并集（排除 .got/.dynamic 等 link 元数据）
    spans = _build_spans(bf, bo)
    # ★ 访存指纹的归一口径以**工厂的符号绑定**为准（工厂是规格）
    spec_private = bf.pure_private()   # 工厂里"唯一且 LOCAL"的名字（地址是实现细节）
    fspans = _build_spans(bf)          # 工厂侧单独的可比区段（用于"按地址配对"的过滤）
    # ★ 最终内容两侧共用**工厂的符号名**（同址同名才可比）
    kw = dict(steps=steps, spans=spans, syms_for_final=bf.data_syms)
    ret_unjudged = False
    for cname, args, cseed, outs, cpre in _unpack_cps(corpus or CORPUS):
        rf = run_func(bf, fname, args, seed=cseed, out_windows=outs, pre=cpre, **kw)
        ro = run_func(bo, o_name or fname, args, seed=cseed, out_windows=outs, pre=cpre, **kw)
        if rf.get('error') or ro.get('error'):
            rows.append((cname, 'SKIP', rf.get('error'), ro.get('error')))
            _x('SKIP', None, None, err=str(rf.get('error') or ro.get('error'))[:100])
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
            _x('trunc', 'cap', 'cap', why=why)
            continue
        diffs = []
        sf, so = norm_stop(rf['stopped']), norm_stop(ro['stopped'])
        # ★★★ 2026-09-29 新增：**参照侧(F)内存未映射早死 ⇒ 本组不可判**（机械实现 §2.3）。
        #   机制：沙箱里 F 侧一解引用就 UC_ERR_*_UNMAPPED ⇒ 它的 calls_ext/访存/final **全都没有观测力**；
        #   而我们这一侧继续跑完 ⇒ "F 侧空、O 侧有" 会被算成**我们的发散**。这就是 §2.3 点名、
        #   但从 2026-09-22 起一直**没有做成机械判据**的老账。
        #   实证（2026-09-29 GCC 6.3 臂）：80 行明细里 31 个函数中有 **22 个**是这一类
        #   （clang 基线只有 6/39）⇒ 直接把 DIVERGE 从 44 抬到 92，**掩盖了真实信号**。
        #   判据：仅当 **F 侧**因内存未映射停下、而 O 侧不是同一类停下 ⇒ 本组不可判（REFDEAD）。
        #   ★ 反向（O 侧早死、F 侧正常）**不**豁免 —— 那才是我们自己的信号。
        #   ★ 可关：`CGM_REFDEAD_OFF=1` 恢复旧口径（便于 A/B 与回归）。
        _EARLY = ('UC_ERR_READ_UNMAPPED', 'UC_ERR_WRITE_UNMAPPED', 'UC_ERR_FETCH_UNMAPPED')
        if (os.environ.get('CGM_REFDEAD_OFF') != '1' and sf in _EARLY and so not in _EARLY
                and not cap_f and not cap_o):
            rows.append((cname, 'refdead', rf['ret'], ro['ret'], rf['insns'], ro['insns'],
                         sf, so, [],
                         '参照侧(F)在 %s 早死（沙箱缺内存映射）⇒ 本组不可判；'
                         'F 侧的外部调用/访存指纹无观测力，不得据此判我们发散（§2.3）' % sf))
            _x('refdead', sf, so)
            continue
        # ★ DEADEQ-v2 组级豁免：见下方 `trace_diffs` **之后**的豁免块（第 154 轮移位）。
        #   ★ 第 153 轮第一版把豁免放在这里并 `continue`（跳过 trace_diffs），实测后果：
        #     594 个「早死但**无 diffs**」的 info 组被改判 deadeq ⇒ 146 个旧 PASS 函数
        #     被函数级分支拖进 DEADEQ（PASS 771→625，DEADEQ 0→147）。
        #     根因：**没算差异就豁免**，把"两侧轨迹一致"的组也标成"不可判"。
        #   ★ 根解原则（第 154 轮）：**豁免只能减少 DIVERGE，绝不能把 PASS 降级为不可判。**
        #   ★ 三个机械条件（fault 逐位相同 / 段外 / calls_ext 相同）与历史教训
        #     （DEADEQ-v1 视野对齐被推翻）写在下方豁免块，描述只允许有一处（纪律 69）。
        # ★★★ 2026-10-01：「两侧同类早死 ⇒ 本组不可比」这个假设**已被实测推翻**，不要重犯。
        #   我曾按 `min(insns)` 把两侧截断到同一指令数再比，结果（单变量 A/B，同一产物）：
        #       旧口径 PASS 759 ｜ DIVERGE **18**        新口径 PASS 623 ｜ DIVERGE **81**
        #   ⇒ 凭空造 63 个发散。**根因**：`insns` 是“已执行指令数”，两套编译产物的
        #     **指令密度不同** ⇒ 同指令数 ≠ 同程序点，按它对齐是**无效刻度**。
        #   ⇒ 本组**照旧按全量轨迹比对**；早死带来的深度差**不是**豁免理由。
        #   ★ 唯一有效的“是不是同一个死亡点”的判据 = **死亡现场**（未映射访问的 地址/宽度/读写），
        #     由 `run_func` 的 `fault` 字段提供（实测：`strtrim` F READ@0x0 vs O READ@0xffffffff ⇒ 真差异；
        #     `outputxy1` 两侧均 READ@0x0 ⇒ 同一个逻辑死亡点）。
        # ★ 观测差异的比对**只有一处实现**（`trace_diffs`）。
        diffs2, note, _ru, _fps = trace_diffs(
            rf, ro, bf, bo, fname, spec_private, fspans, void_fns,
            allow_terminal=True, cap_f=cap_f, cap_o=cap_o, cap_asym=cap_asym)
        diffs.extend(diffs2)
        # ★★★ 2026-10-07（第 160 轮）：**输出窗逐位判据**（FN_CORPUS 的 `out` 字段）。
        #   背景（FDCT32 取证闭环）：`data-reads` 分歧，但 buf/dest 的**最终字节逐位相同**
        #   ⇒ 访问模式（读几次/读多宽/常量是否折叠成立即数）是编译策略，不是语义。
        #   ★ 实现在 `_out_window_diffs`（纯函数，--self-test 可直接自证）；
        #     降级在**下方** DEADEQ-v2 豁免块之后做（`_apply_out_equiv`）。
        _out_diffs, out_ok, out_names_ok = _out_window_diffs(rf, ro, outs)
        diffs.extend(_out_diffs)
        # ★★★ 2026-10-01：死亡现场（未映射访问的 地址/宽度/读写）**只作证据，不作判据**。
        #   实测：把“现场不同”直接当成差异 ⇒ DIVERGE 18 → **91**。
        #   根因：死亡地址是**绝对地址**，而两套映像的**数据布局不同**（我方 0x4xxxxx）
        #   ⇒ 与 `insns` 同理：**绝对地址也不是可比刻度**。只能用来把已有的差异说得更清楚。
        fs_f, fs_o = rf.get('fault'), ro.get('fault')
        fs_txt = ('死亡现场 F=%s O=%s' % (_fault_str(fs_f), _fault_str(fs_o))
                  if (fs_f and fs_o) else '')
        # ★ 实测教训：这段**绝不能** `diffs.append` —— `inline_move.dims_are_mem_only()`
        #   是解析 `diffs` 文本判维度的，塞进中文说明会让整组"夹着别的维度"，
        #   于是 5 个已判"访存内联等价"的函数退回 DIVERGE（18→23）。
        #   ⇒ `diffs` = **判据承载体**，只放判据词汇；证据/说明一律进 `note`。
        if fs_txt:
            note = (note + ' ;; ' if note else '') + fs_txt
        if sf in _EARLY and so in _EARLY and rf['insns'] != ro['insns']:
            note = (note + ' ;; ' if note else '') + (
                '深度差(F=%d O=%d 条指令)仅是指令密度差，**不构成证据**'
                % (rf['insns'], ro['insns']))
        if _ru:
            ret_unjudged = True
        # ★★★ 2026-10-06（第 153 轮）：**共同早死等价（DEADEQ-v2）** —— 只在
        #   「两侧崩在**同一个野地址**」时豁免本组，**不含任何视野对齐**。
        #   ★ 为什么这是**根本**而不是补丁：UNDECIDABLE 7 个里的 5 个，两侧的死亡
        #     由**同一个未初始化的运行时全局**造成（取证：工厂 `mui_DisplayLine_t`
        #     反编译为 `*(int *)((&m_ui)[m_ui + 0x16] + 0x40)`；沙箱里 `m_ui` 是
        #     .data 初值 0 ⇒ 算出地址 0x40 ⇒ 读 0x40 崩。两侧**逐位同一个死亡点**）。
        #     ⇒ 对给定输入产生**同一个致命错误** ⇒ 语义等价。剩下的「深度差 / 死前
        #     多读几个全局」只发生在死前的合法执行里，由指令密度与代码布局决定
        #     （§0.46 已实测：这不是语义差异）。
        #   ★ 与被撤销的 DEADEQ-v1 的关键区别：v1 按 `min(insns)` **对齐视野**
        #     （无效刻度，凭空造 63 个发散）；v2 **不对齐**，只钉三个条件：
        #       ① 两侧 fault 三元组（访问码/地址/宽度）**逐位相同**；
        #       ② 死亡地址落在**两侧所有 PT_LOAD 之外**（⇒ 野指针，非数据布局差异）；
        #       ③ 两侧 `calls_ext` 序列相同（⇒ 执行的是同一段逻辑）。
        #   ★ 判别力（反例，实测保留为 DIVERGE）：`strtrim` F READ@0x0 vs
        #     O READ@0xffffffff ⇒ ①不满足 ⇒ 不豁免（这正是 §0.47 记录的「真差异」样本）。
        #   ★ 可关：`CGM_DEADEQ2_OFF=1` 恢复旧口径（A/B 与回归）。
        #   ★★★ 2026-10-06（第 154 轮）**位置修正**：豁免块必须在 `trace_diffs`
        #     **之后**，且**只豁免「本组原本会判 DIVERGE」的组**（`diffs` 非空）。
        #     第 153 轮第一版放在 `trace_diffs` 之前并 `continue` ⇒ 594 个「早死但
        #     无 diffs」的 info 组被改判 deadeq ⇒ 108 个「4 组全早死且无 diffs」的
        #     旧 PASS 函数被拖进 DEADEQ（PASS 771→625）⇒ 判据观测力被严重稀释。
        #     ★ 根解原则：**豁免只能减少 DIVERGE，绝不能把 PASS 降级为不可判。**
        if (diffs and os.environ.get('CGM_DEADEQ2_OFF') != '1'
                and sf in _EARLY and so in _EARLY
                and fs_f and fs_o
                and list(fs_f) == list(fs_o)
                and _fault_out_of_segments(fs_f[1], bf, bo)
                and list(rf.get('calls_ext') or []) == list(ro.get('calls_ext') or [])):
            rows.append((cname, 'deadeq', rf['ret'], ro['ret'], rf['insns'], ro['insns'],
                         sf, so, [],
                         (note + ' ;; ' if note else '')
                         + 'DEADEQ-v2 豁免（本组原判 DIVERGE）：两侧同类早死且死亡现场'
                           '逐位相同（%s）⇒ 同一个逻辑死亡点；被豁免的差异全来自死前'
                           '深度（指令密度），不构成语义差异（第 154 轮）'
                           % _fault_str(fs_f)))
            _x('deadeq', sf, so, diffs=list(diffs), note=note,
               wr_f=_fps['wr_f'], wr_o=_fps['wr_o'],
               rd_f=_fps['rd_f'], rd_o=_fps['rd_o'],
               ca_f=_fps['ca_f'], ca_o=_fps['ca_o'],
               fault_f=list(fs_f), fault_o=list(fs_o))
            continue
        # ★★★ 2026-10-07（第 160 轮）：**输出等价降级**（实现在 `_apply_out_equiv`，
        #   纯函数，--self-test 可自证）。前提：输出窗全部逐位相同（out_ok）
        #   且无 data-writes 差异。降级只动 data-reads，其余判据一律保留。
        diffs, note, _suppressed = _apply_out_equiv(diffs, note, out_ok, out_names_ok)
        if diffs:
            verdict = 'DIVERGE'
        _x('DIVERGE' if diffs else ('info' if note else 'ok'), sf, so,
           diffs=list(diffs), note=note, wr_f=_fps['wr_f'], wr_o=_fps['wr_o'],
           rd_f=_fps['rd_f'], rd_o=_fps['rd_o'], ca_f=_fps['ca_f'], ca_o=_fps['ca_o'],
           # ★ 被输出等价降级掉的 data-reads（审计用：--dump-rows 可见，不丢信息）
           suppressed=list(_suppressed),
           # ★ 返回值（机器可读；classify_signal 的 ABI 档用，第 154 轮）
           ret_f=rf['ret'], ret_o=ro['ret'],
           # ★ 死亡现场（机器可读；**不是判据**，见 compare() 注释）
           fault_f=list(fs_f) if fs_f else None, fault_o=list(fs_o) if fs_o else None)
        rows.append((cname, 'DIVERGE' if diffs else ('info' if note else 'ok'),
                     rf['ret'], ro['ret'], rf['insns'], ro['insns'], sf, so, diffs, note))
    # 若**没有任何一组**能给出判定（全是 trunc）⇒ 该函数整体不可判
    if rows and all(r[1] == 'trunc' for r in rows):
        verdict = 'TRUNC'
    # 若**没有任何一组**能给出判定（全是"参照侧早死"）⇒ 该函数整体不可判（REFDEAD）
    elif rows and all(r[1] == 'refdead' for r in rows):
        verdict = 'REFDEAD'
    # 若**没有任何一组**存在**未豁免**的差异、且**至少一组**被 DEADEQ-v2 豁免 ⇒
    #   该函数的 DIVERGE 被 DEADEQ-v2 完全豁免 ⇒ DEADEQ（第 154 轮修正）。
    #   ★ 为什么条件是「有 deadeq 组」而不是「所有组都早死」：DEADEQ-v2 的语义是
    #     「豁免本组**原本要判的 DIVERGE**」。一个所有组都早死但**无任何差异**的函数，
    #     旧口径本来就是 PASS（两侧轨迹一致）；把它改判不可判会稀释判据观测力
    #     （第 153 轮第一版实测教训：PASS 771→625）。
    #   ★ 混合情形（`outputxy1`：core/strs 组两侧早死且无差异 ⇒ ok/info；
    #     misc/zero 组有差异但被豁免 ⇒ deadeq）在此正确判为 DEADEQ。
    elif (rows and not any(r[1] == 'DIVERGE' for r in rows)
          and any(r[1] == 'deadeq' for r in rows)):
        verdict = 'DEADEQ'
    if out is not None:
        out['ret_unjudged'] = 1 if ret_unjudged else 0
        out['xrows'] = xr
    return verdict, rows


# --------------------------------------------------------------------------- #
def _zig():
    """多级解析 zig —— **委托给唯一解析器** `tools/zig_resolve.py`（纪律 69）。

    ★ 为什么改成薄封装：本函数原来各写一份解析链（且链尾还留了 Windows 默认路径兜底），
      在 Linux/CI 上曾返回 None（与 `ub_census.py` 同族缺陷）。解析规则只允许有一处。
    """
    try:
        import importlib.util as _ilu
        _sp = _ilu.spec_from_file_location(
            'zig_resolve', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zig_resolve.py'))
        _m = _ilu.module_from_spec(_sp)
        _sp.loader.exec_module(_m)
        _p, _ = _m.resolve_zig()
        return _p
    except Exception:
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


# ★★★ 2026-10-05（第 153 轮）：DIVERGE 的**信号强度**分档（只读不改）。
#   为什么需要：现存 DIVERGE 里混着「两侧在非法输入组**双双撞未映射内存而死**」的噪声，
#   差异只反映"死在哪个地址 / 跑了几步"，与语义无关（`strtrim` 是完整取证过的样板 ——
#   合法输入组两侧 ret 逐项相同，只有 `[zero]` 组发散且两侧都 READ_UNMAPPED 早死）。
#   把它们和真有语义差异的混进同一个 DIVERGE 数字 ⇒ 头条误导 + 诱导"给噪声改源码"。
#
#   ★ 本函数**只读不判**：输入 = `compare()` 已经产出的 xr 逐组明细，**不重跑、不改变
#     任何 verdict / stats / 判据指纹 / 棘轮台账**；只在汇总里多打一行派生分类。
#   ★ 规则（只用 xr 已有字段，不引入新判据）：
#       跑完组   = 两侧 stop 都是 `return`（都正常跑完）；
#       早死组   = 两侧 stop 都是 UC_ERR_*_UNMAPPED；
#       发散组   = 该组 kind == 'DIVERGE'（`diffs` 非空 —— 唯一的判据承载体）。
#     · 无跑完组                                  ⇒ UNDECIDABLE（没有任何一致证据，不许算 NOISE）
#     · 有跑完组，且**任一跑完组本身发散**          ⇒ REAL（合法输入下就有可观测差异 —— 这是要追的）
#     · 有跑完组，跑完组全一致，但有**非早死**的发散组 ⇒ REAL（发散形态不是"双双早死"，视野不对齐）
#     · 有跑完组，跑完组全一致，发散组**全是早死组**  ⇒ NOISE
#   ★ 判别力由 `--self-test` 的反例保证（见 selftest_classify）：把某个跑完组改成发散 ⇒ 必须判 REAL。
_EARLY_STOPS = ('UC_ERR_READ_UNMAPPED', 'UC_ERR_WRITE_UNMAPPED', 'UC_ERR_FETCH_UNMAPPED')


def _ret_value_is_artifact(v):
    """ret 值是否是「沙箱人造物」：落在 SCRATCH/STACK 区，或是明显非指针的小整数。

    ★ 用途（第 154 轮，classify_signal 的 ABI 档）：两侧 ret 都是人造物时，
      「ret 不同」只反映**按值返回结构体时的寄存器布局差异**（ABI），不是语义差异。
    ★ 小整数阈值 0x1000：真指针不会落在这个范围；两侧「类型类别」不同本身
      就是「两侧返回约定不同」的证据（如 F 侧把结构体放成 r0 小常数、O 侧放指针）。
    """
    if v is None:
        return False
    if SCRATCH <= v < SCRATCH + SCRATCH_SIZE:
        return True
    if STACK_BASE <= v < STACK_BASE + STACK_SIZE:
        return True
    return v < 0x1000


def _ret_only_and_sandbox(r):
    """该 DIVERGE 组的差异是否**只有 ret**、且两侧 ret 都是沙箱人造物。

    ★ ret 值优先取 xr 的结构化字段 `ret_f`/`ret_o`（batch 路径，权威）；
      缺失时从 `diffs` 文本正则解析 —— 该格式由 `trace_diffs()` 的
      `'ret F=0x%x O=0x%x'` 唯一定义，本函数**只解析、不复述规则**（纪律 69）。
    ★ diffs 为空 ⇒ 返回 False（不是 ret-only），避免 vacuous truth 吞掉真 REAL。
    """
    dd = [str(x) for x in (r.get('diffs') or [])]
    if not dd or not all(x.startswith('ret ') for x in dd):
        return False
    vf, vo = r.get('ret_f'), r.get('ret_o')
    if vf is None or vo is None:
        import re
        m = re.match(r'ret F=(0x[0-9a-fA-F]+) O=(0x[0-9a-fA-F]+)$', dd[0])
        if not m:
            return False
        vf, vo = int(m.group(1), 16), int(m.group(2), 16)
    return _ret_value_is_artifact(vf) and _ret_value_is_artifact(vo)


def classify_signal(rows):
    """rows = 一个函数的 xr 字典列表（字段 grp/kind/sf/so/diffs/ret_f/ret_o…）。
    → ('REAL'|'ABI'|'NOISE'|'UNDECIDABLE', 说明)。
    ★ ABI（第 154 轮）：跑完组的差异**只有 ret** 且两侧 ret 都是沙箱人造物 ⇒
      ABI 寄存器布局差异，**不是语义差异**（不改判据，只改派生分档）。"""
    if not rows:
        return 'UNDECIDABLE', '无逐组明细（compare 未产出 xr）'
    finished = [r for r in rows if r.get('sf') == 'return' and r.get('so') == 'return']
    if not finished:
        return 'UNDECIDABLE', '无跑完组（全是早死/单侧死/截断），视野不对齐，无法判语义'
    bad_finished_rows = [r for r in finished if r.get('kind') == 'DIVERGE']
    bad_finished = [r['grp'] for r in bad_finished_rows]
    if bad_finished:
        # ★ 2026-10-06（第 154 轮）：ret-only 差异 + 两侧 ret 都落在沙箱人造区
        #   ⇒ **ABI 档**（不是语义差异）。唯二样本：`stbtt__get_subrs`
        #   （F=`0x7d000300` O=`0x7e03fed0`）/ `stbtt__tesselate_curve`
        #   （F=`0x1` O=`0x7d000300`）—— 第 146–149 轮已证 `stbtt__buf` 按值传参
        #   的寄存器布局差异同理；两侧同一次编译、调用方与被调方约定自洽 ⇒ 真机无害。
        #   ★ 判别力（反例，必须保留 REAL）：一侧 ret 落在**产物段内**（真地址）
        #     ⇒ 可能是数据布局差异 ⇒ 仍 REAL。
        if all(_ret_only_and_sandbox(r) for r in bad_finished_rows):
            return 'ABI', ('跑完组 %s 的差异**只有 ret**，且两侧 ret 都落在沙箱人造区'
                           '（SCRATCH/STACK）或为小整数 ⇒ ABI 寄存器布局差异，非语义'
                           '（第 154 轮）') % ','.join(sorted(bad_finished))
        return 'REAL', '跑完组 %s 两侧观测不同（合法输入下即有差异）' % ','.join(sorted(bad_finished))
    diverging = [r for r in rows if r.get('kind') == 'DIVERGE']
    non_early = [r['grp'] for r in diverging
                 if not (r.get('sf') in _EARLY_STOPS and r.get('so') in _EARLY_STOPS)]
    if non_early:
        return 'REAL', '发散组 %s 不是双侧早死（形态差异，不是单纯死亡点不同）' % ','.join(sorted(non_early))
    if not diverging:
        return 'NOISE', '（其实没发散 —— 不该进分类器；batch 却把它列在 DIVERGE 里，需核对）'
    return 'NOISE', '跑完组 %d 个全部一致；发散组 %s 全是双侧早死（只在非法输入下发散，无语义含量）' % (
        len(finished), ','.join(sorted(r['grp'] for r in diverging)))


def partition_ok(stats, n_funcs):
    """判据分桶自洽：PASS+DIVERGE+TRUNC+SKIP+REFDEAD 必须等于本轮函数数。

    ★ 为什么必须独立成纯函数（2026-09-27）：汇总行曾把 INFO 并列成第四类，
      让读者以为四类可相加 —— 实际 INFO 是**重叠计数**（只在 ok/info 行上另计）。
      一旦某类被判据漏计，肉眼加总不会发现，报告会被当成"全绿"引用。
      现在：不一致 ⇒ fail-closed（退出码 1），且本函数有正/反例锚点自证。
    ★ 2026-09-29：新增第 5 桶 REFDEAD（参照侧库存早死 ⇒ 本组不可判，机械实现 §2.3）——
      它**必须**计入等式，否则新桶会被静默漏计（正是本函数存在的理由）。
    ★ 2026-10-01：第 6 桶 DEADEQ 曾按“两侧早死 ⇒ 共同视野前缀”上线，**已被实测推翻并撤销**
      （按 `min(insns)` 对齐在跨编译产物时无效，见 §0.46）。**不要再试这个方向。**
    """
    return (stats.get('PASS', 0) + stats.get('DIVERGE', 0)
            + stats.get('TRUNC', 0) + stats.get('SKIP', 0)
            + stats.get('REFDEAD', 0) + stats.get('DEADEQ', 0)) == n_funcs


def _strip_src(s):
    """去掉空行与**整行注释**，保留代码与 docstring（减少"只改注释就作废台账"的噪声）。"""
    out = []
    for ln in s.splitlines():
        t = ln.strip()
        if not t or t.startswith('#'):
            continue
        out.append(ln.rstrip())
    return '\n'.join(out)


def ruler_protocol_fingerprint():
    """判据口径指纹 = sha256( `compare()` + `partition_ok()` + **归因链** 的源码 + 常量/开关面 )。

    ★ 为什么是**源码 + 常量取值**而不是手填版本串（纪律 73）：
      手填的版本号会与代码脱节（本项目已 4 次栽在"硬编码与事实脱节"上）。
      取 `compare()` 的源码 ⇒ 任何改动**判据核心**的编辑都会改变指纹，
      台账随之失效并 fail-closed ⇒ 逼迫一次**显式、留痕**的重新记账。
    ★ 为什么把常量与开关名也纳入：它们同样是判据的一部分
      （改 `ESCALATE_FACTOR` 或关掉 `CGM_REFDEAD_OFF` 都会改分桶，必须让旧账作废）。
    ★★ 2026-09-30（§0.42）：把**归因链** `fp_key` / `norm_fp` / `canon_obj_name` 也纳入。
      病灶：改 `fp_key` 的配对规则**会改变 DIVERGE 集合**，但它不在指纹里 ⇒
      台账的旧账会被**静默沿用**（正是 §0.36 那类"改了尺子却还能对旧账"的洞）。
    """
    import hashlib
    import inspect
    parts = []
    for fn in (compare, partition_ok, fp_key, norm_fp, canon_obj_name):
        try:
            parts.append(_strip_src(inspect.getsource(fn)))
        except Exception as e:                                  # pragma: no cover
            parts.append('%s<source-unavailable:%s>' % (fn.__name__, type(e).__name__))
    for nm in RULER_CONSTANT_NAMES:
        parts.append('%s=%r' % (nm, globals().get(nm, '<缺失>')))
    for nm in RULER_PROTOCOL_SWITCHES:
        parts.append('%s=%r' % (nm, os.environ.get(nm, '<未设>')))
    parts.append('backend-switches=' + ','.join(RULER_BACKEND_SWITCH_NAMES))
    # ★ 2026-10-01：void 表是**判据的一部分**（它决定 ret 是否参与比对）⇒ 必须进指纹，
    #   否则"改了 void 名单"会**静默改变 DIVERGE 集合**而旧台账被沿用。
    try:
        import hashlib as _h2
        parts.append('void-src=' + _h2.sha256(
            '\n'.join(sorted(void_fns_from_sources())).encode('utf-8')).hexdigest()[:16])
    except Exception:                                          # pragma: no cover
        parts.append('void-src=<unavailable>')
    return hashlib.sha256('\n'.join(parts).encode('utf-8')).hexdigest()


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
    # ★★ 第 64 轮实测缺陷的回归锚点：**本轮新出现的不可判项必须进台账**
    #   旧实现 `diverging ∪ (old ∩ undecidable)` 里的 `∩ old` 会把"首次变成 TRUNC"
    #   的函数永远挡在台账外 —— 实测 `MP3InitDecoder`/`TestRun`/`WaitNMI`/
    #   `xmp3_AllocateBuffers` 连续多轮 TRUNC 而台账里一个都没有。
    c('台账语义  首次出现的不可判项也要进台账（不得藏在台账之外）',
      ledger_update([], [], {'w'})[0], ['w'])
    c('台账语义  新不可判项不得被算作"移除"',
      ledger_update(['w'], [], {'w'})[1], [])
    c('台账语义  发散 ∪ 不可判 都保留且去重',
      ledger_update(['a'], ['a'], {'a'})[0], ['a'])

    # 本项目真实函数：可执行性前提（不判等价，只证"两侧都能跑到停止"）
    if os.path.exists(FACTORY) and os.path.exists(OURS):
        BF, BO = Bin(FACTORY), Bin(OURS)
        c('前置：工厂 .symtab 可用（FUNC > 700）', len(BF.funcs) > 700, True)
        c('前置：两侧 PLT 都解析出名字', len(BF.plt_map) > 0 and len(BO.plt_map) > 0, True)
        # ★ 第 152 轮：PLT 名字解析换成了 GOT 槽配对；旧的位置配对留作**金丝雀**。
        #   两者若逐项不同 ⇒ 解析路径漂了 ⇒ calls_ext 的名字不可信 ⇒ 必须 fail-loud。
        #   （此前 `_r152_plt_got.py` 已在两份产物上证明二者逐项相同：工厂 105 / 我方 104 槽。）
        for tag, B in (('工厂', BF), ('我方', BO)):
            c('金丝雀  %s PLT：GOT配对 与 位置配对 **逐项相同**（%d 槽）' % (tag, len(B.plt_map)),
              B.plt_map == B._build_plt_positional()[0], True)
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
            # ★ 2026-10-20（R218）：**越界前驱归因**（locale_charset 假发散的根因）回归锚点。
            #   工厂纯私有 LOCAL `asso_values.9691`（sz=256）末尾后 1 字节是空串字面量
            #   （内容 0x00，另一个对象）。nearest_sym 的"最近前驱"语义会把越界地址
            #   误归因成 `asso_values+256`（偏移==size）⇒ 错按名字配对（LN 形）⇒
            #   与我方被 fspans 过滤的空串读（A 形）不对称 ⇒ 假发散「仅F 读 asso_values+256」。
            #   修复后：越界 ⇒ 退回 A 形，两侧对称，交给 fspans 过滤。
            _asvo = [(a, sz) for a, sz, n, ty in BF.sym_list
                     if n == 'asso_values.9691' and ty == 'STT_OBJECT']
            c('前提  工厂存在纯私有 LOCAL `asso_values.9691`（R218 越界前驱锚点的样本）',
              len(_asvo), 1)
            _ka, _ks = _asvo[0]
            c('正例  纯私有符号**区间内**读 ⇒ LN 形（按名字配对，私有副本合法）',
              fp_key(BF, (_ka, 4, 'R'), sb)[0][0], 'LN')
            c('反例  纯私有符号**越界**读（表尾后 1 字节空串）⇒ 退回 A 形（防 locale_charset 假发散）',
              fp_key(BF, (_ka + _ks, 1, 'R'), sb)[0][0], 'A')
            # ---- 回归锚点：把"非语义量"当判据的两类假发散（GAP 17.12）-------------
            vf, vmsg = void_fns_from_corpus()
            if vf:
                c('正例  void 集合从语料解析出来（AudioProcess 在其中）',
                  'AudioProcess' in vf, True)
                c('正例  void 集合非平凡（>50 个）', len(vf) > 50, True)
                # ★ 2026-10-01 新增：**上游源码**这条来源（实测缺口：csctx_rccurve_to）
                _vs = void_fns_from_sources()
                c('正例  上游源码 `static void stbtt__csctx_rccurve_to` 必须进 void 表',
                  'stbtt__csctx_rccurve_to' in _vs, True)
                c('正例  上游源码 void 表非平凡（实测 102 个 ⇒ 门槛 80）', len(_vs) > 80, True)
                c('反例  本表**只**含上游源码（不得混入 Ghidra 重建的 FUN_xxx）',
                  any(n.startswith('FUN_') for n in _vs), False)
                _vall = void_fns_all()
                c('正例  双源并集 ⊇ 语料表', set(vf) <= _vall, True)
                c('正例  双源并集 ⊇ 上游源码表', _vs <= _vall, True)
                c('正例  双源并集非平凡（实测 240 个 ⇒ 门槛 200）', len(_vall) > 200, True)
                # ★★ 2026-09-27 新增：Itanium demangle 查表（修 C++ 函数漏判 void）
                c('正例  _Z20inflate_blocks_reset… → 基础名',
                  itanium_base('_Z20inflate_blocks_resetP20inflate_blocks_stateP10z_stream_sPm'),
                  'inflate_blocks_reset')
                c('正例  _Z25unzlocal_DosDateToTmuDate… → 基础名',
                  itanium_base('_Z25unzlocal_DosDateToTmuDatemP8tm_unz_s'),
                  'unzlocal_DosDateToTmuDate')
                c('正例  嵌套名 _ZN6TUnzip4OpenEPvjj → 最内层节',
                  itanium_base('_ZN6TUnzip4OpenEPvjj'), 'Open')
                c('正例  非 mangled 名原样返回', itanium_base('AudioProcess'), 'AudioProcess')
                c('反例  基础名不在 void 集合 ⇒ 仍作判据（不得宽放）',
                  is_void_fn({'inflate_blocks_reset'}, '_Z8luferrorP6LUFILE'), False)
                c('正例  mangled 名经 demangle 命中 void 集合',
                  is_void_fn({'inflate_blocks_reset'},
                             '_Z20inflate_blocks_resetP20inflate_blocks_stateP10z_stream_sPm'),
                  True)
                c('正例  真 void 名两种形态都命中（AudioProcess）',
                  is_void_fn({'AudioProcess'}, 'AudioProcess'), True)
                c('反例  畸形 mangled 名不得抛出（且不得误命中）',
                  itanium_base('_Z9') in (None, '_Z9'), True)
                # ★ 只在一侧触上限时**不得**判 DIVERGE（否则把"跑得慢"当成"语义不同"）
                v_a, _ = compare(BF, BO, 'AudioProcess', 3000, void_fns=vf)
                c('反例  一侧触上限（3000 步）⇒ 必须 TRUNC，不得 DIVERGE', v_a, 'TRUNC')
                # ★ void 函数在足够预算下只差 r0 ⇒ 必须 PASS（r0 是残留值，不是输出）
                o2 = {}
                v_b, _ = compare(BF, BO, 'AudioProcess', 60000, void_fns=vf, out=o2)
                c('反例  预算足够时 void 函数只差 r0 ⇒ PASS（r0 不作判据）', v_b, 'PASS')
                c('正例  上述判定确实发生了"r0 未作判据"', o2.get('ret_unjudged'), 1)

        # ---- libc 模型接线（GAP 17.16）：外部调用不再一律返回 0 ----------------
        if 1:
            # ⓿ ★★★ 2026-10-05（第 142 轮）**接上 `libc_model.self_test()` 整条链**。
            #   为什么必须接（这是本轮自证抓到的**真缺陷**，不是形式主义）：
            #     `libc_model.self_test()` 此前**没有任何调用方** —— `diff_exec --self-test`
            #     只**重写**了其中几条（直接引用 `libc_model.PTR_RETURNING` 之类），
            #     于是模型侧 108 条自证**一条都没跑**，新加的契约型锚点也只写在死链上
            #     ⇒ 典型的「自证形同虚设 = 假绿」。
            #   ⇒ 这里**整条调用**（不重述、不摘抄），元组从 `(label,got,want)`
            #     折算成本文件的 `(tag,got,want,ok)`。标签加前缀便于一眼看出来源。
            for _lb, _g, _w in libc_model.self_test():
                c('libc模型自证· ' + _lb, _g, _w)
            # ① 跨模块一致性：CALL_MECH 里的 ctype 名必须是 libc_model 真正实现的
            pred_names = {n for n, w in libc_model.CTYPE_PREDICATES.items() if w}
            tbl_names = {'__ctype_b_loc', '__ctype_toupper_loc', '__ctype_tolower_loc'}
            map_names = {'toupper', 'tolower'}
            mech_ctype = {n for n, tag in CALL_MECH.items() if tag.startswith('ctype:')}
            c('正例  CALL_MECH 的 ctype 项全部在 libc_model 有实现（无悬空归一）',
              mech_ctype <= (pred_names | tbl_names | map_names), True)
            c('正例  ctype 族非平凡（>=12 个谓词）', len(pred_names) >= 12, True)
            c('正例  指针返回型集合非平凡（>=15 个）', len(libc_model.PTR_RETURNING) >= 15, True)
            # ② 端到端机制锚点：`strupr` 曾因"指针返回型被兜底成 0"而 READ_UNMAPPED
            #    ★ 锚点必须挑**有效输入**那一组：`zero`/`misc` 组参数是 NULL，
            #      两侧**同样**读崩 —— 那是真实行为一致，不是缺陷（自证要能区分这两件事）。
            o3 = {}
            v_s, rows_s = compare(BF, BO, 'strupr', 3000, void_fns=vf, out=o3)
            rs = [r for r in rows_s if r[0] == 'strs']
            c('前提  `strs` 组存在（有效字符串输入）', len(rs), 1)
            c('反例  有效字符串下我方侧不得再 READ_UNMAPPED（libc 模型缺位造成的假发散）',
              'UC_ERR_READ_UNMAPPED' in (rs[0][6], rs[0][7]), False)
            # ★★ 2026-10-04（第 130 轮）**锚点更新：判据从「留痕」改为「已消解」**。
            #   旧锚点要求 `strupr` 判为 `info`（无差异但有留痕，且留痕里同时出现
            #   `islower` 与 `__ctype_b_loc`）—— 那描述的是**调用名差异被机制等价归一、
            #   留痕待人工复核**的中间状态。
            #   实测（第 130 轮，云开发权威基线）：`strupr` 判为 **`ok`**，即两侧
            #   连留痕都没有 ⇒ `islower` / `__ctype_b_loc` 的调用序列差异**已彻底消解**
            #   （`libc_model` 的 ctype 族建模把它归一成了同一机制，且不留残余说明）。
            #   ⇒ 旧锚点是**过期判据**（instrument drift），不是代码缺陷；
            #     若继续要求 `info` 就会把「更强的结果」误判成「仪器坏了」。
            #   新锚点按位宽无关的**方向性**断言：只可能 ok/info（绝不能 DIVERGE），
            #   并在 note 非空时**仍要求**它同时含两侧调用名（保留可复核性）。
            c('正例  `strupr` 非 DIVERGE（调用名机制等价已消解：ok 或 info）',
              rs[0][1] in ('ok', 'info'), True)
            c('正例  若仍有留痕，则必须同时打印两侧原始调用名（可复核，不是抹掉）',
              (rs[0][9] in (None, '')) or
              (('islower' in (rs[0][9] or '')) and ('__ctype_b_loc' in (rs[0][9] or ''))), True)
            c('反例  NULL 输入时两侧**同样**读崩 ⇒ 不得被判成发散',
              v_s, 'PASS')

        # ---- 别名唯一真源 + 写粒度归一（GAP 17.17）------------------------------
        if 1:
            c('正例  CALL_ALIAS 与 libc_model.ALIASES 是同一份（两份硬编清单必然漂移）',
              CALL_ALIAS == libc_model.ALIASES, True)
            c('正例  `_Znwj`（C++ operator new）在别名表里（漏掉它会造 18 个假发散）',
              CALL_ALIAS.get('_Znwj'), 'malloc')
            # 写合并：两个相邻 4B 写 == 一个 8B 写
            c('正例  相邻 4B 写被合并为 8B 覆盖',
              coalesce_writes([(0x1000, 4, 'W'), (0x1004, 4, 'W')]), [(0x1000, 8, 'W')])
            c('反例  不相邻的写**不得**被合并',
              coalesce_writes([(0x1000, 4, 'W'), (0x2000, 4, 'W')]),
              [(0x1000, 4, 'W'), (0x2000, 4, 'W')])
            c('反例  读不得被**写合并**规则吸收（读的粒度差异由 read_width_only 单独判定）',
              coalesce_writes([(0x1000, 1, 'R'), (0x1001, 1, 'R')]),
              [(0x1000, 1, 'R'), (0x1001, 1, 'R')])
            c('反例  读写混合不得跨方向合并',
              coalesce_writes([(0x1000, 4, 'R'), (0x1004, 4, 'W')]),
              [(0x1000, 4, 'R'), (0x1004, 4, 'W')])
            # 访存粒度（GAP 17.18）：同址同对象、仅宽度不同 ⇒ 粒度差异；地址集合不同 ⇒ 真差异
            A4 = [('A', 0x3BC40C, 4, 'R')]
            A1 = [('A', 0x3BC40C, 1, 'R')]
            c('正例  同址同对象、仅宽度不同 ⇒ 判为"粒度差异"',
              read_width_only(A4, A1)[0], True)
            c('反例  地址集合不同（少读一个对象）⇒ 不得判为粒度差异',
              read_width_only([('A', 0x10, 4, 'R'), ('A', 0x20, 4, 'R')],
                              [('A', 0x10, 4, 'R')])[0], False)
            # ★ 2026-09-28 更正标签：本锚点实际比较的是 **0x10 vs 0x3BC40C**
            #   ⇒ 它测的是"地址集合不同"，之前写成"次数不同"是**标签与内容不符**，
            #   导致 count 这条语义长期没有锚点覆盖（真覆盖见下面 LN 的两条）。
            c('反例  地址集合不同（两次读 vs 另一地址一次读）⇒ 不得判为粒度差异',
              read_width_only([('A', 0x10, 4, 'R'), ('A', 0x10, 4, 'R')], A4)[0], False)
            c('反例  同址同宽但次数不同（2 vs 1）⇒ 不得判为粒度差异',
              read_width_only([('A', 0x10, 4, 'R'), ('A', 0x10, 4, 'R')],
                              [('A', 0x10, 4, 'R')])[0], False)
            # ★★ 2026-09-28 新增：**'LN'（具名全局）形式的锚点** —— 旧锚点全是 'A' 形，
            #   正是这个形态盲区让"取错宽度下标"的 bug 活了很久（实测 mui_search/mui_setting）。
            c('正例  LN 同对象同偏移、仅宽度不同（4 vs 1）⇒ 粒度差异',
              read_width_only([('LN', 'Flag', 0, 4, 'R')], [('LN', 'Flag', 0, 1, 'R')])[0], True)
            c('反例  LN 同对象**不同偏移**（一侧少读）⇒ 不得判粒度',
              read_width_only([('LN', 'G', 0, 4, 'R'), ('LN', 'G', 4, 4, 'R')],
                              [('LN', 'G', 0, 4, 'R')])[0], False)
            c('反例  LN 同偏移但读次数不同（2 vs 1）⇒ 不得判粒度',
              read_width_only([('LN', 'G', 0, 4, 'R'), ('LN', 'G', 0, 4, 'R')],
                              [('LN', 'G', 0, 4, 'R')])[0], False)
            c('反例  LN 对象不同 ⇒ 不得判粒度',
              read_width_only([('LN', 'A', 0, 4, 'R')], [('LN', 'B', 0, 4, 'R')])[0], False)
            c('反例  读写方向不同 ⇒ 不得判为粒度差异',
              read_width_only([('A', 0x10, 4, 'R')], [('A', 0x10, 4, 'W')])[0], False)
            # ★★★ 2026-10-07（第 160 轮）：**输出窗逐位判据**（`_out_window_diffs` +
            #   `_apply_out_equiv`，两个纯函数）。先离线自证判据本身，再端到端跑 FDCT32。
            # ★ R289：契约升级为 5 元组（第 5 项 = pre 前置钩子）。以下四条同步更新，
            #   并保留"5 元组的第 5 项必须被透传（不是被忽略）"与"6 元组仍非法"两个方向。
            c('正例  `_unpack_cps` 2 元组 → (名, args, None, None, None)',
              list(_unpack_cps([('a', [1])])),
              [('a', [1], None, None, None)])
            c('正例  `_unpack_cps` 3 元组 → seed 透传、out/pre=None',
              list(_unpack_cps([('a', [1], [(2, b'x')])])),
              [('a', [1], [(2, b'x')], None, None)])
            c('正例  `_unpack_cps` 4 元组 → out_windows 透传、pre=None',
              list(_unpack_cps([('a', [1], None, [('w', 2, 4)])])),
              [('a', [1], None, [('w', 2, 4)], None)])
            # ★ R290：克隆后缀配对归一（双向）
            c('正例  _pair_key 剥工厂点号形 .isra.16',
              _pair_key('stbtt__rasterize_sorted_edges.isra.16'),
              'stbtt__rasterize_sorted_edges')
            c('正例  _pair_key 剥我方下划线形 _isra_19',
              _pair_key('mui_outputxy_length_isra_19'),
              'mui_outputxy_length')
            c('正例  _pair_key 幂等（无后缀名不变）',
              _pair_key('stbtt_InitFont'), 'stbtt_InitFont')

            class _FB(object):
                def __init__(self, d):
                    self.funcs = {k: (0, 1) for k in d}
            _pr, _am = build_pairs(_FB({'A.isra.1': 1, 'B': 1}), _FB({'A_isra_1': 1, 'B': 1}))
            c('正例  build_pairs 克隆名唯一 ⇒ 跨名配对',
              _pr.get('A.isra.1'), ('A.isra.1', 'A_isra_1'))
            _pr2, _am2 = build_pairs(_FB({'C.isra.1': 1}), _FB({'C': 1, 'C_isra_1': 1}))
            c('反例  build_pairs 我方同键多候选 ⇒ 歧义不配对',
              (('C.isra.1' in _pr2), len(_am2)), (False, 1))
            c('正例  `_unpack_cps` 5 元组 → pre 必须被透传（R289 新增）',
              list(_unpack_cps([('a', [1], None, None, [('initfont', [0])])])),
              [('a', [1], None, None, [('initfont', [0])])])
            try:
                list(_unpack_cps([('a', 1, 2, 3, 4, 5)]))
                _bad5 = 'no-raise'
            except ValueError:
                _bad5 = 'raised'
            c('反例  `_unpack_cps` 6 元组必须报错（不得静默截断）', _bad5, 'raised')
            _OW = [('w', 0x1000, 8)]
            _same = b'\x01\x02\x03\x04\x05\x06\x07\x08'
            c('正例  无输出窗 ⇒ 不比、不降级（[], False, []）',
              _out_window_diffs({}, {}, []), ([], False, []))
            c('正例  窗口逐位相同 ⇒ 无差异、out_ok=True',
              _out_window_diffs({'out_bytes': {'w': _same}},
                                {'out_bytes': {'w': _same}}, _OW),
              ([], True, ['w[0x1000+0x8]']))
            c('反例  窗口内容不同 ⇒ 报 data-out 且 out_ok=False',
              _out_window_diffs({'out_bytes': {'w': _same}},
                                {'out_bytes': {'w': b'\x00' * 8}}, _OW)[1], False)
            c('反例  窗口读不到（None）⇒ 报「不可读」且 out_ok=False（fail-loud）',
              _out_window_diffs({'out_bytes': {'w': None}},
                                {'out_bytes': {'w': _same}}, _OW),
              (['data-out w 不可读（窗口落在段外？）'], False, []))
            c('反例  多窗口中只要有一个不同 ⇒ out_ok=False（必须**全部**相同）',
              _out_window_diffs({'out_bytes': {'a': b'x', 'b': b'y'}},
                                {'out_bytes': {'a': b'x', 'b': b'z'}},
                                [('a', 0, 1), ('b', 1, 1)])[1], False)
            c('正例  out_ok 且仅 data-reads 差异 ⇒ 降级（diffs 清空、note 留痕）',
              _apply_out_equiv(['data-reads 仅F=[x]'], '', True, ['w[0x1000+0x8]'])[0], [])
            c('正例  降级后 note 必须含「输出等价」（可审计，不是静默放过）',
              '输出等价' in _apply_out_equiv(['data-reads x'], '', True, ['w'])[1], True)
            c('反例  out_ok 但有 data-writes 差异 ⇒ **不得**降级（窗口可能不完备）',
              _apply_out_equiv(['data-reads x', 'data-writes y'], '', True, ['w'])[0],
              ['data-reads x', 'data-writes y'])
            c('反例  out_ok=False ⇒ 任何差异都不得降级',
              _apply_out_equiv(['data-reads x'], '', False, [])[0], ['data-reads x'])
            c('正例  降级只动 data-reads：calls_ext 等其它判据**必须保留**',
              _apply_out_equiv(['data-reads x', 'calls_ext y'], '', True, ['w'])[0],
              ['calls_ext y'])
            c('正例  被降级的 data-reads 必须被返回（审计不丢信息）',
              _apply_out_equiv(['data-reads x', 'calls_ext y'], '', True, ['w'])[2],
              ['data-reads x'])
            # ★ 端到端：真实 FDCT32（两侧真实 ELF，4 组合法输入）。
            #   依据（第 160 轮云工作区取证）：buf 128B + dest 4096B 逐位相同
            #   ⇒ data-reads 差异（dcttab 折叠/buf reload/LDM 合并）被证明不影响输出。
            _fv, _frows = compare(BF, BO, 'xmp3_FDCT32', steps=20000,
                                  corpus=FN_CORPUS['xmp3_FDCT32'],
                                  void_fns=void_fns_all())
            c('正例  FDCT32 输出等价 ⇒ 整体 PASS（不再判 DIVERGE）', _fv, 'PASS')
            c('正例  每一组都留痕「输出等价」',
              all('输出等价' in (r[9] or '') for r in _frows if r[1] in ('ok', 'info')), True)
            c('正例  四组全部跑到 return（观测窗有效，不是双双早死的假 PASS）',
              all(r[6] == 'return' and r[7] == 'return' for r in _frows), True)
            # 分桶自洽（2026-09-27，P0-B）：真实头条数字 661/75/5/0 = 741
            c('正例  分桶自洽：661+75+5+0+0 == 741',
              partition_ok({'PASS': 661, 'DIVERGE': 75, 'TRUNC': 5, 'SKIP': 0, 'REFDEAD': 0}, 741), True)
            c('反例  少算一个函数（741 vs 746）⇒ 必须判为不自洽',
              partition_ok({'PASS': 661, 'DIVERGE': 75, 'TRUNC': 5, 'SKIP': 0, 'REFDEAD': 0}, 746), False)
            c('反例  把 INFO 当加数（661+75+39+5=780≠741）⇒ 必须判为不自洽',
              partition_ok({'PASS': 661 + 39, 'DIVERGE': 75, 'TRUNC': 5, 'SKIP': 0, 'REFDEAD': 0},
                           741), False)
            # ★ 2026-09-29 新增锚点：REFDEAD 桶**必须**计入等式（否则新桶被静默漏计）
            c('反例  REFDEAD 漏计（661+75+5+0=741，另有 20 个 REFDEAD）⇒ 必须判为不自洽',
              partition_ok({'PASS': 661, 'DIVERGE': 75, 'TRUNC': 5, 'SKIP': 0}, 761), False)
            c('正例  REFDEAD 计入后自洽：661+75+5+0+20 == 761',
              partition_ok({'PASS': 661, 'DIVERGE': 75, 'TRUNC': 5, 'SKIP': 0, 'REFDEAD': 20}, 761), True)
            # ★ 2026-10-01 新增锚点：DEADEQ 桶**必须**计入等式（否则“不可判”被静默漏计）
            # ★ 2026-10-06（第 153 轮）：DEADEQ 桶**重新接线**（v2 = 两侧同一个野地址早死）。
            #   分桶等式**只认列出的桶** ⇒ 多给一个桶就是不自洽。
            c('正例  DEADEQ 计入后自洽：661+75+5+0+0+12 == 753',
              partition_ok({'PASS': 661, 'DIVERGE': 75, 'TRUNC': 5, 'SKIP': 0,
                            'REFDEAD': 0, 'DEADEQ': 12}, 753), True)
            c('反例  多出一个未接线的桶（BOGUS=12）⇒ 必须判为不自洽',
              partition_ok({'PASS': 661, 'DIVERGE': 75, 'TRUNC': 5, 'SKIP': 0,
                            'REFDEAD': 0, 'BOGUS': 12}, 753), False)

        # ---- ★ 2026-10-05（第 153 轮）：classify_signal 判别力（正反对照）----------
        #   规则只允许有一处（纪律 69）⇒ `diverge_classify.py` 的旧实现作废，统一调这里。
        if 1:
            def _xr(grp, kind, sf='return', so='return', diffs=None, ret_f=None, ret_o=None):
                return {'fn': 't', 'grp': grp, 'kind': kind, 'sf': sf, 'so': so,
                        'diffs': diffs or [], 'ret_f': ret_f, 'ret_o': ret_o}

            ok = [_xr('zero', 'ok', 'UC_ERR_READ_UNMAPPED', 'UC_ERR_READ_UNMAPPED'),
                  _xr('strs', 'DIVERGE', 'UC_ERR_READ_UNMAPPED', 'UC_ERR_WRITE_UNMAPPED'),
                  _xr('core', 'ok'), _xr('misc', 'info')]
            c('正例  classify  跑完组全一致 + 发散组都是双侧早死 ⇒ NOISE',
              classify_signal(ok)[0], 'NOISE')
            _bad = list(ok); _bad[2] = _xr('core', 'DIVERGE')
            c('反例  classify  跑完组里就有差异 ⇒ **必须 REAL**（NOISE 不许吞真信号）',
              classify_signal(_bad)[0], 'REAL')
            _bad2 = list(ok); _bad2[1] = _xr('strs', 'DIVERGE', 'return',
                                             'UC_ERR_READ_UNMAPPED')
            c('反例  classify  发散组是「单侧死」（视野不对齐）⇒ REAL',
              classify_signal(_bad2)[0], 'REAL')
            # ★ 2026-10-06（第 154 轮）：ABI 档 —— ret-only + 两侧 ret 都是沙箱人造物
            _abi = list(ok)
            _abi[2] = _xr('core', 'DIVERGE', diffs=['ret F=0x7d000300 O=0x7e03fed0'],
                          ret_f=0x7d000300, ret_o=0x7e03fed0)
            c('正例  classify  ret-only 且两侧 ret 都在沙箱区 ⇒ ABI（非语义差异）',
              classify_signal(_abi)[0], 'ABI')
            _abi2 = list(ok)
            _abi2[2] = _xr('core', 'DIVERGE', diffs=['ret F=0x1 O=0x7d000100'],
                           ret_f=0x1, ret_o=0x7d000100)
            c('正例  classify  一侧 ret 是小整数、一侧沙箱区 ⇒ ABI（类型类别不同）',
              classify_signal(_abi2)[0], 'ABI')
            _real_ret = list(ok)
            _real_ret[2] = _xr('core', 'DIVERGE', diffs=['ret F=0x3e0000 O=0x7d000300'],
                               ret_f=0x3e0000, ret_o=0x7d000300)
            c('反例  classify  一侧 ret 落在**产物段内**（真地址）⇒ 仍 REAL',
              classify_signal(_real_ret)[0], 'REAL')
            _real_mixed = list(ok)
            _real_mixed[2] = _xr('core', 'DIVERGE',
                                 diffs=["data-reads 仅F=[] 仅O=['0x003cfa94:4:R ×1']"])
            c('反例  classify  差异含 data-reads（不只是 ret）⇒ 仍 REAL',
              classify_signal(_real_mixed)[0], 'REAL')
            _nod = [_xr(g, 'DIVERGE', 'UC_ERR_READ_UNMAPPED', 'UC_ERR_READ_UNMAPPED')
                    for g in ('zero', 'strs', 'core', 'misc')]
            c('反例  classify  无跑完组 ⇒ UNDECIDABLE（无一致证据，不许算 NOISE）',
              classify_signal(_nod)[0], 'UNDECIDABLE')
            c('反例  classify  空明细 ⇒ UNDECIDABLE（不许默认 NOISE）',
              classify_signal([])[0], 'UNDECIDABLE')
            c('正例  classify  跑完组全一致且无发散 ⇒ NOISE 且说明含「不该进分类器」',
              '没发散' in classify_signal([_xr('zero', 'ok'), _xr('strs', 'ok')])[1], True)

        # ---- ★ 2026-09-29 新增：台账**口径指纹**（防"尺子换了却被读成 ★新增发散"）----
        if 1:
            _mm = read_ledger_meta('# steps=3000\n# escalate=60000\n# ruler=deadbeef\n'
                                   '# ours=ac6bb562a0d20561\n'
                                   '# rebaseline: 行为尺升 v2（新增 REFDEAD 桶）\nfoo\nbar\n')
            c('台账元信息  解析 ruler', _mm['ruler'], 'deadbeef')
            c('台账元信息  解析 ours（被测产物 sha）', _mm['ours'], 'ac6bb562a0d20561')
            c('台账元信息  解析 rebaseline 原因（留痕）', _mm['rebaseline'],
              '行为尺升 v2（新增 REFDEAD 桶）')
            c('反例  旧台账（只记 steps/escalate）⇒ ruler 必须为 None（⇒ 判为口径不一致）',
              read_ledger_meta('# steps=3000\n# escalate=60000\nfoo\n')['ruler'], None)
            c('正例  台账正文不被元信息干扰（read_ledger_text 语义零回归）',
              read_ledger_text('# steps=3000\n# ruler=deadbeef\nfoo\nbar\n')[2], ['foo', 'bar'])
            _f1 = ruler_protocol_fingerprint()
            _f2 = ruler_protocol_fingerprint()
            c('口径指纹  可复现（同一次运行两次调用相同）', _f1 == _f2, True)
            c('口径指纹  形态 = 64 位小写 hex', bool(re.fullmatch(r'[0-9a-f]{64}', _f1)), True)
            _saved = ESCALATE_FACTOR
            globals()['ESCALATE_FACTOR'] = _saved + 1
            _f3 = ruler_protocol_fingerprint()
            globals()['ESCALATE_FACTOR'] = _saved
            c('反例  改判据常量（ESCALATE_FACTOR）⇒ 口径指纹**必须**变化'
              '（否则旧账会被静默沿用）', _f3 != _f1, True)
            c('正例  恢复常量后指纹回到原值（证明变化确实来自该常量）',
              ruler_protocol_fingerprint() == _f1, True)
            # ★ 开关分两类：判据开关改**值**必须变指纹；执行后端开关**不得**影响指纹
            _saved_env = {k: os.environ.get(k) for k in
                          (RULER_PROTOCOL_SWITCHES + RULER_BACKEND_SWITCH_NAMES)}
            try:
                os.environ['CGM_MACHINE_REUSE'] = '1'
                c('反例  执行后端开关（CGM_MACHINE_REUSE）**不得**影响口径指纹'
                  '（否则"本地带 reuse / CI 不带"这种无关差异会判废台账）',
                  ruler_protocol_fingerprint() == _f1, True)
                os.environ['CGM_REFDEAD_OFF'] = '1'
                c('反例  判据开关改生效值（CGM_REFDEAD_OFF=1）**必须**改变口径指纹'
                  '（它取消 REFDEAD 桶 ⇒ DIVERGE 集合随之改变）',
                  ruler_protocol_fingerprint() != _f1, True)
            finally:
                for k, v in _saved_env.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            c('正例  恢复开关后指纹回到原值', ruler_protocol_fingerprint() == _f1, True)
    # ★★ 2026-09-30（§0.42）：块作用域 static 的**规范名**归一（真缺陷的回归锚点）。
    c('规范名 GCC 形  name.NNNN → name', canon_obj_name('asso_values.9691'), 'asso_values')
    c('规范名 clang 形 func.name → name', canon_obj_name('aliases_hash.asso_values'), 'asso_values')
    c('规范名 两套工具链**归一到同一个键**（这才是修的东西）',
      canon_obj_name('asso_values.9691') == canon_obj_name('aliases_hash.asso_values'), True)
    c('反例 普通名字不得被改（`_mxml_key` / `m_ui` 不受影响）',
      (canon_obj_name('_mxml_key'), canon_obj_name('m_ui')), ('_mxml_key', 'm_ui'))
    # ★ 这条是**已知代价**的显式锚点，不是"正例"：不同 TU 的同名块作用域 static 会归到
    #   同一个规范名。正因如此，"唯一性"必须在**规范名**上判定（两个 ⇒ 不判私有 ⇒
    #   退回按地址配对）——方向保守，不会洗白。工厂侧 `asso_values` 只有 1 份（规范名计数 1）
    #   才使它成为"按名字配对"的对象。
    c('★ 已知代价 不同 TU 的同名块作用域 static 归到同一规范名（故唯一性须在规范名上判）',
      canon_obj_name('iso8859_1.asso_values') == canon_obj_name('iso8859_2.asso_values'), True)
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
    ap.add_argument('--from-state', dest='from_state', default=None,
                    help='G1：真实状态快照（由 guest shim 的 CGM_STATE_DUMP 产出）；'
                         '两侧先写入同一份数据区字节再执行')
    ap.add_argument('--dump-rows', dest='dump_rows',
                    help='把**逐组机器可读明细**（含两侧归一化后的访存/调用指纹）写成 JSON。'
                         '★ 归类（差异类别收敛）必须用它，不得用报告里的"前 80"截断摘要。')
    ap.add_argument('--ledger', help='发散棘轮台账：只允许减少，不允许新增')
    ap.add_argument('--update-ledger', action='store_true', help='用当前发散集重写台账')
    ap.add_argument('--rebaseline', action='store_true',
                    help='★ 显式重新记账：口径（ruler 指纹）变更后必须走这条路；'
                         '新台账会记下 ruler / 被测产物 sha / 原因（配 --reason）')
    ap.add_argument('--reason', default=None,
                    help='--rebaseline 的原因（写进台账头部，留痕；强烈建议填写）')
    ap.add_argument('--self-test', action='store_true')
    # ★ 2026-10-01 新增：**只跑指定语料组**（只读测量，用于把"NULL 组上的指令顺序伪影"
    #   与"真语义差异"分开）。默认 = 全部三组，**默认口径与判据指纹都不受影响**。
    #   ★ 安全约束：子集运行**禁止**碰棘轮台账（否则会用缩小后的分母重写台账 ⇒ 静默变弱）。
    ap.add_argument('--groups', default=None,
                    help='只跑指定语料组（逗号分隔，如 strs）；只读测量，不得与 --ledger 同用')
    ap.add_argument('--ours', help='被测产物（默认 build/rkgame.rebuilt.elf）；'
                                   '用于单变量 A/B：同一把尺子量不同工具链/不同 flags 的产物')
    ap.add_argument('--factory', help='对照产物（默认 golden/factory.rkgame.bin）')

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

    fac = a.factory or FACTORY
    ours = a.ours or OURS
    # ★ 语料子集（只读测量）：`--groups strs` 之类。默认 = 全部三组，口径不变。
    cps = list(CORPUS)
    if a.groups:
        want = {g.strip() for g in a.groups.split(',') if g.strip()}
        # ★ 第 160 轮：若该函数有特设语料（FN_CORPUS），组名以它的为准。
        known = {c[0] for c in CORPUS}
        if a.fn and a.fn in FN_CORPUS:
            known = {c[0] for c in FN_CORPUS[a.fn]}
        unknown = want - known
        if unknown:
            sys.stderr.write('★★ --groups 含未知语料组 %s（已知：%s）\n'
                             % (sorted(unknown), sorted(known)))
            return 9
        cps = [c for c in CORPUS if c[0] in want]
        if a.ledger or a.update_ledger:
            sys.stderr.write('★★ 子集运行（--groups %s）**禁止**与台账同用：\n'
                             '   用缩小后的分母重写棘轮台账会让台账**静默变弱**。\n' % a.groups)
            return 9
        sys.stderr.write('★ 只读测量：语料子集 = %s（**不写台账**）\n' % [c[0] for c in cps])
    for p in (fac, ours):
        if not os.path.exists(p):
            sys.stderr.write('缺 %s\n' % p)
            return 11
    # ★ 报告必须能回溯到**具体产物**：把两侧 sha256 打在最前（GAP 17.23 纪律）。
    _sha = {p: hashlib.sha256(open(p, 'rb').read()).hexdigest() for p in (fac, ours)}
    sys.stderr.write('  对照 = %s\n    sha256=%s\n' % (fac, _sha[fac]))
    sys.stderr.write('  被测 = %s\n    sha256=%s\n' % (ours, _sha[ours]))
    BF, BO = Bin(fac), Bin(ours)
    # ★ R294：加载状态快照（fail-loud：magic/尺寸不符立即报错，不静默降级成"没状态"）
    global _STATE_BLOB
    if getattr(a, 'from_state', None):
        _raw = open(a.from_state, 'rb').read()
        if len(_raw) < 16 or _raw[:8] != b'CGMST001':
            sys.stderr.write('★★ --from-state 文件头不合法（需 CGMST001）：%s\n' % a.from_state)
            return 12
        _lo = int.from_bytes(_raw[8:12], 'little')
        _hi = int.from_bytes(_raw[12:16], 'little')
        _body = _raw[16:]
        if _hi <= _lo or len(_body) != _hi - _lo:
            sys.stderr.write('★★ --from-state 尺寸不符：lo=0x%x hi=0x%x body=%d\n'
                             % (_lo, _hi, len(_body)))
            return 12
        _STATE_BLOB = (_lo, _body)
        sys.stderr.write('  状态快照 = %s  [0x%08x,0x%08x) %d B\n'
                         % (a.from_state, _lo, _hi, len(_body)))
    # ★ R290：配对归一（含克隆后缀）；`_PAIRS` 供 --list/--batch 共用
    _PAIRS, _AMBIG = build_pairs(BF, BO)
    common = sorted(_PAIRS)

    # ★★ 台账口径门禁：**跑之前**就判（口径不一致 ⇒ 直接 exit 3，不白跑一轮）。
    _cur_ruler = ruler_protocol_fingerprint()
    _gok, _glines = ledger_protocol_guard(a.ledger, _cur_ruler,
                                          bool(a.update_ledger or a.rebaseline), a.steps)
    if not _gok:
        _txt = '\n'.join(['=' * 70, '差分执行对拍（工厂 vs 重建产物）', '=' * 70] + _glines)
        print(_txt)
        if a.out:
            with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(_txt + '\n')
        return 3

    if a.list:
        print('  两侧共有函数 %d 个（工厂 %d / 我们 %d）；数据区 F=%s O=%s'
              % (len(common), len(BF.funcs), len(BO.funcs), BF.dregion, BO.dregion))
        for n in common[:a.limit or 30]:
            _on = _PAIRS[n][1]
            print('   %-46s F@0x%08x(%d) O@0x%08x(%d)%s'
                  % (n, BF.funcs[n][0], BF.funcs[n][1], BO.funcs[_on][0], BO.funcs[_on][1],
                     ('' if _on == n else '  [配对 ⇄ %s]' % _on)))
        if _AMBIG:
            print('   ★ 配对歧义（不比较，逐条公示）：%d 项' % len(_AMBIG))
            for k, fc, oc in _AMBIG[:10]:
                print('      键 %-40s 工厂%s 我方%s' % (k, fc, oc))
        return 0

    if a.fn:
        vf = void_fns_all()          # ★ 双源：语料 ∪ 上游源码签名（第 105 轮）
        o = {}
        # ★ 第 160 轮：函数特设合法输入组（如 `xmp3_FDCT32` 的合法定点缓冲区）。
        #   ★ 只在 FN_CORPUS 里有该函数时替换全局语料；--groups 仍可按组名筛子集。
        cps_fn = FN_CORPUS.get(a.fn)
        if cps_fn is not None:
            _validate_fn_corpus(BF, BO, a.fn)      # 种子地址必须两侧都映射（fail-loud）
            if a.groups:
                want = {g.strip() for g in a.groups.split(',') if g.strip()}
                cps_fn = [c for c in cps_fn if c[0] in want]
            if not cps_fn:
                sys.stderr.write('★★ FN_CORPUS[%s] 被 --groups 过滤成空集\n' % a.fn)
                return 9
        else:
            cps_fn = cps
        v, rows = compare(BF, BO, a.fn, a.steps, corpus=cps_fn, void_fns=vf, out=o,
                         o_name=_PAIRS.get(a.fn, (a.fn, a.fn))[1])
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
        ART = {'factory': {'path': os.path.relpath(fac, ROOT), 'sha256': _sha[fac]},
               'ours': {'path': os.path.relpath(ours, ROOT), 'sha256': _sha[ours]}}
        names = common[:a.limit] if a.limit else common
        esc_steps = a.steps * ESCALATE_FACTOR
        void_fns = void_fns_all()    # ★ 双源（第 105 轮）
        vmsg = 'void 表 = Ghidra 语料 ∪ 上游源码签名'
        stats = {'PASS': 0, 'DIVERGE': 0, 'SKIP': 0, 'INFO': 0, 'TRUNC': 0, 'REFDEAD': 0,
                 'DEADEQ': 0}
        n_esc = 0                      # 靠放大预算才判出来的函数数
        n_voidret = 0                  # r0 因"返回类型 void"而未作判据的函数数
        voidret_names = []
        info_names = []
        det = []
        verdicts = {}                # ★ R295：fn -> 最终等级（供 G3 全表）
        div_names_all = []
        trunc_names = []
        refdead_names = []
        skip_names = []
        deadeq_names = []
        all_x = []          # ★ `--dump-rows` 用：逐组机器可读明细（**不截断**）
        for i, n in enumerate(names):
            o = {}
            v, rows = compare(BF, BO, n, a.steps, corpus=cps, void_fns=void_fns, out=o,
                             o_name=_PAIRS.get(n, (n, n))[1])
            if v == 'TRUNC':
                # ★ 放大重试：只对"确实截断"的函数付费，避免把分歧藏进"不可判"
                o2 = {}
                v2, rows2 = compare(BF, BO, n, esc_steps, corpus=cps, void_fns=void_fns, out=o2,
                                  o_name=_PAIRS.get(n, (n, n))[1])
                if v2 != 'TRUNC':
                    v, rows, o = v2, rows2, o2
                    n_esc += 1
            # ★ 2026-09-30：明细**无条件**收集（原来只在 `--dump-rows` 时收）。
            #   为什么必须：新加的「访存内联等价」判据靠它建索引；若只有传了 `--dump-rows`
            #   才算，则 **CI 与本地会得出两个 DIVERGE 值**（正是"同一分母两个值"。
            #   内存代价实测 ~5 MB，可忽略）。`--dump-rows` 现在只决定**要不要落盘**。
            all_x.extend(o.get('xrows') or [])
            if o.get('ret_unjudged'):
                n_voidret += 1
                if len(voidret_names) < 40:
                    voidret_names.append(n)
            stats[v] += 1
            verdicts[n] = v          # ★ R295（G3）：每函数最终等级，全量落盘
            if (i + 1) % 25 == 0:
                gc.collect()          # ★ 见 run_func 末尾注释：不周期回收会 MemoryError
            if v == 'DIVERGE':
                div_names_all.append(n)
            elif v == 'TRUNC':
                trunc_names.append(n)
            elif v == 'REFDEAD':
                refdead_names.append(n)
            elif v == 'DEADEQ':
                deadeq_names.append(n)
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
                        # ★ 证据（死亡现场等）走 note ⇒ 附在明细里，**不进 diffs**（判据字段必须纯净）
                        _ev = (r[9] if len(r) > 9 and r[9] else '')
                        det.append((n, '  %-44s [%s] %s%s'
                                    % (n, r[0], '; '.join(map(str, r[8])),
                                       ('  || 证据: ' + _ev[:120]) if _ev else '')))
            if (i + 1) % 10 == 0:
                sys.stderr.write('   ... %d/%d\n' % (i + 1, len(names)))

        # ★★★ 2026-09-30 新增：把「**访存**内联等价」接进尺子 —— 与 `calls_ext` 那条
        #   「内联等价」判据**对称**（§0.29-F P0'）。
        #   机理：工厂把共享子过程**内联**进调用方、我们保留成独立函数 ⇒ 同一地址的访存
        #   归到"别的函数"头上 ⇒ 整类**假发散**（§0.29-D 的 INLINE-MOVE）。
        #   判据真源 = `tools/inline_move.py`（纪律 69，此处只**调用**）。
        #   ★ **保守**：要求逐行都只含访存维度，且**每一条**一侧键都在对侧别的函数里被解释。
        #   ★ 预登记（纪律 61，改前先在现有数据上算出）：DIVERGE 36 → **27**（降级 9 个）。
        #   ★ 可关：`CGM_INLINE_MOVE_OFF=1` 恢复旧口径（已并入判据指纹 ⇒ 关掉即台账失效）。
        imv_names = []
        if os.environ.get('CGM_INLINE_MOVE_OFF') != '1':
            try:
                import inline_move as _IM
            except ImportError:                                   # pragma: no cover
                import importlib.util as _ilu
                _sp = _ilu.spec_from_file_location(
                    'inline_move', os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                'inline_move.py'))
                _IM = _ilu.module_from_spec(_sp)
                _sp.loader.exec_module(_IM)                       # ★ 导入失败必须炸，不得静默退化
            _sf, _so = _IM.build_index(all_x)
            _byfn = {}
            for _r in all_x:
                if _r.get('kind') == 'DIVERGE':
                    _byfn.setdefault(_r['fn'], []).append(_r)
            for _n in div_names_all:
                if _IM.function_verdict(_n, _byfn.get(_n, []), _sf, _so)[0] == 'FULL':
                    imv_names.append(_n)
            if imv_names:
                _s = set(imv_names)
                stats['DIVERGE'] -= len(imv_names)
                stats['PASS'] += len(imv_names)      # 与 calls_ext 的内联等价同待遇：计入 PASS
                div_names_all[:] = [x for x in div_names_all if x not in _s]
                det[:] = [(n, t) for n, t in det if n not in _s]
        # ★★★ 2026-10-05（第 153 轮）：DIVERGE **信号强度**分档（派生报告，只读不改）。
        #   见 classify_signal()：把 DIVERGE 拆成 REAL（合法输入下就有差异）/ ABI
        #   （ret-only 且两侧 ret 都落在沙箱人造区，非语义差异）/ NOISE（只在
        #   双侧早死组发散）/ UNDECIDABLE（无跑完组）。**不改 stats、不改 verdict**，
        #   棘轮台账与分桶自洽等式一律不动 —— 这一行只是让头条数字不再把噪声当信号。
        _byfn_x = {}
        for _r in all_x:
            _byfn_x.setdefault(_r['fn'], []).append(_r)
        sig = {'REAL': [], 'ABI': [], 'NOISE': [], 'UNDECIDABLE': []}
        for _n in sorted(set(div_names_all)):
            _t, _w = classify_signal(_byfn_x.get(_n, []))
            sig[_t].append((_n, _w))
        lines = ['=' * 96, 'diff_exec 批量对拍（工厂 vs 重建产物）', '=' * 96,
                 '  分母口径：工厂 STT_FUNC ∧ 有名 ∧ st_size>0 = 804（权威，与 ledger/functions.csv 同源）',
                 '  ⚠ 已排除工厂 st_size==0 的无长度别名 %d 个（工具链 CRT/libgcc，非重建范围）：%s'
                 % (len(BF.zero_len_funcs), ', '.join(sorted(BF.zero_len_funcs)) or '（无）'),
                 '  共有函数 %d；本轮 %d 个；每函数 3 组输入' % (len(common), len(names)),
                 '  被测产物：%s (sha256 %s)' % (ART['ours']['path'], ART['ours']['sha256'][:16]),
                 '  对照产物：%s (sha256 %s)' % (ART['factory']['path'], ART['factory']['sha256'][:16]),
                 '  判据强度：--steps %d；触上限者按 %d× 放大重试一次（本轮 %d 个靠放大才判出）'
                 % (a.steps, ESCALATE_FACTOR, n_esc),
                 '  返回类型：%s；r0 未作判据（void）的函数 %d 个'
                 % (vmsg, n_voidret),
                 '  汇总：PASS %d ｜ DIVERGE %d ｜ TRUNC(不可判) %d ｜ DEADEQ(共同早死等价) %d '
                 '｜ REFDEAD(参照侧早死) %d ｜ SKIP %d'
                 % (stats['PASS'], stats['DIVERGE'], stats['TRUNC'], stats['DEADEQ'],
                    stats['REFDEAD'], stats['SKIP']),
                 '        （另：INFO「内联等价留痕」%d 个 —— 在 ok/info 行上单独计数，**与上面各类不互斥**，'
                 '不可相加）' % stats['INFO'],
                 '        （另：**访存**内联等价留痕 %d 个 —— 已计入 PASS，**与上面各类不互斥**，'
                 '不可相加；关掉用 CGM_INLINE_MOVE_OFF=1）%s'
                 % (len(imv_names), ('：' + ', '.join(imv_names[:12])) if imv_names else ''),
                 '  ★ 自洽校验：%d + %d + %d + %d + %d + %d = %d ；本轮函数数 = %d ⇒ %s'
                 % (stats['PASS'], stats['DIVERGE'], stats['TRUNC'], stats['DEADEQ'],
                    stats['REFDEAD'], stats['SKIP'],
                    stats['PASS'] + stats['DIVERGE'] + stats['TRUNC'] + stats['DEADEQ']
                    + stats['REFDEAD'] + stats['SKIP'],
                    len(names),
                    'OK' if (stats['PASS'] + stats['DIVERGE'] + stats['TRUNC'] + stats['DEADEQ']
                             + stats['REFDEAD'] + stats['SKIP']) == len(names)
                    else '★ 不一致 ⇒ 判据分桶有漏项，本报告不可引用 ★'),
                 '', '  --- DIVERGE 明细（前 80）---']
        lines.extend(t for _, t in det[:80])
        # ★★★ 信号强度分档（第 153 轮）：**不改变上面任何 verdict**，只把同一批 DIVERGE
        #   按「差异出现在合法输入组 / 只出现在双侧早死组 / 根本没有跑完组」重述一遍。
        #   目的：头条数字 DIVERGE=N 里的噪声可见，避免"给噪声改源码"。
        lines.append('')
        lines.append('  --- DIVERGE 信号强度（派生，不改判据）：REAL %d ｜ ABI %d ｜ NOISE %d ｜ UNDECIDABLE %d ｜'
                     ' 合计 %d ---' % (len(sig['REAL']), len(sig['ABI']), len(sig['NOISE']),
                                        len(sig['UNDECIDABLE']),
                                        len(sig['REAL']) + len(sig['ABI']) + len(sig['NOISE'])
                                        + len(sig['UNDECIDABLE'])))
        lines.append('      REAL = 有跑完组且其中就有差异（**该追**）；'
                     'NOISE = 跑完组全一致、发散只在双侧早死组（**别改源码**）；'
                     'UNDECIDABLE = 无跑完组（先补沙箱/模型）')
        for _t in ('REAL', 'ABI', 'NOISE', 'UNDECIDABLE'):
            for _n, _w in sig[_t]:
                lines.append('    [%-11s] %-34s %s' % (_t, _n[:34], _w))
        lines.append('')
        lines.append('  --- 访存内联等价（工厂把共享子过程内联进调用方，其余观测量全一致；'
                     '已计入 PASS，**与上面各类不互斥**）（前 40）---')
        lines.extend('  %s' % n for n in (imv_names[:40] or ['（无）']))
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
        lines.append('  --- REFDEAD：**参照侧(F)在沙箱里内存未映射早死** ⇒ 本组不可判'
                     '（不得算成我们的发散；§2.3 的机械实现）---')
        lines.extend('  %s' % n for n in (refdead_names[:40] or ['（无）']))
        lines.append('')
        lines.append('  --- DEADEQ：两侧**同一个野地址（段外）早死** ⇒ 语义等价，不计 DIVERGE'
                     '（DEADEQ-v2，第 153 轮；关掉用 CGM_DEADEQ2_OFF=1）---')
        lines.extend('  %s' % n for n in (deadeq_names[:40] or ['（无）']))
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
        undecidable = set(trunc_names) | set(skip_names) | set(refdead_names) | set(deadeq_names)
        rc = 1 if stats['DIVERGE'] else 0
        # ★ 分桶自洽（fail-closed）：PASS+DIVERGE+TRUNC+SKIP+REFDEAD 必须**等于**本轮函数数。
        #   不等 ⇒ 有函数没被计入任何一桶（判据漏项）⇒ 报告不可引用 ⇒ 直接红。
        #   来源：2026-09-27 发现 INFO 曾被并列在汇总行里，让人误以为四类可相加（实际 INFO 是重叠计数）。
        _part_ok = partition_ok(stats, len(names))
        if not _part_ok:
            sys.stderr.write('★★ 分桶不自洽：PASS+DIVERGE+TRUNC+DEADEQ+SKIP+REFDEAD ≠ 本轮函数数 '
                             '(%d+%d+%d+%d+%d+%d vs %d)\n'
                             % (stats['PASS'], stats['DIVERGE'], stats['TRUNC'], stats['DEADEQ'],
                                stats['SKIP'], stats['REFDEAD'], len(names)))
            rc = 1
        if a.ledger:
            old_steps = old_esc = None
            old = []
            led_txt = ''
            if os.path.exists(a.ledger):
                led_txt = open(a.ledger, encoding='utf-8', errors='replace').read()
                old_steps, old_esc, old = read_ledger_text(led_txt)
            _meta = read_ledger_meta(led_txt)
            _write = bool(a.update_ledger or a.rebaseline)
            # （★ 口径门禁已在**跑之前**执行 —— 见 `ledger_protocol_guard`。此处不重复实现，纪律 69。）
            if _write:
                keep, removed, kept_und = ledger_update(old, div_names, undecidable)
                os.makedirs(os.path.dirname(a.ledger) or '.', exist_ok=True)
                with open(a.ledger, 'w', encoding='utf-8', newline='\n') as fh:
                    fh.write('# diff_exec 发散棘轮台账（只允许减少）\n')
                    fh.write('# steps=%d\n' % a.steps)
                    fh.write('# escalate=%d\n' % esc_steps)
                    fh.write('# ruler=%s\n' % _cur_ruler)
                    fh.write('# ours=%s\n' % ART['ours']['sha256'])
                    if a.reason:
                        fh.write('# rebaseline: %s\n' % a.reason)
                    fh.write('# 生成：python tools/diff_exec.py --batch --steps %d '
                             '--ledger <本文件> --update-ledger\n' % a.steps)
                    fh.write('# ★ 评测时必须用**相同的 steps/escalate/ruler**，否则本工具 '
                             'fail-closed (exit 3) —— 见 GAP 17.10 / §0.36\n')
                    fh.write('# ★ ruler = 判据口径指纹（compare() 源码 + 判据常量，机械推导）；'
                             '口径变了必须 --rebaseline --reason "..." 留痕\n')
                    for n in keep:
                        fh.write(n + '\n')
                lines.append('')
                lines.append('  台账已重写%s：%d 项（发散 %d + 旧台账中本轮不可判 %d）-> %s'
                             % ('（--rebaseline）' if a.rebaseline else '', len(keep),
                                len(div_names), len(kept_und), a.ledger))
                if a.rebaseline:
                    lines.append('    ruler = %s' % _cur_ruler)
                    lines.append('    ours  = %s' % ART['ours']['sha256'][:16])
                    lines.append('    原因  = %s' % (a.reason or '★ 未填（建议补 --reason）'))
                lines.append('  收敛移除 %d 项：%s' % (len(removed), removed[:30]))
                if kept_und:
                    lines.append('  ★ 保留的"不可判"债务（TRUNC/SKIP ≠ 已收敛）：%s' % kept_und[:30])
                rc = 0 if _part_ok else 1
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
        if a.dump_rows:
            # ★★★ 机器可读明细（不截断）：归类唯一合法的数据源。
            #   同时记录**两侧产物 sha + 判据强度**，否则下游归类无法证明它读的是哪一版。
            meta = dict(ours=ART['ours'], factory=ART['factory'],
                        steps=a.steps, escalate_factor=ESCALATE_FACTOR,
                        shared=len(common), judged=len(names),
                        stats={k: stats[k] for k in
                               ('PASS', 'DIVERGE', 'TRUNC', 'DEADEQ', 'REFDEAD', 'SKIP', 'INFO')},
                        refdead_off=(os.environ.get('CGM_REFDEAD_OFF') == '1'),
                        inline_move_off=(os.environ.get('CGM_INLINE_MOVE_OFF') == '1'),
                        inline_move_equiv=sorted(imv_names))
            with open(a.dump_rows, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(dict(meta=dict(meta, verdicts=verdicts), rows=all_x), fh, ensure_ascii=False)
            print('  ★ 逐组明细已写出：%s（%d 行；含两侧归一化访存/调用指纹）'
                  % (a.dump_rows, len(all_x)))
        return rc

    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
