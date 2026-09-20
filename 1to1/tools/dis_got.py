#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dis_got.py —— 最小 ARM32 反汇编器：只解「字面量池 → GOT → 符号名」

为什么需要它（2026-09-20）
------------------------
GAP 16.28 暴露的矛盾：`gr_blit_b` 里 `P->[12] != source->[12]` 的 `P` 到底是谁？
我手算的字面量池地址（0x171cc）**不在** GOT 区间（0x16ef4..0x171ac），
⇒ 要么它是 BSS 里的**指针变量**，要么我 pc 基准取错（ARM 里 `ldr Rd,[pc,#imm]`
与 `add Rd,pc,Rm` 的 pc = **该指令地址 + 8**，差一个 4 字节就全错）。

本工具把这件事变成**确定性**的：逐指令解码，凡遇到
    ldr  rD, [pc, #imm]        ; 取字面量池
    add  rD, pc, rD            ; 转成绝对地址
就按 ARM 语义精确算出目标地址，再用 `.rel.dyn` 把它翻成符号名。

用法
----
    python3 tools/dis_got.py <elf> --func gr_blit_b
    python3 tools/dis_got.py <elf> --addr 0x34fc --size 1184
    python3 tools/dis_got.py <elf> --func video_driver_disp_frame --grep GOT

不依赖任何 ARM 工具链 / 不依赖设备：只读 ELF（PT_LOAD + PT_DYNAMIC + .dynsym）。
"""
from __future__ import annotations

import argparse
import os as _os
import re
import struct
import sys

# ★ 2026-09-20：解码器换成 tools/arm_dis.py 的**完整 ARMv7-A 解码器**。
#   动机：本文件原自带"够用就好"的局部解码器，实测**未识别率 32%**
#   （134511 条指令里 43047 条解不出），漏掉的全是最基本的指令：
#       cmp r0,#0 (1596) · ldr r0,[pc,r0] (932) · mvn r0,#0 (408) · bx lr (164) · lsl r1,r1,#1 (152)
#   后果不是"少显示几行"，而是把下游「逐函数等价性差分」（tools/prop_equiv.py）
#   的助记符相似度判据彻底污染（我们侧一半是 `?` ⇒ 该指标显示"无信息量"）。
#   `arm_dis.py` 带 40 个锚点自证，实测真未识别率 **0.00%**。
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import arm_dis as _arm_dis          # noqa: E402


# ---------------------------------------------------------------- ELF 读取
class Elf:
    def __init__(self, path: str):
        self.d = open(path, "rb").read()
        d = self.d
        (self.phoff,) = struct.unpack_from("<I", d, 28)
        (self.phent,) = struct.unpack_from("<H", d, 42)
        (self.phnum,) = struct.unpack_from("<H", d, 44)
        (self.shoff,) = struct.unpack_from("<I", d, 32)
        (self.shent,) = struct.unpack_from("<H", d, 46)
        (self.shnum,) = struct.unpack_from("<H", d, 48)
        (self.shstrndx,) = struct.unpack_from("<H", d, 62)
        self.loads = []          # (vaddr, off, filesz, memsz, flags)
        dyn_o = dyn_s = None
        for i in range(self.phnum):
            t, o, v, pa, fs, ms, fl, al = struct.unpack_from("<8I", d, self.phoff + i * self.phent)
            if t == 1:
                self.loads.append((v, o, fs, ms, fl))
            elif t == 2:
                dyn_o, dyn_s = o, fs
        self.dyn_o, self.dyn_s = dyn_o, dyn_s
        self.sections = [struct.unpack_from("<10I", d, self.shoff + i * self.shent)
                         for i in range(self.shnum)]
        self.secname = {}
        if self.shstrndx < self.shnum:
            st = self.sections[self.shstrndx][4]
            self.secname = {i: self._cstr(st + s[0]) for i, s in enumerate(self.sections)}
        self._read_dynamic()
        self._read_dynsym()
        self._read_relocs()

    # -- 基础
    def _cstr(self, off: int) -> str:
        k = self.d.index(b"\x00", off)
        return self.d[off:k].decode("utf-8", "replace")

    def v2o(self, v: int):
        for vv, oo, fs, ms, _ in self.loads:
            if vv <= v < vv + max(fs, ms):
                return oo + (v - vv)
        return None

    def o2v(self, o: int):
        for vv, oo, fs, ms, _ in self.loads:
            if oo <= o < oo + fs:
                return vv + (o - oo)
        return None

    def rd32(self, v: int):
        o = self.v2o(v)
        if o is None or o + 4 > len(self.d):
            return None
        return struct.unpack_from("<I", self.d, o)[0]

    # -- .dynamic
    def _read_dynamic(self):
        self.dyn = {}
        if self.dyn_o is None:
            return
        for j in range(self.dyn_s // 8):
            tag, val = struct.unpack_from("<iI", self.d, self.dyn_o + j * 8)
            self.dyn.setdefault(tag, val)

    # -- .dynsym（用节表；实测该 DSO 节表里没有 .dynsym 的名字但有 SHT_DYNSYM 段）
    def _read_dynsym(self):
        idx = None
        for i, s in enumerate(self.sections):
            if s[1] == 11:                      # SHT_DYNSYM
                idx = i
                break
        self.syms = {}
        self.sym_by_addr = {}
        if idx is None:
            return
        sym = self.sections[idx]
        stro = self.sections[sym[6]][4]
        es = sym[9] or 16
        for j in range(sym[5] // es):
            nmn, val, sz, inf, oth, shx = struct.unpack_from("<IIIBBH", self.d, sym[4] + j * es)
            if nmn == 0:
                continue
            n = self._cstr(stro + nmn)
            self.syms[n] = (val, sz, shx, inf)
            if shx != 0:
                self.sym_by_addr.setdefault(val, n)

    # -- .rel.dyn + .rel.plt（★ 必须同时读！实测该 DSO 的 PLT 重定位全在 DT_JMPREL，
    #    只读 DT_REL 会得到"PLT 目标全部未知"的假象 —— 2026-09-20 踩过）
    def _read_relocs(self):
        self.rel = {}
        pairs = [
            (self.dyn.get(17), self.dyn.get(18), self.dyn.get(19) or 8),   # DT_REL/RELSZ/RELENT
            (self.dyn.get(23), self.dyn.get(2), self.dyn.get(20) or 17),   # DT_JMPREL/PLTRELSZ/PLTREL
        ]
        for r_off, r_sz, r_ent in pairs:
            if not (r_off and r_sz):
                continue
            o = self.v2o(r_off)
            if o is None:
                continue
            ent = 8 if r_ent in (17, 0) else (16 if r_ent == 18 else 8)
            for j in range(r_sz // ent):
                off, info = struct.unpack_from("<II", self.d, o + j * ent)
                self.rel[off] = ((info >> 8) & 0xFFFFFF, info & 0xFF)
        # 反向：符号序号 → 名
        idx = next((i for i, s in enumerate(self.sections) if s[1] == 11), None)
        self.symname = {}
        if idx is not None:
            sym = self.sections[idx]
            stro = self.sections[sym[6]][4]
            es = sym[9] or 16
            for j in range(sym[5] // es):
                nmn, *_ = struct.unpack_from("<IIIBBH", self.d, sym[4] + j * es)
                self.symname[j] = self._cstr(stro + nmn) if nmn else "*ABS*"

    def rel_sym(self, addr: int):
        e = self.rel.get(addr)
        if e is None:
            return None
        return self.symname.get(e[0], "?"), e[1]


# ---------------------------------------------------------------- 解码子集
RN = {13: "sp", 11: "fp", 15: "pc", 9: "sb", 10: "sl", 12: "ip"}
def r(n: int) -> str:
    return RN.get(n, "r%d" % n)


def rot_imm(w: int) -> int:
    """数据处理的**旋转立即数**：imm12 = (rotate<<8)|imm8，值 = ror(imm8, 2*rotate)。

    ★ 忘了这一步会得到**看似合理但完全错误**的数字（本项目 2026-09-20 踩过）：
      `add ip, pc, #0x600`（rotate=6,imm8=0）其实加的是 **0**；
      `add ip, ip, #0xA15`（rotate=0xA,imm8=0x15）其实加的是 **0x15000**。
      当时据此把 PLT 目标算成 0x30A9（未对齐、落在 .text 里）而误判"这不是 PLT"。
    """
    imm8 = w & 0xFF
    rot = ((w >> 8) & 0xF) * 2
    return ((imm8 >> rot) | (imm8 << (32 - rot))) & 0xFFFFFFFF if rot else imm8


def dec(w: int, addr: int, elf: Elf):
    """**兼容入口**：转发到 `tools/arm_dis.py` 的完整解码器。

    保留本函数（而不是让调用方直接 import arm_dis）的原因：
      `dis_assemble()` 与若干下游工具都用 `dec(w, addr, elf) -> (text, note)` 签名，
      且**同时**用它做 GOT 解算 —— 正则依赖两种精确文本形态：
          ldr rD, [pc, #imm]        （字面量池取址）
          add rD, pc, rM            （池值 + pc ⇒ 绝对地址）
      `arm_dis.dec()` 保证输出这两种形态（有专门的锚点覆盖）。

    历史：本函数曾是局部实现，未识别率 32%，2026-09-20 弃用（改为转发）。
    """
    return _arm_dis.dec(w, addr, elf)


def dis_assemble(elf: Elf, start: int, size: int, resolve_got: bool = True):
    lines = []
    pending = {}          # rD -> (pool_addr, pool_val, src_addr)
    for off in range(0, size, 4):
        addr = start + off
        o = elf.v2o(addr)
        if o is None:
            break
        w = struct.unpack_from("<I", elf.d, o)[0]
        mn, note = dec(w, addr, elf)

        # 记录 ldr rD,[pc,#imm]
        if mn.startswith("ldr ") and "[pc," in mn:
            rd = int(re.search(r"ldr r(\d+)", mn).group(1))
            # ★ 必须容忍**负偏移**（`ldr rD, [pc, #-4]`）：新解码器 arm_dis 会输出符号，
            #   旧正则 `#(\d+)` 在负偏移上 group(1) 为 None ⇒ AttributeError 直接崩（实测踩过）。
            _m = re.search(r"#(-?\d+)", mn)
            imm = int(_m.group(1)) if _m else 0
            tgt = (addr + 8 + imm) & ~3
            val = elf.rd32(tgt)
            pending[rd] = (tgt, val, addr)
        # 记录 add rD, pc, rD
        elif mn.startswith("add r") and ", pc, r" in mn:
            m2 = re.search(r"add r(\d+), pc, r(\d+)", mn)
            rd, rm = int(m2.group(1)), int(m2.group(2))
            if rm in pending and pending[rm][1] is not None:
                target = (addr + 8) + pending[rm][1]
                sym = elf.rel_sym(target)
                nm2 = elf.sym_by_addr.get(target)
                tag = []
                if nm2:
                    tag.append("= &%s" % nm2)
                if sym:
                    tag.append("[rel → %s type=%d]" % sym)
                if target in elf.rel:
                    tag.append("(GOT 项)")
                else:
                    # 落在哪个 BSS/数据符号区间？
                    best = None
                    for n3, (v3, sz3, shx3, _) in elf.syms.items():
                        if v3 <= target < v3 + max(sz3, 1):
                            best = (n3, v3, sz3)
                    if best:
                        tag.append("落在 %s(0x%x,size=%d) 内 +%d" % (
                            best[0], best[1], best[2], target - best[1]))
                    else:
                        tag.append("无重定位、不在已知符号内")
                note = (note + " | " if note else "") + "⇒ 池值 0x%x ⇒ 绝对 0x%x %s" % (
                    pending[rm][1], target, " ".join(tag))
                pending.pop(rm, None)
        lines.append((addr, w, mn + (("  ; " + note) if note else "")))
    return lines


def find_xref(elf: Elf, target: int):
    """找所有可能引用 `target` 的指令：
    ① ldr/str rX,[rY,#imm]，imm == target & 0xFFF（基址寄存器模式，常见于 `base+off`）
    ② ldr Rd,[pc,#imm] 后紧随 add Rd,pc,Rd ⇒ 绝对地址 == target（池里放**偏移**）
    ③ 池里直接放绝对地址 target（`ldr Rd,[pc,#imm]` 取到 == target，再 ldr 一次）
    返回 [(addr, kind, text)]
    """
    imm = target & 0xFFF
    hits = []
    text_v = None
    for v, o, fs, ms, fl in elf.loads:
        if fl & 0x1:                       # 可执行
            text_v = (v, o, fs)
            break
    if not text_v:
        return hits
    v0, o0, fs = text_v
    for off in range(0, fs - 8, 4):
        addr = v0 + off
        w = struct.unpack_from("<I", elf.d, o0 + off)[0]
        # ① 基址寄存器模式
        if (w & 0x0F000000) == 0x05000000 and (w & 0xFFF) == imm:
            m = "ldr" if (w & 0x00100000) else "str"
            rd, rn = (w >> 12) & 0xF, (w >> 16) & 0xF
            if rn != 15:
                hits.append((addr, "basereg", "%s %s, [%s, #0x%x]" % (m, r(rd), r(rn), imm)))
        # ② 池放偏移（ldr pc 相对 + add pc）
        if (w & 0x0FFF0000) == 0x059F0000:
            rd = (w >> 12) & 0xF
            pool = (addr + 8 + (w & 0xFFF)) & ~3
            val = elf.rd32(pool)
            if val is None:
                continue
            # 后面的 add Rd, pc, Rd
            for step in (4, 8):
                w2 = struct.unpack_from("<I", elf.d, o0 + off + step)[0] if off + step + 4 <= fs else 0
                if w2 == (0xE08F0000 | (rd << 12) | rd):
                    abs_ = (addr + step + 8) + val
                    if abs_ == target:
                        hits.append((addr, "pc+pool", "ldr r%d,[pc,#%d]; add r%d,pc,r%d ⇒ 0x%x"
                                     % (rd, w & 0xFFF, rd, rd, abs_)))
                    break
        # ③ 池里放绝对地址
        if (w & 0x0FFF0000) == 0x059F0000:
            pool = (addr + 8 + (w & 0xFFF)) & ~3
            if elf.rd32(pool) == target:
                hits.append((addr, "abs-in-pool", "ldr r%d,[pc,#%d] 池值 == 0x%x"
                             % ((w >> 12) & 0xF, w & 0xFFF, target)))
    return hits


def enclosing_sym(elf: Elf, addr: int):
    best = None
    for n, (v, sz, shx, inf) in elf.syms.items():
        if (inf & 0xF) == 2 and v <= addr < v + max(sz, 1):
            if best is None or v > best[1]:
                best = (n, v, sz)
    return best


def dump_plt(elf: Elf, lo: int, hi: int):
    """解 PLT 桩。实测形态（RK3036G 的 driver.so，gcc -fpic）：

        0x1a08:  e28fc600  add ip, pc, #0        ; ★ 旋转立即数（imm8=0 ⇒ 加 0）
        0x1a0c:  e28cca15  add ip, ip, #0x15000  ; ★ 旋转立即数（rotate=0xA）
        0x1a10:  e5bcf684  ldr pc, [ip, #0x684]! ; ⇒ 目标 = ip + 0x684

    每桩 16 字节，`N` 每桩递减 8 ⇒ 目标地址每桩 +8（4 对齐）。
    """
    rows = []
    for v, o, fs, ms, fl in elf.loads:
        if not (fl & 0x1):
            continue
        addr = lo
        while addr < min(hi, v + fs) - 12:
            off = o + (addr - v)
            w1 = struct.unpack_from("<I", elf.d, off)[0]
            # add ip, pc, #imm   (Rd=ip=12, Rn=pc=15)
            if (w1 & 0xFFFFF000) == 0xE28FC000:
                ip = (addr + 8) + rot_imm(w1)
                w2 = struct.unpack_from("<I", elf.d, off + 4)[0]
                # add ip, ip, #imm  (Rd=Rn=ip)
                if (w2 & 0xFFFFF000) == 0xE28CC000:
                    ip += rot_imm(w2)
                else:
                    addr += 4
                    continue
                w3 = struct.unpack_from("<I", elf.d, off + 8)[0]
                # ldr pc, [ip, #imm]!  即 (w & 0xFFFFF000) == 0xE5BCF000
                if (w3 & 0xFFFFF000) == 0xE5BCF000:
                    tgt = ip + (w3 & 0xFFF)
                    sym = elf.rel_sym(tgt)
                    rows.append((addr, tgt, (sym[0] if sym else None)))
                    addr += 12          # ★ 桩长 12 字节（add/add/ldr pc）；跳 16 会漏掉一半
                    continue
            addr += 4
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("elf")
    ap.add_argument("--func")
    ap.add_argument("--addr", type=lambda x: int(x, 0))
    ap.add_argument("--size", type=int, default=0)
    ap.add_argument("--grep", default=None, help="只打印含该子串的行")
    ap.add_argument("--rel", action="store_true", help="顺便打印 GOT 重定位表")
    ap.add_argument("--pltrange", default=None, help="a:b 十六进制范围，解 PLT 桩")
    ap.add_argument("--xref", type=lambda x: int(x, 0), default=None,
                    help="找所有引用该地址的指令（③ 种模式）")
    a = ap.parse_args()

    e = Elf(a.elf)
    print("ELF: %s  (%d B)" % (a.elf, len(e.d)))
    for v, o, fs, ms, fl in e.loads:
        print("  PT_LOAD vaddr=0x%-7x off=0x%-7x filesz=0x%-7x memsz=0x%-7x flags=0x%x" % (v, o, fs, ms, fl))
    print("  DT_REL=%s DT_RELSZ=%s 重定位 %d 条  符号 %d 个" % (
        hex(e.dyn.get(17, 0)), e.dyn.get(18), len(e.rel), len(e.syms)))

    if a.pltrange:
        lo, hi = (int(x, 16) for x in a.pltrange.split(":"))
        print("\n=== PLT 桩 %x..%x ===" % (lo, hi))
        for addr, got, sym in dump_plt(e, lo, hi):
            print("  PLT 0x%06x → GOT 0x%06x → %s" % (addr, got, sym or "（未知）"))
        return 0

    if a.xref is not None:
        print("\n=== xref 0x%x ===" % a.xref)
        hits = find_xref(e, a.xref)
        for addr, kind, txt in hits:
            sym = enclosing_sym(e, addr)
            print("  0x%06x [%-11s] %-52s %s" % (
                addr, kind, txt, ("∈ %s+0x%x" % (sym[0], addr - sym[1])) if sym else ""))
        print("  共 %d 处" % len(hits))
        return 0

    if a.rel:
        print("\n=== R_ARM_GLOB_DAT(21)/ABS32(2) 重定位（GOT 项 → 符号）===")
        for off in sorted(e.rel):
            si, ty = e.rel[off]
            if ty in (21, 2, 1):
                print("  GOT/池 0x%-7x type=%-3d → %s" % (off, ty, e.symname.get(si, "?")))

    start, size = a.addr, a.size
    if a.func:
        if a.func not in e.syms:
            print("!! 找不到符号 %s" % a.func)
            return 2
        v, sz, shx, inf = e.syms[a.func]
        start, size = v, (size or sz)
    if start is None:
        ap.error("需要 --func 或 --addr")
    if not size:
        size = 256

    print("\n=== 反汇编 0x%x .. 0x%x（%d 字节）===" % (start, start + size, size))
    for addr, w, txt in dis_assemble(e, start, size):
        if a.grep and a.grep not in txt:
            continue
        print("  0x%06x  %08x  %s" % (addr, w, txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
