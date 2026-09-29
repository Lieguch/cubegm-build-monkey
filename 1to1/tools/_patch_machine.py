#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_patch_machine.py —— 把 diff_exec.run_func 的「每次新建 Unicorn」改成「复用执行环境」。

病灶（2026-09-29 实测）：746 函数 × 2 二进制 × 3 组语料 ≈ 4700 个 Unicorn 实例，
  每个 mem_map 数 MB；Unicorn 的 C 侧内存归还 OS 不及时 ⇒ 本机 commit 吃紧时
  直接 MemoryError / UC_ERR_NOMEM（`--limit 5` 就炸，单函数却能过）。

修法（结构性，非补丁）：同一二进制的**段几何 + 模型映射是常量**，每次只变**内容** ⇒
  把 mem_map 提到只做一次，per-call 只：复位寄存器 → 重写段内容/SCRATCH → 模型 reset。
  验证口径：批量汇总必须与改前**逐字相同**（782 / 737 / 40 / 5 / 0）。
"""
import io
import re
import sys

P = 'tools/diff_exec.py'
src = io.open(P, encoding='utf-8').read()

start_anchor = '    mu = Uc(UC_ARCH_ARM, mode)\n'
end_anchor = '    _model.map_regions(mu)\n'

i = src.find(start_anchor)
j = src.find(end_anchor)
if i < 0 or j < 0 or j < i:
    print('!! 定位失败 i=%d j=%d' % (i, j)); sys.exit(1)
j_end = j + len(end_anchor)

NEW = '''    # ★★★ 2026-09-29 结构性修复：**复用执行环境**（几何建一次，内容每次重写）。
    #   病灶（实测）：746 函数 × 2 二进制 × 3 组语料 ≈ **4700 个 Unicorn 实例**，
    #   每个 mem_map 数 MB；Unicorn 的 **C 侧内存归还给 OS 不及时** ⇒ 本机 commit 吃紧时
    #   直接 `MemoryError` / `UC_ERR_NOMEM`（本轮实测：`--limit 5` 就炸，单函数却能过）。
    #   而**同一个二进制**的段几何 + 模型映射是**常量**，每次变的只有**内容** ——
    #   所以正确做法是把 `mem_map` 提出来只做一次，per-call 只重写内容 + 复位寄存器/模型。
    #   ⇒ commit 峰值 ~4700×11 MB → **2×11 MB**；顺带省掉每函数重复的段 mem_write。
    mu, _model = _machine_for(b, mode)
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
    _model.reset(mu)                 # 堆重新涂 0xa5（**不清零**，见 map_regions 注释）+ 状态清零
    # ★ 段内容每次重写：**内容才是变量**，几何不是
    for va, fsz, msz, fl, off in b.segs:
        if fsz:
            mu.mem_write(va, b.raw[off:off + fsz])
        if msz > fsz:
            mu.mem_write(va + fsz, b'\\x00' * (msz - fsz))
    mu.mem_write(SCRATCH, b'\\x00' * SCRATCH_SIZE)
    mu.mem_write(SCRATCH + 0x100, b'A\\x00')
    mu.mem_write(SCRATCH + 0x200, b'core\\x00')

    sp = spans
    d = b.dregion
    ctx = {'insns': 0, 'calls': [], 'w': [], 'r': [],
           'unmodelled': [], 'modelled': []}
    # ★★ 外部调用**语义模型**（GAP 17.16）：原先所有外部调用一律 `r0 = 0`，
    #   对**指针返回型**函数等于"返回 NULL" ⇒ 调用方一解引用就 UC_ERR_READ_UNMAPPED
    #   ⇒ 4 个函数（strupr/get_from_line/myStrrstr/GetFilenameExt）被**仪器**判成发散。
    #   现在两侧共用同一份模型与同一组地址 ⇒ 差异只可能来自被测代码。
''' + '    ' + end_anchor.lstrip()

src = src[:i] + NEW + src[j_end:]

# ---- 插入 _machine_for（放在 run_func 之前） ----
HELPER = '''
# --------------------------------------------------------------------------- #
# ★★★ 2026-09-29：**可复用的执行环境**（几何一次，内容每次重写）
# --------------------------------------------------------------------------- #
_MACHINES = {}


def _machine_for(b, mode):
    """返回 (mu, model)。同一二进制只建**一次**；几何（段/栈/PRNG区/模型区）只 map 一次。

    ★ 为什么必须复用：见 run_func 里 2026-09-29 那段注释（4700 个实例 ⇒ MemoryError）。
    ★ 缓存键带 `id(b)`，并把 `b` **强引用**存在缓存里 ⇒ 防止 id 复用造成串味。
    """
    key = (id(b), mode)
    hit = _MACHINES.get(key)
    if hit is not None and hit[0] is b:
        return hit[1], hit[2]
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
    mu.mem_map(STACK_BASE, STACK_SIZE, 7)
    mu.mem_map(SCRATCH, SCRATCH_SIZE, 7)
    mu.mem_map(SENTINEL & ~0xFFF, 0x1000, 7)
    model = libc_model.Model()
    model.map_regions(mu)
    _MACHINES[key] = (b, mu, model)
    return mu, model


'''

k = src.find('def run_func(')
if k < 0:
    print('!! 找不到 run_func'); sys.exit(1)
# 回退到该函数前的空行边界
k2 = src.rfind('\n\n', 0, k)
src = src[:k2] + '\n' + HELPER + src[k2 + 1:]

io.open(P, 'w', encoding='utf-8', newline='\n').write(src)
print('patched OK')
