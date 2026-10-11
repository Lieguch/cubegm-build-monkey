#!/usr/bin/env python3
# 第 152 轮 P1：把 PLT 名字解析从「.rel.plt 顺序位置配对」换成「GOT 槽地址配对」。
#
# ## 为什么要换（第 150/151 轮遗留）
# 现版 `_build_plt` 靠「.plt 里第 k 个 `ldr pc,[..]` ↔ .rel.plt 第 k 个名字」。
# 这是**位置配对**：任何一条漏认（或多余认出）一个 `ldr pc` ⇒ 后面**全部名字错位**。
# 正确做法：每个 PLT stub 的三条指令**唯一确定它跳的 GOT 地址**，
# 再用 `.rel.plt` 里 `r_offset == GOT地址` 的那条重定位取名字 —— **与顺序无关**。
#
# ## 本脚本 = 先**探**，不改 diff_exec
#   ① 用现版（位置配对）算一份 map；
#   ② 用新法（GOT 地址配对）算一份 map；
#   ③ 逐项比对。**两者必须完全相同**才允许换实现。
#
# ## 新法的指令解码（ARM，两种链接器形态都覆盖）
#   GNU ld stub（12 B）：  add ip,pc,#A ; add ip,ip,#B ; ldr pc,[ip,#C]!
#   lld   stub（16 B）：   add ip,pc,#A ; add ip,ip,#B ; ldr pc,[ip,#C]! ; .word pad
#   ⇒ GOT = (stub+8) + A + B + C        【ARM 的 `add ip,pc,#A` 里 pc = 本指令地址+8】
#   .rel.plt 是 R_ARM_JUMP_SLOT，r_offset 就是 GOT 槽地址 ⇒ 直接配名。
#
# 用法: python3 tools/_r152_plt_got.py <elf> [elf...]
import struct
import sys

sys.path.insert(0, "tools")
import diff_exec  # noqa: E402


def _ror(v, r, bits=32):
    r &= bits - 1
    return ((v >> r) | (v << (bits - r))) & ((1 << bits) - 1)


def arm_imm12(word):
    """ARM 数据处理指令的「immediate + rotate」立即数值。"""
    rot = (word >> 8) & 0xF
    imm8 = word & 0xFF
    return _ror(imm8, rot * 2)


def stub_got(raw, stub_addr):
    """从 stub 的前 3 条字（stub+0/+4/+8）算出它跳的 GOT 地址。返回 None 表示形态不认。"""
    got = None
    for i in range(3):
        off = i * 4
        (word,) = struct.unpack_from("<I", raw, off)
        if word == 0:
            return None
        # add ip, pc, #A   （[27:20]=0x28 ADD-imm, Rn=15(pc), Rd=12(ip), S=0）
        # ★ 掩码必须**保留 [19:16]**（Rn）：第一版掩成 0x0FF0F000 把 Rn 抹掉了，
        #   `add ip,pc,#A` 与 `add ip,ip,#B` 被判成同一条 ⇒ 每根 stub 第一条就走错分支 ⇒ 全军覆没。
        if (word & 0x0FFFF000) == 0x028FC000:
            got = stub_addr + 8 + arm_imm12(word)
            continue
        # add ip, ip, #B   （[27:20]=0x28, Rn=12(ip), Rd=12(ip)）
        if (word & 0x0FFFF000) == 0x028CC000:
            if got is None:
                return None
            got += arm_imm12(word)
            continue
        # ldr pc, [ip, #C](!)  —— 保留 [27:25]=010 / [22]B=0 / [20]L=1 / Rn=12 / Rd=15，
        # 忽略 P[24] U[23] W[21]（正负偏移与是否回写都不影响 GOT 地址）。
        keep = (0b111 << 25) | (1 << 22) | (1 << 20) | (0xC << 16) | (0xF << 12)
        want = (0b010 << 25) | (0 << 22) | (1 << 20) | (0xC << 16) | (0xF << 12)
        if (word & keep) == want:
            if got is None:
                return None
            off12 = word & 0xFFF
            if not (word >> 23) & 1:          # U=0 ⇒ 负偏移
                off12 = -off12
            return got + off12
        return None
    return None


def build_plt_got(binobj):
    """新法：GOT 槽地址 → 名字。"""
    elf = binobj.elf
    plt = elf.get_section_by_name('.plt')
    rel = elf.get_section_by_name('.rel.plt')
    if plt is None or rel is None:
        return {}, "缺 .plt 或 .rel.plt"
    dynsym = elf.get_section_by_name('.dynsym')
    # ① r_offset(=GOT 槽地址) → 符号名
    got2name = {}
    for r in rel.iter_relocations():
        try:
            nm = dynsym.get_symbol(r['r_info_sym']).name
        except Exception:
            nm = '?'
        got2name[int(r['r_offset'])] = nm
    # ② 扫 .plt：用「stub 边界」而非「找 ldr pc」。两种链接器的 stub 都是
    #    从 PLT0 之后开始、每条 12 或 16 B；这里直接**逐字滑窗**找合法 stub 头
    #    （add ip,pc,#A 紧跟 add ip,ip,#B 紧跟 ldr pc,[ip,#C](!)）。
    a0, off, size = plt['sh_addr'], plt['sh_offset'], plt['sh_size']
    body = binobj.raw[off:off + size]
    m = {}
    unknown = 0
    for i in range(0, size - 12 + 1, 4):
        g = stub_got(body[i:i + 12], a0 + i)
        if g is None:
            continue
        nm = got2name.get(g)
        if nm is None:
            unknown += 1
            continue
        # key 与现版一致 = stub 起始地址（现版用 ldr pc 地址 - 8）
        m[a0 + i] = nm
    return m, "未配名的 GOT 地址 %d 个" % unknown if unknown else "全部配名"


def main():
    for path in sys.argv[1:]:
        b = diff_exec.Bin(path)
        print("=" * 70)
        print("%s" % path)
        pos = b.plt_map
        got, note = build_plt_got(b)
        print("  位置配对（现版）: %d 槽" % len(pos))
        print("  GOT 配对（新法）: %d 槽   [%s]" % (len(got), note))
        same = pos == got
        print("  ★ 逐项相同 = %s" % same)
        if not same:
            kp = set(pos)
            kg = set(got)
            only_pos = sorted(kp - kg)
            only_got = sorted(kg - kp)
            print("  仅现版有的 stub = %s" % [hex(x) for x in only_pos[:16]])
            print("  仅新法有的 stub = %s" % [hex(x) for x in only_got[:16]])
            drift = [(hex(k), pos[k], got[k]) for k in sorted(kp & kg) if pos[k] != got[k]]
            print("  ★ 同 stub 名字不同 = %d 条" % len(drift))
            for d in drift[:20]:
                print("      %s : 现版=%-26s 新法=%s" % d)
        # 漏配的 GOT 槽（新法没认出的 stub 形态）也要公示
        nm_pos = set(pos.values())
        nm_got = set(got.values())
        if nm_pos != nm_got:
            print("  ⚠ 名字集合差异：")
            print("     现版独有 = %s" % sorted(nm_pos - nm_got))
            print("     新法独有 = %s" % sorted(nm_got - nm_pos))


if __name__ == '__main__':
    main()
