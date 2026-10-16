#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dce_ref_diff —— 检测「源码引用的工厂符号被优化器消除」（Δ 门禁）。

为什么需要它（GAP 16.99 的根因）
--------------------------------
重建源码来自 Ghidra 反编译，而 Ghidra 会按**类型推断**把工厂栈上的**一个连续缓冲**拆成
若干独立局部量。典型形态：

    char *local_150;          /* -0x150 */
    char *local_14c[4];       /* -0x14c…-0x140 */
    gh_u4 uStack_13c;         /* -0x13c */
    ...
    ppcVar4 = &local_150;     /* 取标量地址 */
    ppcVar4 = ppcVar4 + 1;    /* ★ 跨对象步进 = C 的未定义行为 */

GCC/clang 允许假定「越界指针不被解引用」，于是把**后续槽的写入整体删除**。
后果：原厂跑 10 条候选路径的循环退化成 1 条 —— **产物能链接、能启动，但语义发散**，
而且**任何静态门禁都不会报**（符号只是"少了一个"，不是"未定义"）。

判据（可机械执行、无需人判断语义）
----------------------------------
对同一个 .c **只改优化级别**编译两次，比较 UNDEF 里的工厂符号（`DAT_*` / `UNK_*`）：

    Δ = UNDEF(-O0) 减去 UNDEF(-Os)

Δ 非空 ⇒ 源码里那些工厂数据引用**在 -Os 下消失了**。两种可能：
  (a) UB 被消除（缺陷，见 GAP 16.99）；
  (b) 存储确实是死的（合法优化，例如值从未被使用、或被常量折叠掉）。
★ 因此 Δ 是**待核清单**，不是缺陷证明：默认按 (a) 处理（硬失败），
  确认属于 (b) 的必须在 ALLOW 里登记，并在 GAP.md 写明「为什么语义不变」。
★ 2026-09-23 交叉对照（两个独立仪器）：13 个存量 Δ 文件**全部**在 `tools/prop_equiv.py`
  里判为 **OK**（size 比 0.895–1.448，健康带 p95=1.33），且用 `tools/factory_fn_stack.py`
  对工厂函数反汇编可见「该槽写了但从未按常量位移读回」⇒ 判定为**低风险（不阻塞替代）**，
  但**保守保留在债务表**并逐条标注证据 —— 待有更强判据（帧指针别名数据流）时再清。
★ 工具会给每个 Δ 文件附一个 `[UB?]` 提示（源码里出现「取标量地址 + 步进」形态），
  仅用于分诊排序，不作为判据。

★ 为什么用 `-O0` 当参照：`-O0` 不做 DCE，它最接近「源码字面写了什么引用」。
★ 为什么是 UNDEF：工厂数据/代码符号在 .o 里必然是 UNDEF（由 .set 别名供应），
  所以 UNDEF 集合就是「这个 TU 引用了哪些工厂符号」的精确清单。

★★ 集合级判据的盲区（R180 实证，GAP 18.01）
-----------------------------------------
`Δ = set(-O0) − set(-Os)` 只能发现「**整个符号**在 -Os 下消失」。但若同一个符号
在本 TU 的**别处仍然被引用**（例如 `mui_DisplayThumbnail` 的 `DAT_003af29c`
既在 memcpy 循环里用、又在块读参数槽里用），死写被消除**不会**改变符号的在场性
⇒ Δ 为空，门禁放行，而 -Os 产物里那 12 个槽的写入已经没了。

因此本工具在 `--count` 模式下追加**出现次数级（occurrence-level）**判据：

    Δcount(sym) = reloc_count(-O0, sym) − reloc_count(-Os, sym)

reloc_count = `.rel.text` / `.rel.data*` 里指向该 UNDEF 符号的重定位条目数。
Δcount > 0 ⇒ 该符号在 -Os 下被少引用了若干次 —— 与「集合级 Δ」互补：
集合级回答「符号还在不在」，次数级回答「引用少没少」。二者都必须为空才算清白。

★★ R182 增补：工厂侧旁证（`factory_blockread_hint`，默认开）
---------------------------------------------------------
Δ 只是"待核清单"：符号消失既可能是 UB-DCE 真缺陷，也可能是合法 DCE。
本版把 `tools/factory_fn_stack.py`（R182 的 `--indirect` 判据）接进来：对每个
Δ>0 的文件，按文件名解析出对应**工厂函数**，跑「被调函数间接读」分析，把块读
调用点与覆盖槽直接附在 Δ 报告上（`<<工厂间接读: …>>`；`*` = 块读族高风险）。
* 旁证**永不改变门禁结论**（不新增 hard-fail、不放宽任何一条）—— 它只把
  「必须回工厂反汇编逐槽数」这一步自动化。
* 命名诚实（R184）：它覆盖**所有**经帧地址实参间接读的被调函数（strupr /
  mxmlElementGetAttr / extract_basepath / 块读族…），不只五个块读函数；
  块读族成员带 `*` = 高风险（Ghidra 拆 12-int 参数槽的高发区）。
* 文件名不匹配 / 无 symtab / 无 ELF / 分析异常 ⇒ 返回 None（优雅降级，绝不外抛）。
* `--no-factory-hint` 可关（A/B 用）。

自证（`--self-test`，先自证再信数）
----------------------------------
* 正例：人造「拆局部量 + 跨对象步进」样本 ⇒ Δ 必须非空
* 反例：人造「同一个数组内正常步进」样本 ⇒ Δ 必须为空
* 回归：真实文件 `core/FUN_002b6c14_FBA_Load.c` 修复后 ⇒ Δ 必须为空（防复发）
用法
----
    CC="<zig> cc" python tools/dce_ref_diff.py            # 全量扫描（集合级）
    CC="<zig> cc" python tools/dce_ref_diff.py --count    # 全量扫描（出现次数级，GAP 18.01）
    CC="<zig> cc" python tools/dce_ref_diff.py --self-test

退出码：0 = 无 Δ（或全在 ALLOW 里）；2 = 存在未登记的 Δ
`--count` 模式**恒返回 0**：它是分诊清单（次数下降既可能是缺陷也可能是合法 CSE），
不是硬门禁；硬门禁仍是上面的集合级 Δ。二者都为空才算清白。
"""
import argparse
import os
import re
import struct
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'src', 'proprietary')
INC = os.path.join(ROOT, 'src', 'compat')

# ★ 已登记待核债务：{相对路径: (符号元组, 理由)}。
#
# 纪律：这是一张**必须缩小**的债务表，不是豁免。
#   · 每一条都必须能追溯到 GAP.md 的条目；
#   · 已判定为「合法 DCE」的写明为什么语义不变；
#   · 已判定为「缺陷」的必须修掉并从此表移除（修掉即证据）。
# 门禁只对**表外新增**的 Δ 硬失败 —— 这样既立刻拦住回归，又不掩盖存量。
#
# 判定方法（两种，都要落到原厂反汇编）：看该局部量在**原厂**是否被读。
#   ① 重建源码里「只赋值、从不读」⇒ 大概率合法 DCE（见 #4 的 local_32c）；
#   ② 重建源码里「被跨对象步进读」⇒ UB-DCE，是真缺陷（见已修的 core/FUN_002b6c14_FBA_Load.c）。
ALLOW = {
    # R179 铁证：下面 5 条 b2320 组是「栈槽只写一次、工厂反汇编**从不读回**」的真·合法 DCE，
    # 其余 8 条原债务（joystick/video/PauseMenu/load_state/save_state/DisplayPage_list/TestUSBJoy/
    # DisplayGameSum）经工厂反汇编复核属 UB-DCE 真缺陷，已根修（数组化/块拷），从本表移除。
    'src/proprietary/mui/FUN_00023204_mui_menu.c':
        (('DAT_003b2320',), '合法 DCE（见 R179）：工厂反汇编 local_32c 槽(-0x32c/sp#420) 只 str 一次、全函数无 ldr 读回'),
    'src/proprietary/mui/FUN_00023e10_mui_type.c':
        (('DAT_003b2320',), '合法 DCE（见 R179）：工厂反汇编 local_32c 槽(sp#340) 只 str 一次、无 ldr 读回'),
    'src/proprietary/mui/FUN_00025094_mui_search.c':
        (('DAT_003b2320',), '合法 DCE（见 R179）：工厂反汇编 local_32c 槽(sp#340) 只 str 一次、无 ldr 读回'),
    'src/proprietary/mui/FUN_000277bc_mui_recent.c':
        (('DAT_003b2320',), '合法 DCE（见 R179）：工厂反汇编 local_32c 槽(sp#860) 只 str 一次、无 ldr 读回'),
    'src/proprietary/mui/FUN_00028a74_mui_shoucang.c':
        (('DAT_003b2320',), '合法 DCE（见 R179）：工厂反汇编 local_32c 槽(sp#428) 只 str 一次、无 ldr 读回'),
}
FACTORY_PREFIX = ('DAT_', 'UNK_')

# ARM32 重定位类型（ELF32 ARM ABI）：movw/movt 成对出现算**一次**物化（R183）
#   MOVW_ABS_NC=43 / MOVT_ABS=44 / MOVW_PREL_NC=45 / MOVT_PREL=46 /
#   THM_MOVW_ABS_NC=47 / THM_MOVT_ABS=48
R_MOVW = (43, 44, 45, 46, 47, 48)
R_MOVT = (44, 46, 48)

# 仅用于分诊排序的"UB 形态"提示：
#   形态 A = 取**局部标量**的地址（Ghidra 拆出来的 local_XXX / uStack_XXX / acStack_XXX …）
#   形态 B = 同一个指针变量做 `p = p + n` 步进
RE_UB_A = re.compile(r'&\s*(?:local_|uStack_|iStack_|auStack_|acStack_|stack_|pStack_|uVar|iVar)')
RE_UB_B = re.compile(r'\b([A-Za-z_]\w*)\s*=\s*\1\s*\+\s*\d')


def ub_hint(path):
    try:
        t = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return False
    return bool(RE_UB_A.search(t)) and bool(RE_UB_B.search(t))


def cflags(opt):
    cc = os.environ.get('CC', 'arm-linux-gnueabihf-gcc')
    if 'zig' in cc:
        arch = ['-target', 'arm-linux-gnueabihf', '-mfloat-abi=hard', '-mfpu=neon']
    else:
        arch = ['-march=armv7-a', '-mfloat-abi=hard', '-mfpu=neon', '-fno-pic']
    return [opt, '-c', '-w', '-Wno-error=implicit-function-declaration',
            '-I' + INC] + arch + ['-fno-stack-protector', '-U_FORTIFY_SOURCE',
                                  '-D_FORTIFY_SOURCE=0']


def undef_factory(obj):
    """读 ELF32 .o 的 .symtab，返回 UNDEF 里的工厂符号集合。"""
    if not os.path.exists(obj) or os.path.getsize(obj) < 64:
        return None                      # 编译失败
    b = open(obj, 'rb').read()
    if b[:4] != b'\x7fELF':
        return None
    e_shoff, = struct.unpack_from('<I', b, 0x20)
    ents, shn, shx = struct.unpack_from('<HHH', b, 0x2e)
    sh = [struct.unpack_from('<10I', b, e_shoff + i * ents) for i in range(shn)]
    names = []
    st = sh[shx]
    for s in sh:
        t = b[st[4] + s[0]:]
        names.append(t[:t.index(b'\x00')].decode('ascii', 'replace'))
    if '.symtab' not in names or '.strtab' not in names:
        return None
    S = names.index('.symtab')
    T = names.index('.strtab')
    tb = b[sh[T][4]:sh[T][4] + sh[T][5]]
    out = set()
    for i in range(sh[S][5] // 16):
        o = sh[S][4] + i * 16
        no, va, sz, info, oth, shnd = struct.unpack_from('<IIIBBH', b, o)
        if not no or shnd != 0:
            continue
        n = tb[no:tb.index(b'\x00', no)].decode('ascii', 'replace')
        if n.startswith(FACTORY_PREFIX):
            out.add(n)
    return out


def reloc_counts(obj):
    """读 ELF32 .o 的 SHT_REL 节，返回 {工厂符号名: **物化点**数}。

    这是**出现次数级**判据的原料（见文件头「集合级判据的盲区」）。
    只数 `sh_type == SHT_REL(9)` 的节（ARM32 .o 用 REL，不用 RELA）；
    符号名取自 .symtab，只保留 FACTORY_PREFIX 前缀的 UNDEF 符号。
    ★ 返回的是**物化点**数而非裸 reloc 数：movw/movt 成对算一次（R183，
      否则 -O0/-Os 的码生成策略差会被误报成"引用消失"，见 `_count_sites`）。
    """
    if not os.path.exists(obj) or os.path.getsize(obj) < 64:
        return None
    b = open(obj, 'rb').read()
    if b[:4] != b'\x7fELF':
        return None
    e_shoff, = struct.unpack_from('<I', b, 0x20)
    ents, shn, shx = struct.unpack_from('<HHH', b, 0x2e)
    sh = [struct.unpack_from('<10I', b, e_shoff + i * ents) for i in range(shn)]
    names = []
    st = sh[shx]
    for s in sh:
        t = b[st[4] + s[0]:]
        names.append(t[:t.index(b'\x00')].decode('ascii', 'replace'))
    if '.symtab' not in names or '.strtab' not in names:
        return None
    S = names.index('.symtab')
    T = names.index('.strtab')
    tb = b[sh[T][4]:sh[T][4] + sh[T][5]]
    syms = []
    for i in range(sh[S][5] // 16):
        o = sh[S][4] + i * 16
        no, va, sz, info, oth, shnd = struct.unpack_from('<IIIBBH', b, o)
        if not no:
            syms.append(None)
            continue
        n = tb[no:tb.index(b'\x00', no)].decode('ascii', 'replace')
        syms.append(n if (shnd == 0 and n.startswith(FACTORY_PREFIX)) else None)
    raw = {}                               # sym -> [(r_offset, r_type), ...]
    for s in sh:
        if s[1] != 9:                       # SHT_REL
            continue
        if s[5] == 0:
            continue
        blob = b[s[4]:s[4] + s[5]]
        for i in range(len(blob) // 8):
            r_off, r_info = struct.unpack_from('<II', blob, i * 8)
            sym = r_info >> 8
            rtype = r_info & 0xff
            if sym >= len(syms):
                continue
            n = syms[sym]
            if n is None:
                continue
            raw.setdefault(n, []).append((r_off, rtype))
    return _count_sites(raw)


def _count_sites(raw):
    """把重定位归一成「物化点」数（R183 修：消掉码生成策略差）。

    ★ 为什么必须归一并（R183 云机实测）：`-O0` 用 `movw+movt` **两条** reloc
      物化一个符号地址，`-Os` 用字面量池 `.word` **一条**。不归一时，
      「每条真实引用」在 -O0/-Os 之间恒定差 1 ⇒ 次数级判据把**码生成策略差**
      误报成「引用消失」（两个不同符号各引用一次也报 -1，假阳）。
    ★ 归一规则：同符号、地址相差 4 的 movw/movt 对算**一个**物化点；
      其余每条 reloc 算一个点。这样 -O0 与 -Os 的「每次真实引用」都记 1。
    """
    out = {}
    for n, lst in raw.items():
        by_addr = {}
        for off, t in lst:
            by_addr.setdefault(off, []).append(t)
        used = set()
        cnt = 0
        for off in sorted(by_addr):
            if off in used:
                continue
            used.add(off)
            cnt += 1
            nxt = by_addr.get(off + 4)
            if nxt and any(t in R_MOVW for t in by_addr[off]) and any(t in R_MOVT for t in nxt):
                used.add(off + 4)          # movw/movt 成对 ⇒ 已算 1 点，吃掉 +4 那条
        out[n] = cnt
    return out


def compile_one(src, opt, out):
    cc = os.environ.get('CC', 'arm-linux-gnueabihf-gcc').split()
    cmd = cc + cflags(opt) + [src, '-o', out]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0


def delta_of(src, tmpd):
    o0 = os.path.join(tmpd, 'a.o')
    os_ = os.path.join(tmpd, 'b.o')
    for p in (o0, os_):
        if os.path.exists(p):
            os.remove(p)
    ok0 = compile_one(src, '-O0', o0)
    ok1 = compile_one(src, '-Os', os_)
    if not ok0 or not ok1:
        return None, None            # 编译失败 → 交给别的门禁管
    a = undef_factory(o0)
    c = undef_factory(os_)
    if a is None or c is None:
        return None, None
    return a, c


def delta_count_of(src, tmpd):
    """出现次数级：返回 ({sym: n0}, {sym: n1})，n0=-O0 次数、n1=-Os 次数。"""
    o0 = os.path.join(tmpd, 'a.o')
    os_ = os.path.join(tmpd, 'b.o')
    for p in (o0, os_):
        if os.path.exists(p):
            os.remove(p)
    ok0 = compile_one(src, '-O0', o0)
    ok1 = compile_one(src, '-Os', os_)
    if not ok0 or not ok1:
        return None, None
    a = reloc_counts(o0)
    c = reloc_counts(os_)
    if a is None or c is None:
        return None, None
    return a, c


def _load_ffs():
    """加载同目录的 factory_fn_stack（R182 起用作 Δ 的工厂侧旁证）。
    任何失败都返回 None —— 旁证缺失**不得**影响门禁本身。"""
    try:
        import factory_fn_stack as ffs
        return ffs
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    try:
        import factory_fn_stack as ffs
        return ffs
    except Exception:
        return None


# 我方 TU 文件名 → 工厂函数名：FUN_0002eac8_mui_load_state.c → mui_load_state
#   （GCC 分片后缀 .isra.19 / .constprop.0 / .part.0 / .cold 要剥掉，否则 symtab 查不到）
RE_FN_FILE = re.compile(r'^FUN_[0-9a-fA-F]+_(.+?)\.c$')
RE_GCC_PART = re.compile(r'\.(isra|constprop|part|cold|clone)(\.\d+)?$')


def _factory_fn_name(rel):
    base = os.path.basename(rel)
    m = RE_FN_FILE.match(base)
    if not m:
        return None
    name = m.group(1)
    prev = None
    while prev != name:                      # 可能多重后缀（.isra.0.constprop.0）
        prev = name
        name = RE_GCC_PART.sub('', name)
    return name or None


def factory_blockread_hint(rel):
    """工厂侧旁证（R182）：该 TU 对应的工厂函数里，哪些栈槽被块读函数间接读。

    用途：Δ 只是"待核清单"，本条把工厂侧的槽覆盖情况直接附在 Δ 报告上 ——
    若 Δ 符号落在被 `blockcopy`/`blockadaptive`/`mui_blockcopy`/`popwindows`/
    `popoffwindows` 间接读的槽里 ⇒ 是真缺陷（UB-DCE，GAP 18.01）；
    若工厂侧**没有任何**块读实参落在这些槽 ⇒ 支持"合法 DCE"的判定。

    **永不抛异常、永不改变门禁结论**：文件名不匹配 / 无 symtab / 无 ELF /
    分析异常一律返回 None（旁证缺失 ≠ 通过，也不 ≠ 失败）。
    """
    try:
        fn = _factory_fn_name(rel)
        if not fn:
            return None
        ffs = _load_ffs()
        if ffs is None:
            return None
        syms = ffs.parse_symtab()
        if not syms or fn not in syms:
            return None
        addr, size = syms[fn]
        elf = ffs.Elf32(ffs.FACTORY)
        off = elf.v2f(addr)
        if off is None:
            return None
        code = elf.b[off:off + size]
        a2 = ffs.by_addr(syms)

        def _fetch(a, s):
            o = elf.v2f(a)
            return elf.b[o:o + s] if o is not None else b''

        res = ffs.analyse_indirect(code, addr, lambda t: a2.get(t), _fetch)
        parts = []
        for r in res:
            star = '*' if r['name'] in ffs.BLOCKREAD_FAMILY else ''
            if r.get('unresolved'):
                parts.append('@0x%x→%s%s(边界不可解析⇒不得判死)' % (r['call'], r['name'], star))
                continue
            if r.get('indexed'):
                parts.append('@0x%x→%s%s(索引读⇒不得判死)' % (r['call'], r['name'], star))
            if r['slots']:
                parts.append('@0x%x→%s%s[%s]' % (
                    r['call'], r['name'], star,
                    ' '.join('sp+0x%x' % s for s in sorted(r['slots']))))
        # ★ 命名诚实（R184）：本旁证覆盖**所有**经帧地址实参间接读的被调函数
        #   （strupr / mxmlElementGetAttr / extract_basepath / 块读族…），不只五个块读函数；
        #   块读族成员带 `*` 标记 = 高风险（Ghidra 拆 12-int 参数槽的高发区）。
        return ('工厂间接读: ' + ' ; '.join(parts)) if parts else None
    except Exception:
        return None


def self_test():
    print('=' * 96)
    print('自证：先用已知答案的样本验仪器')
    print('=' * 96)
    ok = True

    def chk(tag, got, want):
        nonlocal ok
        good = (got == want)
        ok = ok and good
        print('   %-58s got=%-22s %s' % (tag, got, '✓' if good else '★ FAIL'))

    tmpd = tempfile.mkdtemp(prefix='dce_')
    hdr = os.path.join(tmpd, 'globals.h')
    with open(hdr, 'w') as fh:
        for n in ('DAT_003b0130', 'DAT_003b0134', 'DAT_003b0140'):
            fh.write('extern unsigned int %s;\n' % n)

    # ① 正例：拆局部量 + 跨对象步进（UB）⇒ 期望 Δ 非空
    pos = os.path.join(tmpd, 'pos.c')
    with open(pos, 'w') as fh:
        fh.write('''#include "globals.h"
char *walk(char **p);
/* 单个缓冲被拆成两个局部量，然后用 &标量 + k 跨对象步进 —— 与原厂 Ghidra 输出同形态 */
int pos(void){
  char *local_150;
  char *local_14c[2];
  char **ppcVar4;
  unsigned acc = 0;
  local_150 = (char *)DAT_003b0130;
  local_14c[0] = (char *)DAT_003b0134;
  ppcVar4 = &local_150;
  ppcVar4 = ppcVar4 + 1;
  acc += (unsigned)(unsigned long)ppcVar4[0];
  return (int)acc;
}
''')
    a, c = delta_of(pos, tmpd)
    chk('正例  拆局部量+跨对象步进 → Δ 非空',
        (sorted(a - c) != []) if (a is not None and c is not None) else '编译失败',
        True)

    # ② 反例：同一个数组内正常步进 + **运行时下标**（强制两个引用都存活）⇒ Δ 必须为空
    neg = os.path.join(tmpd, 'neg.c')
    with open(neg, 'w') as fh:
        fh.write('''#include "globals.h"
char *pick(char **slots, int i);   /* 运行时下标 ⇒ 不能常量折叠 */
char *neg(int i){
  char *slots[3];
  slots[0] = (char *)DAT_003b0130;
  slots[1] = (char *)DAT_003b0134;
  slots[2] = 0;
  return pick(slots, i);
}
''')
    a, c = delta_of(neg, tmpd)
    chk('反例  同一数组内步进(运行时下标) → Δ 为空',
        (sorted(a - c) == []) if (a is not None and c is not None) else '编译失败',
        True)

    # ③ 回归：真实文件修复后 Δ 必须为空（防复发）
    real = os.path.join(SRC, 'core', 'FUN_002b6c14_FBA_Load.c')
    if os.path.exists(real):
        a, c = delta_of(real, tmpd)
        chk('回归  FUN_002b6c14_FBA_Load.c → Δ 为空',
            (sorted(a - c) == []) if (a is not None and c is not None) else '编译失败',
            True)

    # ⑤ 反例：非法输入必须返回 None（不能把失败当"无 Δ"）
    chk('反例  不存在的文件 → 视为不可判（None）',
        delta_of(os.path.join(tmpd, 'nope.c'), tmpd)[0], None)

    # ⑥ ★ 出现次数级（occurrence-level）判据自证 —— 堵「集合级掩盖」盲区（GAP 18.01）
    #    样本：DAT_003b0140 既在**活**处被读、又在**死写**处被存。
    #    预期：集合级 Δ 为空（符号仍在场 ⇒ 老判据放行），
    #          次数级 Δ 非空（死写被消除 ⇒ 新判据抓住）。
    occ = os.path.join(tmpd, 'occ.c')
    with open(occ, 'w') as fh:
        fh.write('''#include "globals.h"
int occ(void){
  int local_150;
  int local_14c[2];
  int acc = (int)DAT_003b0140;      /* 活引用：保证符号在 -Os 后仍在场 */
  local_150 = (int)DAT_003b0140;    /* 死写：从不读 ⇒ -Os 消除 */
  local_14c[0] = (int)DAT_003b0134;
  local_14c[1] = 0;
  return acc + local_14c[0];
}
''')
    a, c = delta_of(occ, tmpd)
    n0, n1 = delta_count_of(occ, tmpd)
    chk('⑥-集合级  活引用+死写 → Δ 为空（老判据放行）',
        (sorted(a - c) == []) if (a is not None and c is not None) else '编译失败',
        True)
    chk('⑥-次数级  活引用+死写 → Δcount 非空（新判据抓住）',
        ({k: v for k, v in n0.items() if n1.get(k, 0) < v} != {})
        if (n0 is not None and n1 is not None) else '编译失败',
        True)

    # ⑦ 反例：两个**不同**符号各引用一次、运行时下标 ⇒ 次数级 Δ 必须为空（防新判据误报）
    #    （R183 修：-O0 用 movw+movt 两条 reloc 物化一个符号、-Os 用字面量池一条 ⇒
    #     不归一时连"每条真实引用"都恒定差 1，假阳。已由 `_count_sites` 按
    # 「movw/movt 成对算一个物化点」归一，本条因此**真的**必须为空。）
    occn = os.path.join(tmpd, 'occn.c')
    with open(occn, 'w') as fh:
        fh.write('''#include "globals.h"
int occn(int i){
  int s[2];
  s[0] = (int)DAT_003b0140;
  s[1] = (int)DAT_003b0134;
  return s[i];
}
''')
    m0, m1 = delta_count_of(occn, tmpd)
    chk('⑦-次数级  两个不同符号各一次(运行时下标) → Δcount 为空',
        ({k: v for k, v in m0.items() if m1.get(k, 0) < v} == {})
        if (m0 is not None and m1 is not None) else '编译失败',
        True)

    # ⑧ ★ 工厂侧旁证（R182）：TU 文件名 → 工厂函数名 的提取 + 优雅降级
    chk('⑧ 文件名→工厂函数名（常规）',
        _factory_fn_name('src/proprietary/mui/FUN_0002eac8_mui_load_state.c'),
        'mui_load_state')
    chk('⑧ 文件名→工厂函数名（剥 .isra.N 分片）',
        _factory_fn_name('src/proprietary/mui/FUN_0001b240_mui_outputxy_length.isra.19.c'),
        'mui_outputxy_length')
    chk('⑧ 文件名→工厂函数名（剥 .constprop.N）',
        _factory_fn_name('src/proprietary/x/FUN_0000d678_InitDisplay.constprop.0.c'),
        'InitDisplay')
    chk('⑧ 非 FUN_ 文件名 → None（不得瞎猜）',
        _factory_fn_name('src/proprietary/misc/blockcopyish.c'), None)
    # 旁证函数必须**永不抛异常**：在/不在有 symtab 的环境里都只能返回 None 或 str
    for probe in ('src/proprietary/mui/FUN_0002eac8_mui_load_state.c',
                  'src/proprietary/misc/FUN_000299a4_blockcopy.c',
                  'tools/not-a-tu.c'):
        try:
            r = factory_blockread_hint(probe)
            chk('⑧ 旁证不抛异常且类型合法 %s' % os.path.basename(probe),
                (r is None or isinstance(r, str)), True)
        except Exception as e:               # pragma: no cover - 真抛了就是缺陷
            chk('⑧ 旁证不抛异常 %s' % probe, 'raised %s' % e, True)
    # 环境齐备（symtab + 工厂 ELF）时加验一条已知答案：mui_load_state 必有 blockcopy 块读
    ffs = _load_ffs()
    if ffs is not None and os.path.exists(ffs.FACTORY) and ffs.parse_symtab():
        h = factory_blockread_hint('src/proprietary/mui/FUN_0002eac8_mui_load_state.c')
        chk('⑧ 已知答案：mui_load_state 旁证含 blockcopy',
            (h is not None and 'blockcopy' in h), True)
        h2 = factory_blockread_hint('src/proprietary/mui/FUN_00023204_mui_menu.c')
        # b2320 槽在 mui_menu 里是 sp#420 = sp+0x1a4（R179 实测）。该函数确实向
        # filelist_run_game / FindZipItemA 传帧地址，但都不覆盖 0x1a4 ⇒ 合法 DCE 仍成立。
        chk('⑧ 已知答案：mui_menu 旁证**不覆盖** b2320 槽(sp+0x1a4)',
            ('sp+0x1a4' in (h2 or '')), False)
    else:
        print('   （⑧ 环境缺 symtab/工厂 ELF ⇒ 已知答案两腿跳过，仅验优雅降级）')

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--count', action='store_true',
                    help='出现次数级判据：Δcount = reloc_count(-O0) − reloc_count(-Os)')
    ap.add_argument('--no-factory-hint', action='store_true',
                    help='关闭工厂侧块读旁证（R182；旁证永不改变门禁结论，只影响报告信息量）')
    ap.add_argument('--out', help='报告输出路径')
    a = ap.parse_args()
    factory_hint = not a.no_factory_hint

    if a.self_test and not self_test():
        return 2

    files = []
    for dp, dn, fn in os.walk(SRC):
        for f in fn:
            if f.endswith('.c'):
                files.append(os.path.join(dp, f))
    files.sort()
    if a.limit:
        files = files[:a.limit]

    tmpd = tempfile.mkdtemp(prefix='dce_scan_')
    lines = []
    hits = []
    skipped = []

    if a.count:
        # ---------------- 出现次数级扫描（与集合级互补，见文件头 GAP 18.01）----------------
        # R184：每个待核文件都挂工厂侧旁证，并按「工厂侧有无块读实参」分两栏
        for p in files:
            rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
            aa, cc = delta_count_of(p, tmpd)
            if aa is None:
                skipped.append(rel)
                continue
            drop = {k: v - cc.get(k, 0) for k, v in aa.items() if cc.get(k, 0) < v}
            fh = factory_blockread_hint(rel) if (drop and factory_hint) else None
            if drop:
                hits.append((rel, drop, fh))
                lines.append('%-70s Δcount: %s%s' % (
                    rel, ' '.join('%s×%d' % (k, v) for k, v in sorted(drop.items())),
                    ('  <<' + fh + '>>') if fh else ''))
        hdr = ['=' * 96,
               'DCE 出现次数级门禁（Δcount = 物化点(-O0) − 物化点(-Os)）',
               '=' * 96,
               '扫描 %d 个文件；编译失败跳过 %d 个；★ 引用次数下降的文件 %d 个'
               % (len(files), len(skipped), len(hits)),
               '（与集合级 Δ 互补：集合级回答"符号还在不在"，次数级回答"引用少没少"）', '']
        if hits:
            colA = [h for h in hits if h[2]]      # 工厂侧有块读实参 ⇒ 疑似 UB-DCE
            colB = [h for h in hits if not h[2]]  # 工厂侧无块读实参 ⇒ 疑似合法
            hdr.append('【★ 引用次数下降】—— 这些符号在 -Os 下被少引用了（待核清单，'
                       '已按工厂侧旁证分栏）：')
            hdr.append('')
            hdr.append('  ── 栏 A：工厂侧**有**块读实参 ⇒ 疑似 UB-DCE（真缺陷候选，%d 个）──'
                       % len(colA))
            if colA:
                hdr.append('     %-64s %s' % ('文件', '下降的符号×次数'))
                for rel, d, fh in colA:
                    hdr.append('     %-64s %s' % (rel, ' '.join(
                        '%s×%d' % (k, v) for k, v in sorted(d.items()))))
                    hdr.append('       %s' % fh)
                    hdr.append('       ⇒ 判定规则：Δ 符号写入的栈槽若在上列被读槽中 = 真缺陷；'
                               '不在其中 = 合法（次数下降来自 CSE/常量折叠）')
            else:
                hdr.append('     （无）')
            hdr.append('')
            hdr.append('  ── 栏 B：工厂侧**无**块读实参 ⇒ 疑似合法 CSE/常量折叠（%d 个）──'
                       % len(colB))
            if colB:
                hdr.append('     %-64s %s' % ('文件', '下降的符号×次数'))
                for rel, d, _fh in colB:
                    hdr.append('     %-64s %s' % (rel, ' '.join(
                        '%s×%d' % (k, v) for k, v in sorted(d.items()))))
            else:
                hdr.append('     （无）')
            hdr.append('')
            hdr.append('   ★ 次数下降的三个来源：(a) UB-DCE 真缺陷（-Os 删掉被块读函数间接读的槽写入）；')
            hdr.append('     (b) 合法 CSE/常量折叠；(c) 残余的码生成策略差（已由「物化点」归一大幅消减）。')
            hdr.append('   ★ 本门禁**恒返回 0**：它是分诊清单，不是硬门禁；硬门禁是上面的集合级 Δ。')
            hdr.append('')
        else:
            hdr.append('【结论】无引用次数下降 ⇒ 通过')
            hdr.append('')
        hdr.append('【全部明细】')
        txt = '\n'.join(hdr + lines) + '\n'
        sys.stdout.write(txt)
        if a.out:
            os.makedirs(os.path.dirname(a.out), exist_ok=True)
            open(a.out, 'w', encoding='utf-8').write(txt)
        if skipped:
            print('\n  （跳过 = 编译失败，不属于本门禁职责）')
        return 0

    for p in files:
        rel = os.path.relpath(p, ROOT).replace(os.sep, '/')
        aa, cc = delta_of(p, tmpd)
        if aa is None:
            skipped.append(rel)
            continue
        d = sorted(aa - cc)
        allow = set(ALLOW.get(rel, ([], ''))[0])
        real = [x for x in d if x not in allow]
        hint = ub_hint(p) if d else False
        fh = factory_blockread_hint(rel) if (d and factory_hint) else None
        if real:
            hits.append((rel, real, hint, fh))
        lines.append('%-70s Δ=%-3d %s%s%s' % (
            rel, len(d), '[UB?] ' if hint else '      ',
            ' '.join(d[:10]),
            ('  <<' + fh + '>>') if fh else ''))

    hdr = ['=' * 96,
           'DCE 引用差门禁（Δ = UNDEF(-O0) 减去 UNDEF(-Os) 的工厂符号）',
           '=' * 96,
           '扫描 %d 个文件；编译失败跳过 %d 个；★ 表外新增 Δ 的文件 %d 个'
           % (len(files), len(skipped), len(hits)),
           '已登记待核债务 %d 条（该表必须缩小，见 GAP 17.00）' % len(ALLOW), '']
    if hits:
        hdr.append('【★ 表外新增 Δ】—— 这些文件里的工厂数据引用在 -Os 下消失了（硬失败）：')
        hdr.append('   %-66s %-6s %s' % ('文件', 'UB?', 'Δ 符号'))
        for rel, d, hint, fh in hits:
            hdr.append('   %-66s %-6s %s' % (rel, '★' if hint else '-', ' '.join(d)))
        hdr.append('')
        hdr.append('   ★ 带 [UB?] 的优先查：源码里有「取局部标量地址 + p = p + n」形态，')
        hdr.append('     这是 C 未定义行为，-Os 会据此删除后续槽的写入（GAP 16.99）。')
        hdr.append('')
        fh_hits = [(rel, fh) for rel, _d, _h, fh in hits if fh]
        if fh_hits:
            hdr.append('   ★★ 工厂侧旁证（factory_fn_stack.py --indirect，R182）：')
            for rel, fh in fh_hits:
                hdr.append('      %s' % rel)
                hdr.append('        %s' % fh)
            hdr.append('      ⇒ Δ 符号若落在上述被块读函数间接读的槽里 = **真缺陷（UB-DCE）**；')
            hdr.append('        旁证为空（工厂侧这些槽无块读实参）才支持"合法 DCE"判定。')
            hdr.append('')
    else:
        hdr.append('【结论】无表外新增 Δ ⇒ 通过（存量债务见下表）')
        hdr.append('')
    hdr.append('【已登记待核债务】')
    hdr.append('   %-66s %s' % ('文件', '理由'))
    for rel in sorted(ALLOW):
        hdr.append('   %-66s %s' % (rel, ALLOW[rel][1]))
        fh = factory_blockread_hint(rel) if factory_hint else None
        if fh:
            # 只陈述事实 + 判定规则，不自动下"需复核"结论：
            # 工厂侧有块读实参 ≠ 该条登记错 —— 要看 Δ 符号写入的**槽**是否被覆盖。
            hdr.append('     %s' % fh)
            hdr.append('     ⇒ 判定规则：Δ 符号写入的栈槽若在上列被读槽中 = 真缺陷（UB-DCE）；'
                       '不在其中 ⇒ 仍支持"合法 DCE"登记')
        elif factory_hint:
            hdr.append('     工厂侧无块读实参 ⇒ 支持"合法 DCE"登记')
    hdr.append('')
    hdr.append('【全部明细】（Δ=0 也列出，便于看出扫描确实跑到了）')
    txt = '\n'.join(hdr + lines) + '\n'
    sys.stdout.write(txt)
    if a.out:
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        open(a.out, 'w', encoding='utf-8').write(txt)
    if skipped:
        print('\n  （跳过 = 编译失败，不属于本门禁职责）')
    return 2 if hits else 0


if __name__ == '__main__':
    sys.exit(main())
