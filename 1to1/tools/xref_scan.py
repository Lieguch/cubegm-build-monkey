#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARM32(A32) 交叉引用扫描器 —— 解析工厂 rkgame 中「哪个函数引用了哪个数据符号」。

动机
----
工厂二进制是 **PIC 代码**（非 PIE 但用 GOT + PC 相对寻址），因此：

  ① 引用**全局**数据对象时走 GOT：
        ldr  rX, [pc, #n]        ; 取「目标 - 本条 add 的 PC」偏移
        add  rX, pc, rX          ; rX = _GLOBAL_OFFSET_TABLE_ (=0x3b1fc4)
        ldr  rY, [rX, #imm]      ; 或 [rX, rZ]（Z 为 movw/movt 常量）
  ② 引用**同 TU 的 static** 对象时，同骨架但 rX 直接 = 符号地址；
     编译器还会用 `add rB, rB, #imm` 做「基址 + 偏移」二次寻址。

⇒ 单纯 grep 地址**找不到任何引用**（.text 里不存绝对地址）。
   本工具做指令级解析，把两类引用都还原出来。

产出
----
  report/xref.json    : {func_addr: {name,size,direct{addr→names},got{addr→names}}}
  report/xref_dup.txt : 指定重名符号的归属报告
"""
import struct
import json
import os
import sys
import bisect
import collections

# ---------------------------------------------------------------- ELF

def load_elf(path):
    d = open(path, 'rb').read()
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    si = struct.unpack_from('<H', d, 50)[0]
    so = e_shoff + si * es
    stroff = struct.unpack_from('<I', d, so + 16)[0]
    hdr, order = {}, []
    for i in range(n):
        o = e_shoff + i * es
        nm, typ, fl, addr, off, size, link, info, al, ent = struct.unpack_from('<10I', d, o)
        e = d.index(b'\x00', stroff + nm)
        name = d[stroff + nm:e].decode('utf-8', 'replace')
        hdr[name] = dict(addr=addr, off=off, size=size, typ=typ,
                         link=link, entsize=ent, idx=i)
        order.append(name)
    return d, hdr, order


def read_syms(d, hdr, secname):
    h = hdr[secname]
    e_shoff = struct.unpack_from('<I', d, 32)[0]
    es = struct.unpack_from('<H', d, 46)[0]
    strtab_off = struct.unpack_from('<I', d, e_shoff + h['link'] * es + 16)[0]
    ent = h['entsize'] or 16
    out = []
    for j in range(h['size'] // ent):
        o = h['off'] + j * ent
        nm_, val, sz, inf, oth, shndx = struct.unpack_from('<IIIBBH', d, o)
        if nm_ == 0:
            continue
        e = d.index(b'\x00', strtab_off + nm_)
        s = d[strtab_off + nm_:e].decode('utf-8', 'replace')
        out.append((s, val, sz, {0: 'l', 1: 'g', 2: 'w'}.get(inf >> 4, '?'), shndx))
    return out


def rd32(d, hdr, ea):
    for name, h in hdr.items():
        if h['typ'] == 8 or h['size'] == 0:
            continue
        if h['addr'] <= ea < h['addr'] + h['size']:
            o = h['off'] + (ea - h['addr'])
            if o + 4 <= len(d):
                return struct.unpack_from('<I', d, o)[0]
    return None


# ---------------------------------------------------------------- 指令模式（A32）
def is_ldr_pc(ins):
    return (ins & 0x0FFF0000) == 0x059F0000


def ldr_pc_rd_imm(ins):
    return (ins >> 12) & 0xF, ins & 0xFFF


def is_add_pc(ins):
    return (ins & 0x0FFF0FF0) == 0x008F0000


def add_pc_rd_rm(ins):
    return (ins >> 12) & 0xF, ins & 0xF


def is_movw(ins):
    return (ins & 0x0FF00000) == 0x03000000


def is_movt(ins):
    return (ins & 0x0FF00000) == 0x03400000


def movwt_fields(ins):
    imm16 = ((ins >> 16) & 0xF) << 12 | (ins & 0xFFF)
    return (ins >> 12) & 0xF, imm16


def is_add_sub_imm(ins):
    return (ins & 0x0FE00000) in (0x02800000, 0x02400000)


def dp_imm(ins):
    """数据处理的 12 位立即数 = imm8 ROR (2*rot)。★ 直接取 ins&0xFFF 是**错的**
       （0xE2832D25 的 imm12=0xD25，真值 0x940）。"""
    rot = (ins >> 8) & 0xF
    v = ins & 0xFF
    if rot:
        v = ((v >> (2 * rot)) | (v << (32 - 2 * rot))) & 0xFFFFFFFF
    return v


def add_sub_imm_fields(ins):
    sub = (ins & 0x0FE00000) == 0x02400000
    return (ins >> 16) & 0xF, (ins >> 12) & 0xF, dp_imm(ins), sub


def is_add_sub_reg(ins):
    return (ins & 0x0FE00FF0) in (0x00800000, 0x00400000)


def add_sub_reg_fields(ins):
    sub = (ins & 0x0FE00FF0) == 0x00400000
    return (ins >> 16) & 0xF, (ins >> 12) & 0xF, ins & 0xF, sub


def is_ldr_imm(ins):
    return (ins & 0x0F700000) == 0x05100000 and ((ins >> 16) & 0xF) != 15


def is_ldr_reg(ins):
    return ((ins & 0x0F700FF0) == 0x07100000) and ((ins >> 16) & 0xF) != 15


def sdt(ins):
    """解码「单寄存器数据传送」(LDR/STR ±B, 立即数/寄存器偏移)。
       ★ 关键：编译器常以「锚点基址 + 立即数偏移」**直接访存**，
         被访问符号的地址从不进入任何寄存器（例：handle = anchor(0x3cf674) + 0x314）。
         只跟踪 reg_base 会漏掉这一类引用。
       返回 (is_load, rn, rd, imm, rm, U, shift_imm, shift_type) 或 None。"""
    if (ins & 0x0C000000) != 0x04000000:
        return None
    if not ((ins >> 24) & 1):                 # P=1（前索引/偏移）
        return None
    L = (ins >> 20) & 1
    rn = (ins >> 16) & 0xF
    rd = (ins >> 12) & 0xF
    U = (ins >> 23) & 1
    if (ins >> 25) & 1:                       # 寄存器偏移（可带移位）
        if ins & 0x10:                        # bit4=1 是媒体指令/非 LDR 形态
            return None
        return (L, rn, rd, None, ins & 0xF, U, (ins >> 7) & 0x1F, (ins >> 5) & 3)
    return (L, rn, rd, ins & 0xFFF, None, U, 0, 0)


def shift_val(v, sh_imm, sh_type):
    """按移位类型对已知常量做移位（只支持 LSL；其它返回 None）。"""
    if sh_type != 0:
        return None
    return (v << sh_imm) & 0xFFFFFFFF


def is_mov_reg(ins):
    return (ins & 0x0FFF0FF0) == 0x01A00000


# ---- 不写 Rd / 特殊寄存器副作用的指令（★ 漏判的头号来源）----

def is_branch(ins):
    return (ins & 0x0E000000) == 0x0A000000


def is_bl(ins):
    return is_branch(ins) and ((ins >> 24) & 1) == 1


def opcode_hi(ins):
    return (ins >> 21) & 0x7F


def is_compare(ins):
    """CMP/CMN/TST/TEQ —— opcode 0x18..0x1B 且 S=1：**不写任何 Rd**。
       误当成写 Rd 会把 (ins>>12)&0xF（其实是立即数/操作数位）当成目标寄存器清掉。"""
    return opcode_hi(ins) in (0x18, 0x19, 0x1A, 0x1B) and ((ins >> 20) & 1) == 1


def is_ldm_stm(ins):
    return (ins & 0x0E000000) == 0x08000000


def ldm_stm_fields(ins):
    return ((ins >> 20) & 1) == 1, (ins >> 16) & 0xF, ins & 0xFFFF  # (is_load, rn, reglist)


# ---------------------------------------------------------------- 扫描

def parse_funcs(path):
    out = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        p = line.split()
        if len(p) < 3:
            continue
        try:
            out.append((int(p[0], 16), int(p[1]), p[2]))
        except ValueError:
            continue
    out.sort()
    return out


def scan(factory, funcs_path, out_json):
    d, hdr, _ = load_elf(factory)
    text = hdr['.text']
    got = hdr['.got']
    got_lo, got_hi = got['addr'], got['addr'] + got['size']
    M32 = 0xFFFFFFFF

    syms = read_syms(d, hdr, '.symtab')
    addr2sym = collections.defaultdict(list)
    for s, val, sz, b, nd in syms:
        if val:
            addr2sym[val].append((s, sz, b))

    got_slot = {}
    for k in range(got['size'] // 4):
        sl = got_lo + k * 4
        v = struct.unpack_from('<I', d, got['off'] + k * 4)[0]
        if v:
            got_slot[sl] = (v, addr2sym.get(v, []))

    funcs = parse_funcs(funcs_path)
    result = {}
    t_lo, t_hi = text['addr'], text['addr'] + text['size']
    # ★ Ghidra 导出的 function size 会**越过下一个函数**（实测 PlayFrame size=4252 覆盖了
    #   run_process/Load_Proc1）⇒ 边界必须用「下一个函数的入口地址」，不能用 a+size，
    #   否则引用会被归到错误的函数名下。
    starts = [a for a, _, _ in funcs]

    for idx, (a, sz, nm) in enumerate(funcs):
        nxt = starts[idx + 1] if idx + 1 < len(starts) else t_hi
        reg_base = {}      # reg -> 已物化的数据/GOT 基址
        reg_const = {}     # reg -> 已知 32 位常量
        direct = []        # 直接引用（static/PC 相对）
        gotrefs = []       # GOT 中介引用（global）

        def note_base(rd, b):
            b &= M32
            reg_base[rd] = b
            reg_const.pop(rd, None)
            if not (got_lo <= b < got_hi):
                hit = addr2sym.get(b)
                if hit:
                    direct.append((b, hit))

        def probe(rn, off):
            """以 reg_base[rn] 为基址、off 为偏移的一次访存 → 记录它落在哪个符号上。"""
            if rn not in reg_base:
                return
            b = reg_base[rn]
            t = (b + off) & M32
            if got_lo <= b < got_hi:
                if t in got_slot:
                    v, names = got_slot[t]
                    gotrefs.append((t, v, names))
            elif not (got_lo <= t < got_hi):
                hit = addr2sym.get(t)
                if hit:
                    direct.append((t, hit))

        ea = a
        end = min(nxt, t_hi)
        while ea < end:
            ins = struct.unpack_from('<I', d, text['off'] + (ea - t_lo))[0]

            if is_ldr_pc(ins):
                rd, imm = ldr_pc_rd_imm(ins)
                pv = rd32(d, hdr, ea + 8 + imm)
                if pv is not None:
                    reg_const[rd] = pv
                    reg_base.pop(rd, None)

            elif is_add_pc(ins):
                ad, ar = add_pc_rd_rm(ins)
                if ar in reg_const:
                    note_base(ad, (ea + 8) + reg_const[ar])
                else:
                    reg_base.pop(ad, None)

            elif is_movw(ins):
                rd, v = movwt_fields(ins)
                reg_const[rd] = v
                reg_base.pop(rd, None)

            elif is_movt(ins):
                rd, v = movwt_fields(ins)
                reg_const[rd] = ((reg_const.get(rd, 0) & 0xFFFF) | (v << 16)) & M32
                reg_base.pop(rd, None)

            elif is_add_sub_imm(ins):
                rn, rd, imm, sub = add_sub_imm_fields(ins)
                delta = -imm if sub else imm
                if rn in reg_base:
                    note_base(rd, reg_base[rn] + delta)
                elif rn in reg_const:
                    reg_const[rd] = (reg_const[rn] + delta) & M32
                    reg_base.pop(rd, None)
                else:
                    reg_base.pop(rd, None)
                    reg_const.pop(rd, None)

            elif is_add_sub_reg(ins):
                rn, rd, rm, sub = add_sub_reg_fields(ins)
                if rn in reg_base and rm in reg_const:
                    c = reg_const[rm]
                    note_base(rd, reg_base[rn] + (-c if sub else c))
                elif rn in reg_const and rm in reg_const:
                    c = reg_const[rm]
                    reg_const[rd] = (reg_const[rn] + (-c if sub else c)) & M32
                    reg_base.pop(rd, None)
                else:
                    reg_base.pop(rd, None)
                    reg_const.pop(rd, None)

            elif is_mov_reg(ins):
                rd, rm = (ins >> 12) & 0xF, ins & 0xF
                for tbl in (reg_base, reg_const):
                    if rm in tbl:
                        tbl[rd] = tbl[rm]
                    else:
                        tbl.pop(rd, None)

            elif is_bl(ins):
                # bl/blx 只写 lr，并破坏调用者保存寄存器 r0-r3/r12
                for r in (0, 1, 2, 3, 12, 14):
                    reg_base.pop(r, None)
                    reg_const.pop(r, None)

            elif is_branch(ins):
                pass                                  # b/bx：不写任何 GPR

            elif is_compare(ins):
                pass                                  # cmp/cmn/tst/teq：不写 Rd

            elif is_ldm_stm(ins):
                ld, rn, rl = ldm_stm_fields(ins)
                if ld:                                # ldm/pop：列表内寄存器被覆盖
                    for r in range(16):
                        if (rl >> r) & 1:
                            reg_base.pop(r, None)
                            reg_const.pop(r, None)
                # stm/push：只读，状态保留

            else:
                s = sdt(ins)
                if s is not None:
                    L, rn, rd, imm, rm, U, sh, sht = s
                    off = None
                    if rm is None:
                        off = imm if U else -imm
                    elif rm in reg_const:
                        c = shift_val(reg_const[rm], sh, sht)
                        if c is not None:
                            off = -c if not U else c
                    if rn == 15 and off is not None:
                        # ldr Rd, [pc, ±Rm] —— PC 相对 + 寄存器偏移（GCC 常用；
                        #   例：DeinitDisplay 的 dlclose(handle)）
                        t = (ea + 8 + off) & M32
                        hit = addr2sym.get(t)
                        if hit:
                            direct.append((t, hit))
                    elif off is not None:
                        probe(rn, off)
                    if L and rd != 15:          # LDR 写 rd；STR 的 rd 是源，不清状态
                        reg_base.pop(rd, None)
                        reg_const.pop(rd, None)
                elif (ins & 0x0C000000) != 0x04000000:
                    rd_dst = (ins >> 12) & 0xF
                    reg_base.pop(rd_dst, None)
                    reg_const.pop(rd_dst, None)
            ea += 4

        dd, gg = {}, {}
        for b, names in direct:
            dd.setdefault('0x%08x' % b, {'addr': b, 'names': [n for n, _, _ in names]})
        for slot, v, names in gotrefs:
            gg.setdefault('0x%08x' % v, {'addr': v, 'names': [n for n, _, _ in names]})
        result['0x%08x' % a] = {'name': nm, 'size': sz, 'direct': dd, 'got': gg}

    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    return result, addr2sym, got_slot


# ---------------------------------------------------------------- 报告

def report(result, targets, out_txt):
    L = []
    L.append('=' * 100)
    L.append('重名/关键符号交叉引用归属报告（工厂 rkgame，A32 PIC 指令级解析）')
    L.append('=' * 100)
    for tgt_addr, tgt_label in targets:
        users = [(fa, info['name']) for fa, info in result.items()
                 for v in info['direct'].values() if v['addr'] == tgt_addr]
        gusers = [(fa, info['name']) for fa, info in result.items()
                  for v in info['got'].values() if v['addr'] == tgt_addr]
        L.append('')
        L.append('● %-30s @0x%08x' % (tgt_label, tgt_addr))
        L.append('   直接引用(static, PC 相对) %2d 处: %s' %
                 (len(users), ', '.join('%s@%s' % (n, a) for a, n in users) or '—'))
        L.append('   GOT 引用(global)          %2d 处: %s' %
                 (len(gusers), ', '.join('%s@%s' % (n, a) for a, n in gusers) or '—'))
    txt = '\n'.join(L) + '\n'
    with open(out_txt, 'w', encoding='utf-8') as f:
        f.write(txt)
    print(txt)


if __name__ == '__main__':
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    factory = sys.argv[1] if len(sys.argv) > 1 else 'D:/output/rkgame/rkgame'
    funcs = sys.argv[2] if len(sys.argv) > 2 else \
        'D:/output/rkgame/decompiled/01-static/functions.txt'
    res, a2s, gs = scan(factory, funcs, os.path.join(ROOT, 'report', 'xref.json'))
    print('函数数 : %d' % len(res))
    print('直接符号引用点 : %d ；GOT 符号引用点 : %d' % (
        sum(len(v['direct']) for v in res.values()),
        sum(len(v['got']) for v in res.values())))

    TARGETS = [
        (0x3b21c8, 'handle (os_windows_rk.c static)'),
        (0x3cf988, 'handle (EmuRun.c static)'),
        (0x3bc414, 'diff_prev (ui_jkt.c static)'),
        (0x3e1a38, 'diff_prev (GLOBAL)'),
        (0x3ceaf0, 'SoundBuffer (ui_jkt.c static)'),
        (0x3e1944, 'SoundBuffer (GLOBAL)'),
        (0x3ae610, 'ArchivePath (ui_jkt.c static)'),
        (0x3e18d4, 'ArchivePath (GLOBAL)'),
    ]
    report(res, TARGETS, os.path.join(ROOT, 'report', 'xref_dup.txt'))
