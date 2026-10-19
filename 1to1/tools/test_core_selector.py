#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_core_selector.py —— core_selector 三层判据测试（R197 建 / R202 更新）

为什么必须单独测②③层：
  `core_selector.py` 的全量自检只用真机 135 条跑，而它们**全部命中第①层**
  （filelist.xml 逐 ROM 覆盖）⇒ ②③层一次都没被执行过 ⇒ 它们的正确性**未经任何验证**。
  本测试用**不在 filelist.xml 里**的路径强制走②③层。

★ R202 关键更新：第②层已从 config.xml 多对多表改为**真机 GetCoreIndex 静态 33 项表**
（一对一）。此前测"一对多必须报 AMBIGUOUS"的 6 条用例**全部改为 OK**（真机表已归一），
并新增 6 条专门验证真机表归一结果的用例。

覆盖点：
  · 第①层优先级最高（即使②层有解）；
  · 第②层一对一查真机表（原一对多的 SFC/SMC/GBA/NES/BIN 现在有确定 core）；
  · 第③层 ROM 标识兜底；
  · 第④层三层全未命中报 NONE；
  · ★ 真机表与 config.xml **不同源**的证据：GBA→gpsp（config.xml 里 GBA 无 gpsp）。

用法: python tools/test_core_selector.py   （exit 0 = 全过）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core_selector import CoreSelector, OK, AMBIGUOUS, NONE  # noqa: E402

# (rel_path, rom_id, 期望 status, 期望 core 或 None, 说明)
CASES = [
    # ---- 第①层：优先级最高（真机 filelist.xml 里的真实条目）----
    ('000/kof96.zip', None, OK, 'libemu_fbalpha2012.so', '①层命中：逐 ROM 覆盖'),
    ('002/Batman - Revenge of the Joker (USA) (Proto).zip', None, OK,
     'libemu_snes9x2010.so', '①层命中：含空格/括号的 ROM 名'),
    ('000/blockgal.zip', None, OK, 'libemu_extend.so',
     '①层命中：同名 ZIP 但 filelist 指定 extend（证明①优先于②）'),
    # ---- 第②层：扩展名唯一候选 ⇒ 直接返回 ----
    ('002/UnknownRom.gen', None, OK, 'libemu_md.so', '②层：GEN'),
    ('000/UnknownRom.img', None, OK, 'libemu_pcsx.so', '②层：IMG'),
    ('002/UnknownRom.fds', None, OK, 'libemu_nes.so', '②层：FDS'),
    ('000/UnknownRom.smd', None, OK, 'libemu_md.so', '②层：SMD'),
    ('002/UnknownRom.sgb', None, OK, 'libemu_tgbdual.so', '②层：SGB'),
    # ★ 真机表不含 TOC/MDF/7Z（只在 config.xml）⇒ 走到 NONE
    ('000/UnknownRom.toc', None, NONE, None,
     'R202：TOC 不在真机 33 项表（仅 config.xml）⇒ NONE'),
    ('000/UnknownRom.mdf', None, NONE, None,
     'R202：MDF 不在真机 33 项表（仅 config.xml）⇒ NONE'),
    # ---- ★ R202 新增：真机 GetCoreIndex 表归一结果验证 ----
    #   原 config.xml 一对多，真机表已选确定 core：
    ('002/UnknownRom.sfc', None, OK, 'libemu_sfc.so',
     'R202：SFC→libemu_sfc.so（config.xml 有 3 候选，真机选 sfc）'),
    ('002/UnknownRom.smc', None, OK, 'libemu_sfc.so',
     'R202：SMC→libemu_sfc.so（同上）'),
    ('002/UnknownRom.fig', None, OK, 'libemu_sfc.so',
     'R202：FIG→libemu_sfc.so'),
    ('002/UnknownRom.nes', None, OK, 'libemu_nes.so',
     'R202：NES→libemu_nes.so（config.xml 有 nes/nestopia，真机选 nes）'),
    ('000/UnknownRom.bin', None, OK, 'libemu_md.so',
     'R202：BIN→libemu_md.so（config.xml 有 md/stella/pcsx，真机选 md）'),
    ('004/UnknownRom.gba', None, OK, 'libemu_gpsp.so',
     'R202：★GBA→libemu_gpsp.so（config.xml 里 GBA 只有 mgba/vbam，'
     '真机表选 gpsp ⇒ 两表不同源）'),
    ('004/UnknownRom.gb', None, OK, 'libemu_tgbdual.so',
     'R202：GB→libemu_tgbdual.so（config.xml 有 mgba/tgbdual，真机选 tgbdual）'),
    ('004/UnknownRom.gbc', None, OK, 'libemu_tgbdual.so',
     'R202：GBC→libemu_tgbdual.so'),
    ('000/UnknownRom.a26', None, OK, 'libemu_stella.so',
     'R202：A26→libemu_stella.so（真机表）'),
    ('000/UnknownRom.a78', None, OK, 'libemu_prosystem.so',
     'R202：A78→libemu_prosystem.so'),
    ('000/UnknownRom.iso', None, OK, 'libemu_pcsx.so',
     'R202：ISO→libemu_pcsx.so'),
    ('000/UnknownRom.sms', None, OK, 'libemu_md.so',
     'R202：SMS→libemu_md.so'),
    ('000/UnknownRom.vt3', None, OK, 'libemu_vrt.so',
     'R202：VT3→libemu_vrt.so'),
    ('000/UnknownRom.vt4', None, OK, 'libemu_vrt.so',
     'R202：VT4→libemu_vrt.so'),
    ('000/UnknownRom.conf', None, OK, 'libemu_dosbox.so',
     'R202：CONF→libemu_dosbox.so'),
    # ---- BKP/ZIP 在真机表中 core 为空 ⇒ 走不到②层 ⇒ NONE（或③层兜底）----
    ('009/UnknownRom.bkp', None, NONE, None,
     'R202：BKP 在真机表 core 为空 ⇒ ②不命中、③无 BKP ⇒ NONE'),
    ('009/UnknownRom.zip', None, NONE, None,
     'R202：ZIP 在真机表 core 为空（需先解压看内部文件）⇒ NONE'),
    # ---- 第③层：ROM 标识兜底 ----
    ('009/UnknownRom.qqq', 'SFC', OK, 'libemu_sfc.so',
     '③层：扩展名未登记 ⇒ rom_id=SFC 命中内嵌表'),
    ('009/UnknownRom.qqq', 'GBA', OK, 'libemu_vrt.so',
     '③层：rom_id=GBA（注意与②层 GBA 扩展名的 gpsp 不同，这是标识表→vrt）'),
    ('009/UnknownRom.qqq', 'A26', OK, 'libemu_pcsx.so',
     '③层：rom_id=A26（R192 疑点项，按真机数据返回）'),
    # ---- 第④层：三层全未命中 ⇒ NONE ----
    ('009/UnknownRom.qqq', None, NONE, None, '④层：扩展名与 rom_id 均未登记 ⇒ 报无'),
    ('009/UnknownRom.qqq', 'ZZZ', NONE, None, '④层：rom_id 也不在表内 ⇒ 报无'),
]


def main():
    cs = CoreSelector()
    npass = nfail = 0
    for rel, rid, exp_status, exp_core, note in CASES:
        r = cs.select_core(rel, rom_id=rid)
        ok = (r.status == exp_status)
        if ok and exp_status == OK:
            ok = (r.core == exp_core)
        if ok:
            npass += 1
            print('  ✓ %-52s -> %-10s %s' % (rel[:52], r.status, r.core or '(none)'))
        else:
            nfail += 1
            print('  ✗ %-52s 期望 %s/%s 实得 %s/%s   (%s)' % (
                rel[:52], exp_status, exp_core, r.status, r.core or '(none)', note))
    print()
    print('=== 结果: pass=%d fail=%d / %d ===' % (npass, nfail, len(CASES)))
    if nfail:
        return 1
    print('✅ 三层判据全过：①优先 / ②真机表一对一 / ③标识兜底 / ④报无')
    return 0


if __name__ == '__main__':
    sys.exit(main())
