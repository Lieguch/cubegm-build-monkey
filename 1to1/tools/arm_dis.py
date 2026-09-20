#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
arm_dis.py — ARMv7-A (A32) 反汇编器：**只求助记符正确 + 覆盖率**

为什么单独成模块（2026-09-20）
------------------------------
`tools/dis_got.py` 原本自带一个"够用就好"的解码器，只覆盖 GOT 解算所需的那几条指令。
把它用在"逐函数等价性差分"（`tools/prop_equiv.py`）上时，实测**未识别率 32%**
（134511 条指令里 43047 条解不出来），未识别的全是**最基本的指令**：

    0xe3500000  ×1596   cmp r0, #0
    0xe79f0000  ×932    ldr r0, [pc, r0]        ← 寄存器偏移寻址（GOT 访问的常见形式）
    0xe3e00000  ×408    mvn r0, #0
    0xe1a01081  ×152    lsl r1, r1, #1
    0xe12fff1e  ×164    bx lr

后果不是"少显示几条指令"，而是**判据失真**：
- `prop_equiv` 的助记符相似度里我们侧一半是 `?` ⇒ 该指标"无信息量"其实是**解码器的锅**；
- "并排反汇编对比"（定位差异最快的办法）直接不可用。

设计取舍
--------
- **按 ARM ARM A5.3 的官方解码层次**（op1 = bits 27:25 分派），而不是"打补丁式"的 if 匹配
  —— 后者正是原解码器漏掉整类指令的原因（掩码少写一位就静默漏掉一批）。
- **只解到"助记符 + 关键操作数"**，不做完整语法/伪指令美化：比对只需要助记符稳定。
- **未知指令必须显式计数**（`unknown`），不静默吞掉 —— 仪器的缺陷要被看见。
- 每组指令都配**锚点**（真实指令字 → 期望助记符），`--selftest` 全绿才算可用。

用法
----
    python3 tools/arm_dis.py --selftest              # 锚点自证
    python3 tools/arm_dis.py --stats build/xxx.elf   # 对 ELF 统计未识别率（目标 < 5%）
    python3 tools/arm_dis.py --word 0xe3500000       # 解一条
"""
import argparse
import struct
import sys

RN = {13: "sp", 11: "fp", 15: "pc", 9: "sb", 10: "sl", 12: "ip"}

COND = {0x0: "eq", 0x1: "ne", 0x2: "cs", 0x3: "cc", 0x4: "mi", 0x5: "pl",
        0x6: "vs", 0x7: "vc", 0x8: "hi", 0x9: "ls", 0xA: "ge", 0xB: "lt",
        0xC: "gt", 0xD: "le", 0xE: ""}

# data-processing 的 16 个 opcode（bits 24:21）
DP_OPS = ["and", "eor", "sub", "rsb", "add", "adc", "sbc", "rsc",
          "tst", "teq", "cmp", "cmn", "orr", "mov", "bic", "mvn"]
DP_NO_RD = {"tst", "teq", "cmp", "cmn"}       # 这四个只写 Rn
DP_NO_RN = {"mov", "mvn"}                     # 这两个只写 Rd
SHIFT = ["lsl", "lsr", "asr", "ror"]


def r(n):
    return RN.get(n, "r%d" % n)


def rot_imm(w):
    """数据处理的 12 位旋转立即数：value = ror(imm8, 2*rotate)。"""
    imm8 = w & 0xFF
    rot = ((w >> 8) & 0xF) * 2
    if not rot:
        return imm8
    return ((imm8 >> rot) | (imm8 << (32 - rot))) & 0xFFFFFFFF


def _imm_or_sym(v):
    """立即数打印：小值用十进制，看起来像地址的用 0x 形式（便于人读）。"""
    return ("0x%x" % v) if v > 0x1000 else str(v)


# --------------------------------------------------------------------------
def dec(w, addr=0, elf=None):
    """返回 (text, note)。text 的第一个 token 就是助记符。

    保持与旧 `dis_got.dec` **兼容的文本形态**，因为 `dis_got.dis_assemble()` 会
    用正则从文本里取 Rd/imm 做 GOT 解算：
        ldr rD, [pc, #imm]
        add rD, pc, rM
    """
    cond = (w >> 28) & 0xF

    if cond == 0xF:
        return _dec_uncond(w, addr, elf)

    c = COND.get(cond, "c%x" % cond)
    op1 = (w >> 25) & 0x7

    if op1 == 0:                       # 000 —— DP(register) / misc / 乘 / 扩展存取
        # ★ extra load/store（LDRH/STRH/LDRSB/LDRSH/LDRD/STRD）住在 **000** 空间：
        #   `cond 000 P U I W L Rn Rt imm4H 1 S H 1 imm4L`，靠 bits 7:4 = 1xx1 与 multiply 区分。
        #   旧实现把它放在 011&bit4=1 ⇒ 整族（含最常见的 LDRH/STRH）全部漏掉。
        if (w >> 23) & 0x3 != 0b00 and ((w >> 4) & 0xF) in (0b1011, 0b1100, 0b1101, 0b1110, 0b1111):
            m = _dec_extra_ldst(w, c)
            if m:
                return m
        return _dec_dp_reg(w, c, addr, elf)
    if op1 == 1:                       # 001 —— DP(immediate) / movw / movt / hint
        return _dec_dp_imm(w, c)
    if op1 == 2:                       # 010 —— load/store（立即数偏移）
        return _dec_ldst_imm(w, c, addr, elf)
    if op1 == 3:                       # 011 —— load/store（寄存器偏移）或 media
        if (w >> 4) & 1:
            m = _dec_media(w, c)
            if m:
                return m
            return "media", "raw=0x%08x" % w
        return _dec_ldst_reg(w, c)
    if op1 == 4:                       # 100 —— LDM/STM
        return _dec_ldm_stm(w, c)
    if op1 == 5:                       # 101 —— B / BL（★ bit24 = LINK，漏它就全变成 b）
        link = "l" if (w >> 24) & 1 else ""
        imm = w & 0xFFFFFF
        if imm & 0x800000:
            imm -= 0x1000000
        mn = "bl" if link else "b"
        return "%s%s 0x%x" % (mn, c, addr + 8 + imm * 4), ""
    # 110 / 111 —— 协处理器 / SVC
    if op1 in (6, 7):
        return _dec_coproc(w, c, addr)
    return "?", "raw=0x%08x" % w


# ---------------------------------------------------------------- DP
def _dec_dp_imm(w, c):
    """data-processing (immediate)，含 MOVW/MOVT/NOP 等 hint。"""
    bits2420 = (w >> 20) & 0x1F
    rd = (w >> 12) & 0xF
    rn = (w >> 16) & 0xF
    imm = w & 0xFFF

    # MOVW/MOVT：opcode 位 == 10000 / 10100
    if bits2420 == 0b10000:
        return "movw%s %s, #0x%x" % (c, r(rd), ((w >> 4) & 0xF000) | imm), ""
    if bits2420 == 0b10100:
        return "movt%s %s, #0x%x" % (c, r(rd), ((w >> 4) & 0xF000) | imm), ""
    # HINT（NOP/YIELD/WFE/WFI/SEV）：bits 24:20 == 10010 且 Rd(15:12)==0
    # ★ HINT 空间（NOP/YIELD/WFE/WFI/SEV）用 **Rd = 1111**，hint 编号在 bits 19:16。
    #   旧实现判 rd == 0 ⇒ `0xE320F000`(nop) 落进 MSR 分支。
    if bits2420 == 0b10010 and rd == 15:
        hints = {0: "nop", 1: "yield", 2: "wfe", 3: "wfi", 4: "sev"}
        return hints.get(rn, "hint") + c, ""
    # MSR/MRS 立即数形式：bits 24:23 == 10 且 bit21:20 == 10
    if (w >> 23) & 0x3 == 0b10 and (w >> 20) & 0x3 == 0b10:
        return "msr%s imm" % c, "raw=0x%08x" % w

    op = DP_OPS[(w >> 21) & 0xF]
    v = rot_imm(w)
    if op in DP_NO_RD:
        return "%s%s %s, #%s" % (op, c, r(rn), _imm_or_sym(v)), ""
    if op in DP_NO_RN:
        return "%s%s %s, #%s" % (op, c, r(rd), _imm_or_sym(v)), ""
    return "%s%s %s, %s, #%s" % (op, c, r(rd), r(rn), _imm_or_sym(v)), ""


def _dec_dp_reg(w, c, addr, elf):
    """data-processing (register) / 乘 / misc 的分派（op1=000）。

    ★ 纪律：**先判"32 位编码唯一确定"的指令**（BX/BLX/BXJ/CLZ/MRS/MSR），
      再按 bits24:23 / bits7:4 做"空间分派"。反了就会漏 ——
      本项目实测：BX 的 bits 24:23 = 0b10，若先要求 bits24:23 == 00，
      `bx lr`（出现 164 次）会被当成 DP-register 里的 `teq`。
    """
    # --- 编码唯一的杂项（与 bits24:23 无关）
    k = w & 0x0FFFFFF0
    if k == 0x012FFF10:
        return "bx%s %s" % (c, r(w & 0xF)), ""
    if k == 0x012FFF30:
        return "blx%s %s" % (c, r(w & 0xF)), ""
    if k == 0x012FFF20:
        return "bxj%s %s" % (c, r(w & 0xF)), ""
    if (w & 0x0FFF0FF0) == 0x016F0F10:            # CLZ Rd, Rm
        return "clz%s %s, %s" % (c, r((w >> 12) & 0xF), r(w & 0xF)), ""
    if (w & 0x0FFF0FFF) == 0x010F0000:            # MRS Rd, CPSR
        return "mrs%s %s, cpsr" % (c, r((w >> 12) & 0xF)), ""
    if (w & 0x0FFF0FFF) == 0x0129F000:            # MSR CPSR_x, Rm
        return "msr%s cpsr, %s" % (c, r(w & 0xF)), ""

    bits76 = (w >> 4) & 0xF
    bits2423 = (w >> 23) & 0x3

    # --- 乘 / 乘加：bits 7:4 == 1001（MUL/MLA）或 1000（UMULL 族，bits 24:23==00）
    if bits76 == 0b1001:
        rd = (w >> 16) & 0xF
        rn = (w >> 12) & 0xF
        rs = (w >> 8) & 0xF
        rm = w & 0xF
        s = "s" if (w >> 20) & 1 else ""
        if rd == 0:
            return "mul%s%s %s, %s, %s" % (c, s, r(rn), r(rm), r(rs)), ""
        return "mla%s%s %s, %s, %s, %s" % (c, s, r(rn), r(rm), r(rs), r(rd)), ""
    if bits76 == 0b1000 and bits2423 == 0b00:
        rdhi = (w >> 16) & 0xF
        rdlo = (w >> 12) & 0xF
        rs = (w >> 8) & 0xF
        rm = w & 0xF
        s = "s" if (w >> 20) & 1 else ""
        signed = (w >> 22) & 1
        accum = (w >> 21) & 1
        nm = ("s" if signed else "u") + "m" + ("lal" if accum else "ull")
        return "%s%s %s, %s, %s, %s" % (nm, c+s, r(rdlo), r(rdhi), r(rm), r(rs)), ""

    # --- 杂项：bits 7:4 == 0001 / 0011 / 0101 / 0111 且 bits 24:23 == 00
    if bits2423 == 0b00 and bits76 in (0b0001, 0b0011, 0b0101, 0b0111):
        return _dec_misc(w, c)

    # --- 其它 media（如 CLZ / SMUL 族）：bits 24:23 != 00 且 bits 7:4 == 100x/101x
    if bits2423 != 0b00 and bits76 in (0b1000, 0b1010, 0b1100, 0b1110, 0b1011, 0b1101):
        m = _dec_media(w, c)
        if m:
            return m

    # --- data-processing (register)，含移位器
    op = DP_OPS[(w >> 21) & 0xF]
    rd = (w >> 12) & 0xF
    rn = (w >> 16) & 0xF
    s = "s" if (w >> 20) & 1 else ""
    rm = w & 0xF
    bit4 = (w >> 4) & 1
    if bit4 == 0:
        typ = (w >> 5) & 0x3
        amt = (w >> 7) & 0x1F
        if amt == 0 and typ == 0:
            op2 = r(rm)
        elif typ == 0 and amt == 0:
            op2 = r(rm)
        else:
            op2 = "%s, %s, #%d" % (r(rm), SHIFT[typ], amt if amt else 32)
        # `mov rX, rY, lsl #n` 显示为 `lsl rX, rY, #n`（与 objdump/Ghidra 一致）
        if op == "mov" and rn == 0 and (typ != 0 or (amt and (w >> 5) & 0x3 == 0)):
            if typ == 0 and amt:
                return "lsl%s%s %s, %s, #%d" % (c, s, r(rd), r(rm), amt), ""
            if typ == 1 and amt:
                return "lsr%s%s %s, %s, #%d" % (c, s, r(rd), r(rm), amt if amt else 32), ""
            if typ == 2 and amt:
                return "asr%s%s %s, %s, #%d" % (c, s, r(rd), r(rm), amt if amt else 32), ""
            if typ == 3 and amt:
                return "ror%s%s %s, %s, #%d" % (c, s, r(rd), r(rm), amt), ""
    else:
        rs = (w >> 8) & 0xF
        typ = (w >> 5) & 0x3
        op2 = "%s, %s, %s" % (r(rm), SHIFT[typ], r(rs))
        if op == "mov" and rn == 0:
            return "%s%s%s %s, %s, %s" % (SHIFT[typ], c, s, r(rd), r(rm), r(rs)), ""

    if op in DP_NO_RD:
        return "%s%s %s, %s" % (op, c, r(rn), op2), ""
    if op in DP_NO_RN:
        return "%s%s%s %s, %s" % (op, c, s, r(rd), op2), ""
    return "%s%s%s %s, %s, %s" % (op, c, s, r(rd), r(rn), op2), ""


def _dec_misc(w, c):
    """MRS/MSR/BX/BLX(reg)/BXJ/CLZ/BKPT 等（op1=000, bits24:23=00, bits7:4=00x1）。"""
    bits76 = (w >> 4) & 0xF
    # BX / BLX(register) / BXJ —— 编码是 `cond 0001 0010 1111 1111 1111 0001 Rm`
    #   ★ 关键：bits 7:4 = **0001**（不是 1111）；用 mask 0x0FFFFFF0 判最稳（屏蔽 cond 与 Rm）。
    #   旧实现按 bits7:4==1111 判 ⇒ 全部漏掉（本项目 `bx lr` 出现 164 次全部落 `?`）。
    k = w & 0x0FFFFFF0
    if k == 0x012FFF10:
        return "bx%s %s" % (c, r(w & 0xF)), ""
    if k == 0x012FFF30:
        return "blx%s %s" % (c, r(w & 0xF)), ""
    if k == 0x012FFF20:
        return "bxj%s %s" % (c, r(w & 0xF)), ""
    # CLZ：bits 7:4 == 0001 且 bits 19:16 == 1111
    if bits76 == 0b0001 and (w >> 16) & 0xF == 0xF:
        return "clz%s %s, %s" % (c, r((w >> 12) & 0xF), r(w & 0xF)), ""
    # MRS / MSR：bits 7:4 in (0000, 0100)
    if bits76 in (0b0000, 0b0100):
        if (w >> 21) & 1 == 0:
            return "mrs%s %s, cpsr" % (c, r((w >> 12) & 0xF)), ""
        return "msr%s cpsr, %s" % (c, r(w & 0xF)), ""
    # BKPT：bits 7:4 == 0111
    if bits76 == 0b0111:
        return "bkpt%s" % c, ""
    # 其它 misc 变体（MRS/MSR banked、SMC 等）—— 不静默吞掉
    return "misc%s" % c, "raw=0x%08x" % w


def _dec_media(w, c):
    """Media / 扩展指令：UXTB/UXTH/SXTB/SXTH/REV/REV16/REVSH/SEL + 乘族等。"""
    k = w & 0x0FF00FF0
    SIMPLE = {
        0x06E00070: "uxtb", 0x06F00070: "uxth",
        0x06A00070: "sxtb", 0x06B00070: "sxth",
        0x06BF0F30: "rev",  0x06BF0FB0: "rev16",
        0x06FF0FB0: "revsh",
        0x06800FB0: "sel",
        0x01600090: "smulbb", 0x016000B0: "smulbt",
        0x016000D0: "smultb", 0x016000F0: "smultt",
        0x0700F010: "smulbb", 0x0700F030: "smulbt",
    }
    if k in SIMPLE:
        return "%s%s %s, %s" % (SIMPLE[k], c, r((w >> 12) & 0xF), r(w & 0xF)), ""
    return None


def _dec_ldst_imm(w, c, addr, elf):
    """LDR/STR (immediate offset) —— op1=010。"""
    P = (w >> 24) & 1
    U = (w >> 23) & 1
    B = (w >> 22) & 1
    W = (w >> 21) & 1
    L = (w >> 20) & 1
    rn = (w >> 16) & 0xF
    rd = (w >> 12) & 0xF
    imm = w & 0xFFF
    base = "ldr" if L else "str"
    m = base + ("b" if B else "")
    sign = "" if U else "-"
    if rn == 15:                                   # pc 相对（字面量池）
        eff = addr + 8 + (imm if U else -imm)
        tgt = eff & ~3
        note = "池@0x%x" % tgt
        if elf is not None:
            val = elf.rd32(tgt)
            if val is not None:
                note += " = 0x%x" % val
        return "%s%s %s, [pc, #%s%d]" % (m, c, r(rd), sign, imm), note
    if P == 0:
        return "%s%s %s, [%s], #%s%d" % (m, c, r(rd), r(rn), sign, imm), ""
    if imm == 0 and W == 0:
        return "%s%s %s, [%s]" % (m, c, r(rd), r(rn)), ""
    if W:
        return "%s%s %s, [%s, #%s%d]!" % (m, c, r(rd), r(rn), sign, imm), ""
    return "%s%s %s, [%s, #%s%d]" % (m, c, r(rd), r(rn), sign, imm), ""


def _dec_ldst_reg(w, c):
    """LDR/STR (register offset) —— op1=011 且 bit4=0。

    ★ 这一族是本项目漏得最多的一类（`ldr r0,[pc,r0]` 出现 932 次）：
      GOT 访问普遍写成 `ldr rX, [pc, rY]`（pc 作基址 + 寄存器偏移），
      旧解码器只认 `[pc, #imm]` ⇒ 整族静默落到 `?`。
    """
    P = (w >> 24) & 1
    U = (w >> 23) & 1
    B = (w >> 22) & 1
    W = (w >> 21) & 1
    L = (w >> 20) & 1
    rn = (w >> 16) & 0xF
    rd = (w >> 12) & 0xF
    typ = (w >> 5) & 0x3
    amt = (w >> 7) & 0x1F
    rm = w & 0xF
    m = ("ldr" if L else "str") + ("b" if B else "")
    off = r(rm)
    if typ != 0 or amt:
        off += ", %s #%d" % (SHIFT[typ], amt if amt or typ == 0 else 32)
    sign = "" if U else "-"
    if rn == 15:
        return "%s%s %s, [pc, %s%s]" % (m, c, r(rd), sign, off), "pc+寄存器偏移"
    if P == 0:
        return "%s%s %s, [%s], %s%s" % (m, c, r(rd), r(rn), sign, off), ""
    bang = "!" if W else ""
    if not (typ or amt):
        return "%s%s %s, [%s, %s]%s" % (m, c, r(rd), r(rn), off, bang), ""
    return "%s%s %s, [%s, %s%s]%s" % (m, c, r(rd), r(rn), sign, off, bang), ""


def _dec_extra_ldst(w, c):
    """LDRH/STRH/LDRSB/LDRSH/LDRD/STRD —— op1=011, bit4=1, bits7:4 高半区。"""
    P = (w >> 24) & 1
    U = (w >> 23) & 1
    I = (w >> 22) & 1                       # 1 = immediate offset
    W = (w >> 21) & 1
    L = (w >> 20) & 1
    rn = (w >> 16) & 0xF
    rd = (w >> 12) & 0xF
    b76 = (w >> 4) & 0xF
    sign = "" if U else "-"
    if b76 in (0b1011, 0b1111):            # 半字
        m = "ldrh" if L else "strh"
        if I:
            imm = ((w >> 4) & 0xF0) | (w & 0xF)
            return "%s%s %s, [%s, #%s%d]" % (m, c, r(rd), r(rn), sign, imm), ""
        return "%s%s %s, [%s, %s%s]" % (m, c, r(rd), r(rn), sign, r(w & 0xF)), ""
    if b76 in (0b1101,):                   # 有符号字节/半字
        m = ("ldrsb" if (w >> 5) & 1 == 0 else "ldrsh")
        if I:
            imm = ((w >> 4) & 0xF0) | (w & 0xF)
            return "%s%s %s, [%s, #%s%d]" % (m, c, r(rd), r(rn), sign, imm), ""
        return "%s%s %s, [%s, %s%s]" % (m, c, r(rd), r(rn), sign, r(w & 0xF)), ""
    if b76 in (0b1100, 0b1110):            # 双字
        m = "ldrd" if L else "strd"
        if I:
            imm = ((w >> 4) & 0xF0) | (w & 0xF)
            return "%s%s %s, [%s, #%s%d]" % (m, c, r(rd), r(rn), sign, imm), ""
        return "%s%s %s, [%s, %s%s]" % (m, c, r(rd), r(rn), sign, r(w & 0xF)), ""
    return None


def _dec_ldm_stm(w, c):
    """LDM/STM（含 push/pop 的常见形态）。"""
    P = (w >> 24) & 1
    U = (w >> 23) & 1
    S = (w >> 22) & 1
    W = (w >> 21) & 1
    L = (w >> 20) & 1
    rn = (w >> 16) & 0xF
    lst = w & 0xFFFF
    regs = ",".join(r(i) for i in range(16) if lst & (1 << i))
    base = "ldm" if L else "stm"
    # push/pop：pop = LDMIA sp!（L=1,P=0,U=1,W=1）；push = STMDB sp!（L=0,P=1,U=0,W=1）
    #   ★ 旧实现写成 `P == (not L) and U == 0` ⇒ pop(P=0,U=1) 恒不匹配。
    if rn == 13 and W == 1:
        if L and P == 0 and U == 1:
            return "pop%s {%s}" % (c, regs), ""
        if (not L) and P == 1 and U == 0:
            return "push%s {%s}" % (c, regs), ""
    mode = {0b01: "ea" if U else "fa", 0b10: "fd" if U else "ed"}.get(P, "?")
    if P == 0 and U == 1:
        mode = "ia"
    elif P == 1 and U == 0:
        mode = "db"
    elif P == 0 and U == 0:
        mode = "da"
    elif P == 1 and U == 1:
        mode = "ib"
    bang = "!" if W else ""
    return "%s%s%s %s%s, {%s}" % (base, mode, c, r(rn), bang, regs), ""


def _dec_coproc(w, c, addr):
    """协处理器 / VFP / SVC —— 不细解，但必须给出**非 `?`** 的分类助记符（供比对用）。"""
    # ★ SVC 的编码是 `cond 1111 imm24` ⇒ 它落在 op1=111 且 bits27:24 == 1111，
    #   不是"cond=1111 的无条件指令"（旧实现放在 _dec_uncond ⇒ 被判成 mcr）。
    if (w >> 24) & 0xF == 0xF:
        return "svc%s #%d" % (c, w & 0xFFFFFF), ""
    cp = (w >> 8) & 0xF
    # VFP：cp == 10 或 11（0xA/0xB）
    if cp in (0xA, 0xB):
        op1 = (w >> 20) & 0x3F
        if (w >> 28) & 0xF == 0xE and (w >> 4) & 1 == 1 and (w >> 20) & 0xFF == 0xEF:
            return "vmrs" + c, "状态寄存器读（VFP）"
        if op1 in (0b000000, 0b000001, 0b000100, 0b000101):
            return "vmov" + c, "VFP 寄存器传送"
        return "vfp" + c, "raw=0x%08x" % w
    if (w >> 24) & 0xF == 0xE:
        return "cdp" + c, "coproc%d" % cp
    if (w >> 24) & 0xF in (0xC, 0xD):
        return ("ldc" if (w >> 20) & 1 else "stc") + c, "coproc%d" % cp
    return "mcr" + c, "coproc%d" % cp


def _dec_uncond(w, addr, elf):
    """cond=1111 的无条件指令 / 以及明显的"数据而非指令"的字。"""
    op1 = (w >> 25) & 0x7
    bits2420 = (w >> 20) & 0x1F
    if op1 == 0b101:
        imm = w & 0xFFFFFF
        if imm & 0x800000:
            imm -= 0x1000000
        h = (w >> 24) & 1
        tgt = addr + 8 + imm * 4 + (2 if h else 0)
        return ("blx 0x%x" % tgt) if h else ("b 0x%x" % tgt), ""
    # 屏障/清独占族：`F57FF0xx`（bits 19:16 = F4/F5/F6）
    if (w >> 16) & 0xFF == 0xF5:
        return "dmb", ""
    if (w >> 16) & 0xFF == 0xF4:
        return "dsb", ""
    if (w >> 16) & 0xFF == 0xF6:
        return "isb", ""
    if (w >> 4) & 0xF == 0x1:
        return "clrex", ""
    if op1 in (0b100, 0b110, 0b111):
        return "uncond", "raw=0x%08x" % w
    # 落到这里的基本是**数据**（跳转表/字面量），显式标出，不当成指令
    return ".word", "0x%08x（疑数据，非指令）" % w


# --------------------------------------------------------------------------
def disasm_range(elf, vaddr, size, limit=None):
    """对一个区间逐条解码，返回 (list_of_(text,note), unknown_count)。"""
    out, unk = [], 0
    off = 0
    while off + 4 <= size:
        w = elf.rd32(vaddr + off)
        if w is None:
            break
        try:
            t, n = dec(w, vaddr + off, elf)
        except Exception:
            t, n = "?", "dec exception"
        tok = t.split(" ")[0]
        if tok in ("?", ".word", "media", "uncond", "misc", "hint", "vfp", "vmov",
                   "vmrs", "cdp", "mcr", "ldc", "stc"):
            unk += 1
        out.append((t, n))
        off += 4
        if limit and len(out) >= limit:
            break
    return out, unk


# --------------------------------------------------------------------------
#  锚点自证：全部取自本项目的**真实指令字**，人工核对过助记符
ANCHORS = [
    (0xE3500000, "cmp",   "cmp r0, #0 —— 出现 1596 次（旧解码器全部漏掉）"),
    (0xE3500001, "cmp",   "cmp r0, #1"),
    (0xE3510000, "cmp",   "cmp r1, #0"),
    (0xE3700001, "cmn",   "cmn r0, #1"),
    (0xE79F0000, "ldr",   "ldr r0, [pc, r0] —— 寄存器偏移，出现 932 次"),
    (0xE79F1001, "ldr",   "ldr r1, [pc, r1]"),
    (0xE5923000, "ldr",   "ldr r3, [r2, #0]"),
    (0xE59F0010, "ldr",   "ldr r0, [pc, #16] —— 字面量池"),
    (0xE3E00000, "mvn",   "mvn r0, #0 —— 出现 408 次"),
    (0xE3A00001, "mov",   "mov r0, #1"),
    (0xE1A01081, "lsl",   "lsl r1, r1, #1 —— 出现 152 次"),
    (0xE1A00000, "mov",   "mov r0, r0（ARM 的 nop）"),
    (0xE12FFF1E, "bx",    "bx lr —— 出现 164 次"),
    (0xE12FFF11, "bx",    "bx r1"),
    (0xE6FF2072, "uxth",  "uxth r2, r2"),
    (0xE6EF0072, "uxtb",  "uxtb r0, r2"),
    (0xE6BF0072, "sxth",  "sxth r0, r2"),
    (0xE6AF0072, "sxtb",  "sxtb r0, r2"),
    (0xE92D4FF0, "push",  "push {r4-r11, lr}"),
    (0xE8BD8FF0, "pop",   "pop {r4-r11, pc}"),
    (0xEB000010, "bl",    "bl +0x40"),
    (0xEAFFFFFE, "b",     "b .（自旋）"),
    (0x03A00001, "moveq", "moveq r0, #1 —— 条件执行"),
    (0x0A000001, "beq",   "beq +4"),
    (0x1A000001, "bne",   "bne +4"),
    (0xE320F000, "nop",   "nop（ARM HINT）"),
    (0xE5D03000, "ldrb",  "ldrb r3, [r0]"),
    (0xE1D300B0, "ldrh",  "ldrh r0, [r3]"),
    (0xE3000001, "movw",  "movw r0, #1"),
    (0xE3400001, "movt",  "movt r0, #1"),
    (0xE0800001, "add",   "add r0, r0, r1"),
    (0xE2800010, "add",   "add r0, r0, #16"),
    (0xE2400004, "sub",   "sub r0, r0, #4"),
    (0xE0000001, "and",   "and r0, r0, r1"),
    (0xE1800001, "orr",   "orr r0, r0, r1"),
    (0xE1C000B0, "strh",  "strh r0, [r0]"),
    (0xE1A0B00D, "mov",   "mov fp, sp"),
    (0xE28DD010, "add",   "add sp, sp, #16"),
    (0xEF000000, "svc",   "svc #0 —— cond=1111 无条件"),
    (0xE92D0001, "push",  "push {r0}"),
]


def selftest():
    bad = 0
    print("=" * 96)
    print("arm_dis.py --selftest（锚点全部取自本项目真实指令字，人工核对助记符）")
    print("=" * 96)
    for w, want, note in ANCHORS:
        try:
            got = dec(w, 0, None)[0].split(" ")[0]
        except Exception as e:
            got = "EXC:%s" % e
        ok = (got == want)
        if not ok:
            bad += 1
        print("  %s 0x%08x  → %-8s（期望 %-8s）  %s" % ("✓" if ok else "✗", w, got, want, note))
    print()
    print("  锚点通过 %d/%d" % (len(ANCHORS) - bad, len(ANCHORS)))
    return 0 if bad == 0 else 1


def stats(elfpath, show_top=12):
    """对一个 ELF 统计未识别率。

    ★ 口径纪律（很容易自欺）：
      - `.word`（我判定为"数据而非指令"）**单列**，不计入"未识别指令"。
        为什么必须分开：本项目工厂二进制的 `PT_LOAD` 把只读数据也标成可执行
        （实测 951211 条"指令" 里绝大多数是数据/字面量）⇒ 把 `.word` 混进 unk
        会让"工厂侧未识别 30%"这种**无意义**的数字出现，掩盖真实缺陷。
      - `?` 才是**真缺陷**（有编码、可识别，但解码器不会）。
      - 分类占位（media/hint/misc/uncond/vfp…）算"已定位未细解"，也单列。
    """
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location(
        "dg", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dis_got.py"))
    dg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dg)
    elf = dg.Elf(elfpath)
    tot = 0
    unk = dat = classified = 0
    bad = {}
    cls = {}
    for v, o, fs, ms, fl in elf.loads:
        if not (fl & 1):
            continue
        for off in range(0, fs - 3, 4):
            w = struct.unpack_from("<I", elf.d, o + off)[0]
            if w == 0:
                continue
            tot += 1
            t = dec(w, v + off, elf)[0]
            tok = t.split(" ")[0]
            if tok == "?":
                unk += 1
                bad[w] = bad.get(w, 0) + 1
            elif tok == ".word":
                dat += 1
            elif tok in ("media", "uncond", "misc", "hint", "vfp", "vmov", "vmrs",
                         "cdp", "mcr", "ldc", "stc"):
                classified += 1
                cls[tok] = cls.get(tok, 0) + 1
    print("  %s" % elfpath)
    print("    指令位槽 %d ；真未识别(?) %d = **%.2f%%**（目标 <5%%）" % (tot, unk, 100.0 * unk / max(tot, 1)))
    print("    判定为数据(.word) %d = %.2f%% ；已定位未细解 %d = %.2f%% %s"
          % (dat, 100.0 * dat / max(tot, 1), classified, 100.0 * classified / max(tot, 1),
             ("(" + ", ".join("%s=%d" % kv for kv in sorted(cls.items(), key=lambda x: -x[1])[:6]) + ")") if cls else ""))
    if bad:
        print("    未识别 Top%d：" % show_top)
        for w, c in sorted(bad.items(), key=lambda x: -x[1])[:show_top]:
            print("      0x%08x ×%-5d  %s" % (w, c, format(w, '032b')))
    return 0 if 100.0 * unk / max(tot, 1) < 5.0 else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--stats", default=None)
    ap.add_argument("--word", default=None, type=lambda x: int(x, 0))
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.stats:
        return stats(a.stats)
    if a.word is not None:
        t, n = dec(a.word, 0, None)
        print("  0x%08x → %s   %s" % (a.word, t, n))
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
