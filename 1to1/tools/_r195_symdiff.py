#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_r195_symdiff.py —— driver.so 符号族 diff 对齐（R195，P0 第一项）

目的（用户指定 P0）：
  driver.so 符号族与项目内已逆向清单做 diff 对齐，确认假桩覆盖全部初始化入口。

做法（全部本机完成，不占云开发额度）：
  1. 解析 driver.so 的 .dynsym UNDEF ⇒ "需要外部提供"的符号全集（权威，不写死清单），
     **并分强/弱两档**（弱 UNDEF 缺失无害，不构成缺口）；
  2. 解析 driver.so 的 .symtab 定义的函数 ⇒ 内部入口（初始化路径候选）；
  3. 解析三个桩源码（drm_stub.c / alsa_stub.c / stub_core.c）定义的导出符号；
  4. 解析 rootfs 真库（golden/device_rootfs_min 下 .so*）的导出符号；
  5. diff 分类：每个 driver **强** UNDEF 的提供者 = 桩 / rootfs 真库 / **无（缺口）**；
  6. ★ 调用图实证：用 capstone 反汇编 + PLT（GOT 地址配对法，承第 152 轮）
     建「内部初始化函数 → 外部符号」调用图，逐个确认其外部依赖已被覆盖
     ⇒ 这才是"假桩覆盖全部初始化入口"的可证判据（不是符号名猜）。

判据纪律（judging-tool-self-test）：
  · 权威来源一律实测（driver.so / 桩源码 / rootfs），不在本文件写死符号清单；
  · 强 UNDEF 无提供者 = fail-closed 显式列出，不静默跳过；
  · 双向：既报"driver 要而没人给"，也报"桩给了而 driver 不要"（漂移）。

用法:
  python tools/_r195_symdiff.py            # 人读报表
  python tools/_r195_symdiff.py --gate     # 门禁模式：有强缺口 exit 1
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
DRIVER = os.path.join(ROOT, 'golden', 'sdcard_min', 'driver.so')
STUBS = [os.path.join(HERE, 'guest_shim', f) for f in ('drm_stub.c', 'alsa_stub.c', 'stub_core.c')]
ROOTFS = os.path.join(ROOT, 'golden', 'device_rootfs_min')

# 初始化相关函数名特征（用于从 .symtab 里挑"初始化入口"候选）
INIT_PAT = re.compile(
    r'(^|_)(init|probe|open|create|setup|alloc|register|load|start)(_|$)|'
    r'gr_|video|sfc|audio|snd_|drm|surface|blit|fb|frame|flip|crtc|plane|modeset|kms',
    re.I)


def elf_undef_split(path):
    """返回 (strong_undef, weak_undef, sym_funcs, dyn_def)。

    strong_undef：STB_GLOBAL 的 UNDEF —— **必须有提供者**，否则加载即失败；
    weak_undef  ：STB_WEAK  的 UNDEF —— GCC 惯例的可选符号（_ITM_*/_Jv_*/__gmon_start__），
                  运行时解析不到即为 0，程序自身判空使用 ⇒ 缺失无害，不构成缺口。
    """
    from elftools.elf.elffile import ELFFile
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        strong, weak, dyn_def = set(), set(), set()
        ds = elf.get_section_by_name('.dynsym')
        if ds is not None:
            for sym in ds.iter_symbols():
                if not sym.name or sym['st_shndx'] != 'SHN_UNDEF':
                    if sym.name and sym['st_shndx'] != 'SHN_UNDEF' and sym['st_info']['bind'] in ('STB_GLOBAL', 'STB_WEAK'):
                        dyn_def.add(sym.name)
                    continue
                if sym['st_info']['bind'] == 'STB_GLOBAL':
                    strong.add(sym.name)
                elif sym['st_info']['bind'] == 'STB_WEAK':
                    weak.add(sym.name)
        sym_funcs = set()
        ss = elf.get_section_by_name('.symtab')
        if ss is not None:
            for sym in ss.iter_symbols():
                if sym.name and sym['st_info']['type'] == 'STT_FUNC' and sym['st_shndx'] != 'SHN_UNDEF':
                    sym_funcs.add(sym.name)
        return strong, weak, sym_funcs, dyn_def


def build_call_graph(path):
    """用 capstone + PLT(GOT 地址配对法，承第 152 轮) 建「函数 → 外部符号」调用图。

    返回 (func_calls, plt_map)：
      func_calls: {func_name: set(外部符号名)}   —— 函数体内 bl 到 .plt stub 的目标
      plt_map   : {plt_stub_addr: symbol_name}   —— 供调试/复核
    """
    from elftools.elf.elffile import ELFFile
    from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
    from capstone.arm import ARM_REG_IP, ARM_REG_PC

    with open(path, 'rb') as f:
        elf = ELFFile(f)
        # --- .rel.plt: GOT 槽地址 → 符号名 ---
        got2name = {}
        rp = elf.get_section_by_name('.rel.plt')
        symtab = elf.get_section_by_name('.dynsym')
        if rp is not None:
            for r in rp.iter_relocations():
                si = r['r_info_sym']
                if si < symtab.num_symbols():
                    got2name[r['r_offset']] = symtab.get_symbol(si).name
        # --- 函数区间（.symtab）---
        func_ranges = []   # (start, end, name)
        ss = elf.get_section_by_name('.symtab')
        if ss is not None:
            for sym in ss.iter_symbols():
                if sym.name and sym['st_info']['type'] == 'STT_FUNC' and sym['st_shndx'] != 'SHN_UNDEF':
                    func_ranges.append((sym['st_value'], sym['st_value'] + sym['st_size'], sym.name))
        # --- .text ---
        text = elf.get_section_by_name('.text')
        taddr, tbytes = text['sh_addr'], text.data()
        # --- 解 PLT stub → GOT 地址 → 符号名 ---
        # 本 ELF 的 stub 形态（capstone 实测，addr=0x185c 起）：
        #   0x185c..0x186c = PLT0 header（20 B，跳过）
        #   其后每 12 B 一个 stub：
        #     add ip, pc, #X          ← X 在 operands[2].imm（ARM: pc = 本指令+8）
        #     add ip, ip, #Y          ← Y 在 operands[2].imm
        #     ldr pc, [ip, #Z]!       ← Z 在 operands[1].mem.disp
        #   ⇒ GOT = (add1_addr + 8) + X + Y + Z
        #   ★ 不能用 op_str 切分（`#0, #12` 形式会切错），必须用 operands API。
        plt = elf.get_section_by_name('.plt')
        plt_map = {}
        if plt is not None:
            paddr, pbytes = plt['sh_addr'], plt.data()
            md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
            md.detail = True
            stub_start = None
            acc = 0
            for ins in md.disasm(pbytes, paddr):
                if ins.mnemonic == 'add' and len(ins.operands) >= 3 \
                        and ins.operands[0].reg == ARM_REG_IP and ins.operands[1].reg == ARM_REG_PC:
                    stub_start = ins.address
                    acc = ins.address + 8 + ins.operands[2].imm
                elif ins.mnemonic == 'add' and len(ins.operands) >= 3 \
                        and ins.operands[0].reg == ARM_REG_IP and ins.operands[1].reg == ARM_REG_IP:
                    acc += ins.operands[2].imm
                elif ins.mnemonic == 'ldr' and stub_start is not None and len(ins.operands) >= 2 \
                        and ins.operands[0].reg == ARM_REG_PC:
                    mem = ins.operands[1].mem
                    got = acc + mem.disp
                    if got in got2name:
                        plt_map[stub_start] = got2name[got]
                    stub_start = None
                    acc = 0
        # --- 反汇编：**按函数分段**（不用线性扫全 .text）---
        # ★ 为什么必须分段：线性扫 .text 遇到字面量池 / switch 表 / 内联数据会**失步**，
        #   导致后续函数的指令整体错位 ⇒ bl 目标匹配大量漏报（实测：gr_init 明明调了
        #   PLT stub 0x1a08/0x1b04，线性扫却完全漏掉）。
        #   .symtab 给了每个函数的 (value, size) ⇒ 从各函数入口独立反汇编，
        #   互不受前一个函数的数据影响。
        func_ranges_sz = []   # (start, end, name)
        if ss is not None:
            for sym in ss.iter_symbols():
                if sym.name and sym['st_info']['type'] == 'STT_FUNC' and sym['st_shndx'] != 'SHN_UNDEF':
                    func_ranges_sz.append((sym['st_value'], sym['st_value'] + sym['st_size'], sym.name))
        plt_lo = min(plt_map) if plt_map else 0
        plt_hi = max(plt_map) if plt_map else 0
        func_calls = {}
        for s, e, fn in func_ranges_sz:
            if e <= s or s < taddr or e > taddr + len(tbytes):
                continue
            for ins in md.disasm(tbytes[s - taddr:e - taddr], s):
                if ins.mnemonic != 'bl':
                    continue
                try:
                    tgt = int(ins.op_str.lstrip('#'), 0)
                except Exception:
                    continue
                key = tgt & ~1
                if plt_lo <= key <= plt_hi and key in plt_map:
                    func_calls.setdefault(fn, set()).add(plt_map[key])
        return func_calls, plt_map

def stub_defined_symbols(paths):
    """从桩源码提取定义的函数名（导出 or static）。

    规则：`TYPE name(` 且 name 不是关键字；加上 `__attribute__((visibility("default")))`
    紧邻的函数名。刻意宽松（宁多勿漏）—— 漏报会让"缺口"假阳性。
    """
    out = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        src = open(p, encoding='utf-8', errors='replace').read()
        names = set()
        # 函数定义：行首类型 + 名字 + (
        for m in re.finditer(r'^[A-Za-z_][A-Za-z0-9_ \*]*?([A-Za-z_][A-Za-z0-9_]*)\s*\(', src, re.M):
            n = m.group(1)
            if n in ('if', 'for', 'while', 'switch', 'return', 'sizeof', 'typeof', 'defined'):
                continue
            names.add(n)
        out[os.path.basename(p)] = names
    return out


def rootfs_exported(rootfs):
    """rootfs 下所有 .so* 的导出符号（dynsym defined）。

    ★ fail-loud：解析失败必须显式报出文件名与原因，不静默 continue
      （静默跳过会让"真库提供"整列变 0 ⇒ 把 22 个 libc 符号误报成缺口，假红）。
    """
    out = {}
    errs = []
    for dp, _dn, fn in os.walk(rootfs):
        for f in fn:
            if '.so' not in f:
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, rootfs).replace('\\', '/')
            try:
                _s, _w, _f, d = elf_undef_split(p)
            except Exception as e:
                errs.append('%s: %s' % (rel, e))
                continue
            if d:
                out[rel] = d
    if errs:
        print('  [warn] rootfs 有 %d 个文件解析失败：%s' % (len(errs), '; '.join(errs[:3])))
    return out


def main():
    gate = '--gate' in sys.argv
    if not os.path.exists(DRIVER):
        print('!! 缺 driver.so: %s' % DRIVER)
        return 9

    strong, weak, sym_funcs, dyn_def = elf_undef_split(DRIVER)
    stubs = stub_defined_symbols(STUBS)
    stub_all = set()
    for v in stubs.values():
        stub_all |= v
    rf = rootfs_exported(ROOTFS)
    rf_all = set()
    for v in rf.values():
        rf_all |= v

    print('=' * 78)
    print('driver.so 符号族 diff 对齐（R195，P0）')
    print('=' * 78)
    print('driver.so            : %s（%d B）' % (os.path.relpath(DRIVER, ROOT), os.path.getsize(DRIVER)))
    print('  .dynsym 强 UNDEF   : %d（**必须有提供者**）' % len(strong))
    print('  .dynsym 弱 UNDEF   : %d（GCC 可选符号，缺失无害）' % len(weak))
    print('  .symtab 函数       : %d（内部定义）' % len(sym_funcs))
    print('  .dynsym 已导出     : %d' % len(dyn_def))
    print('桩源码定义符号       : %s' % ', '.join('%s=%d' % (k, len(v)) for k, v in sorted(stubs.items())))
    print('rootfs 真库          : %d 个，导出合计 %d' % (len(rf), len(rf_all)))

    # ---- 强 UNDEF 分类（缺口只对强符号判）----
    by_stub, by_rf, gap = {}, {}, []
    for s in sorted(strong):
        if s in stub_all:
            by_stub[s] = '桩'
        elif s in rf_all:
            by_rf[s] = '真库'
        else:
            gap.append(s)

    print()
    print('---- 表1：强 UNDEF 按提供者分类 ----')
    print('  桩提供        : %d' % len(by_stub))
    print('  rootfs 真库提供: %d' % len(by_rf))
    print('  ★ 无提供者    : %d' % len(gap))

    # 按族细分
    fam = {'drm*': [], 'snd_pcm_*': [], 'libc/其他': []}
    for s in sorted(strong):
        if s.startswith('drm'):
            fam['drm*'].append(s)
        elif s.startswith('snd_pcm'):
            fam['snd_pcm_*'].append(s)
        else:
            fam['libc/其他'].append(s)
    print()
    print('---- 表2：强 UNDEF 符号族分布 ----')
    for k, v in fam.items():
        print('  %-12s %d' % (k, len(v)))

    print()
    print('---- 表3：强 UNDEF 无提供者清单（真缺口，fail-closed 全列）----')
    if gap:
        for s in gap:
            print('  ★ %s' % s)
    else:
        print('  （无 —— 每个强 UNDEF 都有提供者）')

    print()
    print('---- 表3b：弱 UNDEF（GCC 可选，缺失无害，列出供核对）----')
    for s in sorted(weak):
        prov = '桩' if s in stub_all else ('真库' if s in rf_all else '无（弱符号，无害）')
        print('  %-34s %s' % (s, prov))

    print()
    print('---- 表4：初始化相关强 UNDEF × 覆盖情况 ----')
    init_syms = sorted(s for s in strong if INIT_PAT.search(s))
    print('  初始化相关强 UNDEF 共 %d 个（按名特征筛）' % len(init_syms))
    unc = []
    for s in init_syms:
        if s in stub_all:
            prov = '桩'
        elif s in rf_all:
            prov = '真库'
        else:
            prov = '★无'
            unc.append(s)
        print('    %-34s %s' % (s, prov))

    print()
    print('---- 表5：桩给了而 driver 强 UNDEF 不要（漂移检查）----')
    drift = sorted(s for s in stub_all if s.startswith('drm') and s not in strong and s not in weak)
    if drift:
        for s in drift:
            print('  · %s' % s)
    else:
        print('  （无 drm* 漂移）')

    print()
    print('---- 表6：driver.so 内部初始化入口（.symtab 函数，名特征命中）----')
    init_funcs = sorted(f for f in sym_funcs if INIT_PAT.search(f))
    for f in init_funcs:
        print('  %s' % f)
    if not init_funcs:
        print('  （.symtab 无函数或未命中）')

    # ---- 表7：调用图实证（核心判据）----
    print()
    print('---- 表7：★ 调用图实证 —— 初始化函数的外部依赖 × 覆盖 ----')
    try:
        func_calls, plt_map = build_call_graph(DRIVER)
    except Exception as e:
        func_calls, plt_map = {}, {}
        print('  （调用图构建失败：%s）' % e)
    if func_calls:
        print('  PLT 解析 %d 条；建立 %d 个函数的调用边' % (len(plt_map), len(func_calls)))
        key_funcs = sorted(f for f in init_funcs if f in func_calls)
        print('  初始化函数中有调用边的：%d/%d' % (len(key_funcs), len(init_funcs)))
        # ★ 判据精度：bl 到 PLT 的目标**不全是外部符号** —— driver.so 自己导出/定义的
        #   函数（跨编译单元的内部调用）也可能经 PLT。它们的提供者是 driver.so 自身，
        #   **不构成缺口**。否则会把 gr_flip/gr_rotate/open_drm 等内部调用误报成缺口（假红）。
        self_provided = sym_funcs | dyn_def
        bad = []
        for fn in key_funcs:
            ext = sorted(func_calls[fn])
            unc_ext = [s for s in ext
                       if s not in stub_all and s not in rf_all and s not in self_provided]
            mark = '★' if unc_ext else '✓'
            print('    %s %-26s → %s' % (mark, fn, ', '.join(ext)))
            if unc_ext:
                bad.append((fn, unc_ext))
        print()
        if bad:
            print('  ★ 有初始化函数依赖未覆盖符号：')
            for fn, u in bad:
                print('      %s → %s' % (fn, ', '.join(u)))
        else:
            print('  ✅ 全部初始化函数的外部依赖均已被 桩/真库 覆盖')
    else:
        print('  （无调用边数据）')

    print()
    print('=' * 78)
    ok = not gap
    if ok:
        print('结论：driver.so 全部 %d 个强 UNDEF 均有提供者（桩 %d / 真库 %d）；弱 UNDEF %d 个无害 ✅' % (
            len(strong), len(by_stub), len(by_rf), len(weak)))
    else:
        print('结论：存在 %d 个强 UNDEF 无提供者 ❌（见表3）' % len(gap))
    print('=' * 78)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
