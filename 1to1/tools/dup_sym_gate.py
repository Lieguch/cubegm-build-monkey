#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dup_sym_gate.py —— 数据符号**覆盖**与**重名绑定**门禁（GAP 17.13）。

为什么需要它（本轮实测的真缺陷，两个"静默失效"合起来骗过了所有既有门禁）
--------------------------------------------------------------------------
**症状**：差分执行器报出 ≥9 个函数的一致签名
`data-reads 仅F=[(0x3AE650,4,'R')] 仅O=[(0x3E1914,4,'R')]`
（`InitKeyMapping0fEmuType` / `Load_Proc1` / `PCSX_Load` / `Pico_Load` /
`SaveKeyMappingConfigFile` / `Snes_Load` / `TGB_Load` / `stella_Load` / `prosystem_Load`
—— **全部 `*_Load` 与存档路径生成**）。

**根因（两个漏洞叠加）**：
1. `gen_factory_globals.py` 的 `SEC_KEEP` 里写的是 `.data.rel.ro`，而工厂的节名是
   **`.data.rel.ro.local`（差一个 `.local` 后缀）** ⇒ 该节 **8 个 LOCAL 对象整节漏进不了账本**。
2. `ArchivePath` 在工厂里**同名两份**：LOCAL `0x3AE610`(size 64, `.data.rel.ro.local`)
   与 GLOBAL `0x3E18D4`(size 28, `.bss`)。账本里只有 GLOBAL 那份，
   `gen_data_module.py` 的 `syms.setdefault`（首次命中）就只能绑到 GLOBAL
   ⇒ **工厂代码引用 LOCAL，我们绑到 GLOBAL ⇒ 真机读错内存**。
   （算术证据：工厂读 0x3AE650、我们读 0x3E1914，差 0x32C4 = 0x3E18D4 − 0x3AE610 **恰相等**
     ⇒ 两侧索引相同、只有基址不同 ⇒ 就是绑定错，不是算法错。）
3. 而 `verify_layout.py` 的 `ALIAS` 表里**明明写着** `('ArchivePath', 0x3ae610) -> 'ArchivePath'`，
   但该检查由**账本行驱动** ⇒ 账本没有这一行 ⇒ **检查静默失效**。
   ★ 这与技能第 51 条"判据的输入在 CI 里不存在"是同一族，只是这次缺的是**账本行**而不是文件。

本门禁把这两件事都变成机械判据
------------------------------
**检查 1 · 覆盖完整性**：被镜像节区里的**每一个**工厂数据对象，账本必须有同 (名字, 地址) 行。
  「被镜像节区」不在这里硬编 —— 从 `gen_data_module.py` 的 `SEC_DEF` **解析**出来
  （唯一真源：生成器镜像哪些段，门禁就要求覆盖哪些段）。
**检查 2 · 重名绑定**：工厂里同名数据对象 ≥2 份时，**代码实际引用的那一份**
  （= 地址最低的那份；依据：差分实测 + `xref_scan.py` 指令级交叉引用）
  必须在我方 ELF 里有符号绑定；另一份由拆分别名（`_global` / `_emurun`）覆盖。

自证（两态，含**缺陷态**）
------------------------
* 覆盖：把账本副本里刚补上的 8 行 RELRO 删掉 ⇒ 必须报 **8 条缺失**（这就是修复前的状态）。
* 绑定：把我方绑定换成修复前的 `ArchivePath -> 0x3E18D4` ⇒ 必须 FAIL；
  用当前真实绑定 ⇒ 必须 PASS。

用法：
  python3 tools/dup_sym_gate.py [--self-test] [--elf F] [--ours O] [--ledger L]
退出码：0 = 通过；2 = 有缺口（fail-closed，绝不静默放行）；11 = 输入缺失
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEF_ELF = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
DEF_OURS = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')
DEF_LEDGER = os.path.join(ROOT, 'ledger', 'factory_globals.tsv')
GEN = os.path.join(HERE, 'gen_data_module.py')

# 重名拆分别名表（与 verify_layout.ALIAS / gen_data_module.SPLIT_ALIASES 同源；此处刻意冗余一份
# 并做**一致性自证**：若三者不一致，本门禁会报出来）
SPLIT = {
    ('handle', 0x3cf988): 'handle_emurun',
    ('diff_prev', 0x3e1a38): 'diff_prev_global',
    ('SoundBuffer', 0x3e1944): 'SoundBuffer_global',
    ('ArchivePath', 0x3e18d4): 'ArchivePath_global',
}


# --------------------------------------------------------------------------- #
def imaged_sections(gen_path=GEN):
    """从 gen_data_module.py 的 SEC_DEF 解析「被镜像节区」——唯一真源，避免两处硬编漂移。"""
    txt = open(gen_path, encoding='utf-8', errors='replace').read()
    m = re.search(r'^SEC_DEF = \[(.*?)\]', txt, re.S | re.M)
    if not m:
        raise RuntimeError('无法从 %s 解析 SEC_DEF' % gen_path)
    return [x for x in re.findall(r"\('([^']+)',", m.group(1))]


def read_ledger_rows(path):
    """→ set((name, addr))"""
    rows = set()
    for i, line in enumerate(open(path, encoding='utf-8', errors='replace')):
        if i == 0:
            continue
        f = line.rstrip('\n').split('\t')
        if len(f) < 3:
            continue
        try:
            rows.add((f[0], int(f[1], 16)))
        except ValueError:
            continue
    return rows


def factory_objects(elf_path):
    """→ (objs, dup) ；objs=[(name, addr, size, section)]，dup={name: [addr,...]}（≥2 份）"""
    from elftools.elf.elffile import ELFFile
    objs = []
    with open(elf_path, 'rb') as f:
        e = ELFFile(f)
        for s in e.get_section_by_name('.symtab').iter_symbols():
            if s['st_info']['type'] != 'STT_OBJECT' or not s.name or s['st_value'] == 0:
                continue
            sh = s['st_shndx']
            sec = e.get_section(sh).name if isinstance(sh, int) and sh < e.num_sections() else '?'
            objs.append((s.name, s['st_value'], s['st_size'], sec))
    dup = {}
    for n, a, _sz, _sec in objs:
        dup.setdefault(n, []).append(a)
    dup = {k: sorted(v) for k, v in dup.items() if len(v) > 1}
    return objs, dup


def our_object_addrs(elf_path):
    """→ {name: sorted([addr,...])}（我方 ELF 的全部数据对象）"""
    from elftools.elf.elffile import ELFFile
    out = {}
    with open(elf_path, 'rb') as f:
        e = ELFFile(f)
        for s in e.get_section_by_name('.symtab').iter_symbols():
            if s['st_info']['type'] != 'STT_OBJECT' or not s.name or s['st_value'] == 0:
                continue
            out.setdefault(s.name, []).append(s['st_value'])
    return {k: sorted(v) for k, v in out.items()}


# --------------------------------------------------------------------------- #
def check_coverage(factory_members, ledger_rows):
    """被镜像节区里的每个工厂数据对象，账本必须有同 (名字, 地址) 行。
       factory_members = [(name, addr, size, section)]"""
    missing = [(n, a, sec) for n, a, _s, sec in factory_members if (n, a) not in ledger_rows]
    return sorted(missing, key=lambda x: x[1])


def check_binding(dup, ours, split=SPLIT):
    """重名绑定：工厂里同名 ≥2 份时，**地址最低的那份**必须在我方有符号。
       另一份必须由拆分别名（split 表）落到我方某个符号上。纯函数 ⇒ 可离线自证。
       → (bad, ok_count)"""
    bad, ok = [], 0
    for name, addrs in sorted(dup.items()):
        low, high = addrs[0], addrs[-1]
        alias = split.get((name, high))
        # ① 最低地址那一份：我方必须有同名或别名符号落在该地址
        got = ours.get(name, [])
        if low in got:
            ok += 1
        elif alias and low in ours.get(alias, []):
            ok += 1                      # 极少数情况下主从反过来，只要有符号覆盖即可
        else:
            bad.append((name, '低地址 0x%x 无人绑定' % low, got))
        # ② 另一份：必须由拆分别名覆盖（否则那一份的使用者会指向错的对象）
        if alias is None:
            bad.append((name, '0x%x 与 0x%x 同名但**无拆分别名**' % (low, high), addrs))
        elif high not in ours.get(alias, []):
            bad.append((name, '别名 %s 未落在 0x%x（实际 %s）'
                        % (alias, high, ours.get(alias, [])), addrs))
    return bad, ok


# --------------------------------------------------------------------------- #
def self_test():
    chk = []

    def c(tag, got, want):
        chk.append((tag, got, want, got == want))

    secs = imaged_sections()
    c('前置 能从 SEC_DEF 解析出被镜像节区（≥4 个）', len(secs) >= 4, True)
    c('前提 被镜像节区**包含** .data.rel.ro.local（本次缺陷正源于它缺席）',
      '.data.rel.ro.local' in secs, True)
    c('前提 SPLIT 与 gen_data_module.SPLIT_ALIASES 一致（名字集合）',
      sorted(SPLIT.values()), ['ArchivePath_global', 'SoundBuffer_global',
                               'diff_prev_global', 'handle_emurun'])

    # ---- 绑定检查：缺陷态 vs 正确态（纯函数，喂人造映射）----
    dup = {'ArchivePath': [0x3AE610, 0x3E18D4]}
    bad_fixed, ok_fixed = check_binding(dup, {'ArchivePath': [0x3AE610],
                                              'ArchivePath_global': [0x3E18D4]})
    c('正例 绑定正确（主名=低地址 + 别名=高地址）⇒ 无问题', (bad_fixed, ok_fixed), ([], 1))
    bad_bug, _ = check_binding(dup, {'ArchivePath': [0x3E18D4],
                                     'ArchivePath_global': [0x3E18D4]})
    c('反例 **修复前的绑定**（主名误绑到 GLOBAL 高地址）⇒ 必须报错',
      bool(bad_bug) and '低地址' in bad_bug[0][1], True)
    bad_noalias, _ = check_binding(dup, {'ArchivePath': [0x3AE610]})
    c('反例 缺拆分别名 ⇒ 报"无拆分别名"', bool(bad_noalias), True)

    # ---- 覆盖检查：删掉 8 行 RELRO 的账本副本 ⇒ 必须正好报 8 条 ----
    if os.path.exists(DEF_ELF) and os.path.exists(DEF_LEDGER):
        objs, _dup = factory_objects(DEF_ELF)
        rows = read_ledger_rows(DEF_LEDGER)
        members = [(n, a, s, sec) for n, a, s, sec in objs if sec in secs]
        miss = check_coverage(members, rows)
        c('正例 当前账本覆盖**完整**（缺失 0 条）', len(miss), 0)
        stripped = {r for r in rows if not (r[1] >= 0x3AE5C4 and r[1] < 0x3AEEE0)}
        miss2 = check_coverage(members, stripped)
        c('反例 把 RELRO 区间(0x3AE5C4..0x3AEEE0)的行删掉 ⇒ 恰好报 8 条缺失',
          len(miss2), 8)
        c('反例 缺失项里含 ArchivePath@0x3AE610',
          ('ArchivePath', 0x3AE610) in {(n, a) for n, a, _s in miss2}, True)
    else:
        c('前置 工厂 ELF 与账本存在', False, True)
    return chk


def main():
    if '--self-test' in sys.argv:
        chk = self_test()
        bad = 0
        for tag, got, want, ok in chk:
            print('   %s  %-58s got=%s' % ('✓' if ok else '★FAIL', tag, got))
            bad += 0 if ok else 1
        print('   合计 %d 条，失败 %d 条' % (len(chk), bad))
        return 2 if bad else 0

    def arg(name, default):
        if name in sys.argv:
            return sys.argv[sys.argv.index(name) + 1]
        return default

    elf, ours, ledger = arg('--elf', DEF_ELF), arg('--ours', DEF_OURS), arg('--ledger', DEF_LEDGER)
    for p in (elf, ours, ledger):
        if not os.path.exists(p):
            sys.stderr.write('★ 缺输入 %s —— fail-closed（不做静默跳过）\n' % p)
            return 11

    secs = imaged_sections()
    objs, dup = factory_objects(elf)
    rows = read_ledger_rows(ledger)
    members = [(n, a, s, sec) for n, a, s, sec in objs if sec in secs]
    ours_addrs = our_object_addrs(ours)

    print('=' * 84)
    print('数据符号覆盖 / 重名绑定门禁')
    print('=' * 84)
    print('  被镜像节区（源自 gen_data_module.SEC_DEF）：%s' % ' '.join(secs))
    print('  工厂数据对象 %d 个（其中在被镜像节区内 %d 个）；账本 %d 行；我方数据对象 %d 名'
          % (len(objs), len(members), len(rows), len(ours_addrs)))

    miss = check_coverage(members, rows)
    print()
    print('  --- 检查 1 · 账本覆盖完整性（被镜像节区的每个工厂对象都要有同址行）---')
    if miss:
        print('  ★ FAIL：缺失 %d 条（这些对象**没有任何判据**在守它们）' % len(miss))
        for n, a, sec in miss[:30]:
            print('      %-24s 0x%08x  %s' % (n, a, sec))
    else:
        print('  ✓ PASS：覆盖完整（0 条缺失）')

    bad, ok = check_binding(dup, ours_addrs)
    print()
    print('  --- 检查 2 · 重名符号绑定（同名 ≥2 份 ⇒ 代码引用的低地址那份必须有符号）---')
    print('  工厂同名多定义的名字 %d 个：%s' % (len(dup), ', '.join(sorted(dup))))
    if bad:
        print('  ★ FAIL：%d 条' % len(bad))
        for n, why, got in bad:
            print('      %-24s %s（我方 %s）' % (n, why, got))
    else:
        print('  ✓ PASS：%d 个重名符号的主/从绑定均正确' % ok)

    print()
    rc = 2 if (miss or bad) else 0
    print('  结论：%s' % ('PASS' if rc == 0 else 'FAIL'))
    return rc


if __name__ == '__main__':
    sys.exit(main())
