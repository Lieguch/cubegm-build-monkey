#!/usr/bin/env python3
# 第 152 轮：验收 -fno-builtin-malloc 之前必须排除的**假收敛**风险。
#
# ## 背景
# flag 腿 batch 报 `_ZN6TUnzip5CloseEv` 也收敛（基线 F=[] O=['free'] → flag PASS）。
# 但我们**只重编了 TestLibz0.c**；TUnzip::Close 在 unzip.cpp 里，代码一个字没改。
# 它的 calls_ext 从 ['free'] 变成 [] 只有两种可能：
#   (a) 真收敛 —— 不可能，代码没变；
#   (b) **PLT 名字解析塌了/漂了**（第 150 轮的回归就是这个味道：
#       plt_map 变小 ⇒ calls_ext 变空 ⇒ 假 PASS）。
# 本脚本把 (b) 钉死：比较基线产物与 flag 产物的 plt_map 规模与逐项名字。
#
# ## 原理（为什么真的可能漂）
#   diff_exec.Bin._build_plt() 用「.plt 里的 `ldr pc,[..]` 位置」与「.rel.plt 顺序」
#   **位置配对**。.plt 槽地址由链接脚本定（不动），但 .rel.plt 的**顺序**由
#   「对象顺序 + 对象内重定位顺序」决定。TestLibz0.o 少一个 calloc 重定位 ⇒
#   其后所有槽的名字**整体错位一格** ⇒ 别的函数的 calls_ext 名字被换掉 ⇒ 假收敛/假发散。
#
# 用法: python3 tools/_r152_pltprobe.py <基线elf> <flag elf> [工厂elf]
import sys

sys.path.insert(0, "tools")
import diff_exec  # noqa: E402

BASE = sys.argv[1]
FLAG = sys.argv[2]
FACT = sys.argv[3] if len(sys.argv) > 3 else "golden/factory.rkgame.bin"

bb = diff_exec.Bin(BASE)
ff = diff_exec.Bin(FLAG)

print("== ① 两侧 plt_map 规模与逐项对比 ==")
print("  base.elf plt_map = %d  (lo=%s hi=%s)" % (len(bb.plt_map), bb.plt_lo, bb.plt_hi))
print("  flag.elf plt_map = %d  (lo=%s hi=%s)" % (len(ff.plt_map), ff.plt_lo, ff.plt_hi))
print("  两侧 plt_map **逐项相同** = %s" % (bb.plt_map == ff.plt_map))
if bb.plt_map != ff.plt_map:
    kb, kf = list(bb.plt_map), list(ff.plt_map)
    only_base = [hex(k) for k in kb if k not in ff.plt_map]
    only_flag = [hex(k) for k in kf if k not in bb.plt_map]
    print("  仅 base 有的槽 = %s" % only_base[:12])
    print("  仅 flag  有的槽 = %s" % only_flag[:12])
    drift = [(hex(k), bb.plt_map[k], ff.plt_map[k])
             for k in bb.plt_map if k in ff.plt_map and bb.plt_map[k] != ff.plt_map[k]]
    print("  ★ 同地址名字漂移槽数 = %d / 共有 %d" % (len(drift), len([k for k in bb.plt_map if k in ff.plt_map])))
    for d in drift[:20]:
        print("      %s : base=%-28s flag=%s" % d)

print("")
print("== ② 工厂侧 plt_map（参照）==")
try:
    tt = diff_exec.Bin(FACT)
    print("  factory   plt_map = %d" % len(tt.plt_map))
    sn = set(bb.plt_map.values()) | set(ff.plt_map.values())
    print("  工厂名字集合 ⊇ 我方名字集合 = %s" % (set(tt.plt_map.values()) >= sn))
    print("  我方有、工厂无的名字 = %s" % sorted(sn - set(tt.plt_map.values()))[:12])
except Exception as e:
    print("  factory 读取失败: %s" % e)

print("")
print("== ③ 两个关键函数在两侧的地址/尺寸（确认代码本身没动）==")
for nm in ("TestLibz0", "_ZN6TUnzip5CloseEv"):
    for tag, b in (("base", bb), ("flag", ff)):
        s = b.funcs.get(nm)
        if s is None:
            print("  %-22s %s = < funcs 里没有>" % (nm, tag))
        else:
            print("  %-22s %s addr=0x%08x size=%d" % (nm, tag, s[0], s[1]))

print("")
print("== ④ 用符号地址反查两侧 PLT 名字（模拟 calls_ext 的解析路径）==")
for nm in ("TestLibz0", "_ZN6TUnzip5CloseEv"):
    for tag, b in (("base", bb), ("flag", ff)):
        s = b.funcs.get(nm)
        if s is None:
            continue
        lo, hi = s[0], s[0] + s[1]
        hits = []
        for ins in diff_exec._MD.disasm(b.raw[0:0], 0):
            break
        # 直接扫 .text 里落在 [lo,hi) 的 bl 指令
        txt = b.elf.get_section_by_name('.text')
        if txt is None:
            continue
        toff, tsz, taddr = txt['sh_offset'], txt['sh_size'], txt['sh_addr']
        body = b.raw[toff:toff + tsz]
        for ins in diff_exec._MD.disasm(body, taddr):
            if not (lo <= ins.address < hi):
                continue
            if ins.mnemonic != 'bl':
                continue
            tgt = int(ins.op_str.replace(' ', '').lstrip('#'), 16)
            nm2 = b.plt_name(tgt)
            if nm2:
                hits.append((ins.address, nm2))
        print("  %-22s %s 命中 PLT 的 bl = %s" % (nm, tag, [(hex(a), n) for a, n in hits]))

print("")
print("== 判据 ==")
print("  · 若 ① 显示 flag 侧 plt_map 名字漂移 ⇒ _ZN6TUnzip5CloseEv 的收敛是**假 PASS**，")
print("    且说明 .rel.plt 顺序一变全表漂 ⇒ 必须先修 _build_plt（P1）再谈采纳。")
print("  · 若两侧 plt_map 逐项相同 ⇒ 收敛另有来源，需继续追。")
