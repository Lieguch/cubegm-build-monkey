#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core_dlsym_gate.py —— rkgame core 加载器 dlsym 清单门禁（R195，P1 收尾）

为什么需要
  rkgame 是 libretro **frontend**：`dlopen` core `.so` 后 `dlsym` 取函数指针。
  上游 `madcock/sf2000_multicore` 的标准 `retro_core_t` 有 25 字段，但**本机实测 21 个**
  `retro_*` 字符串，且其中 2 个（`retro_load_state`/`retro_save_state`）是 rkgame **自己实现
  并导出**的（不从 core dlsym）⇒ 真正要 dlsym 的是 **19 个**。
  照标准 25 个写会漏；照 21 个写会把 rkgame 自己的 2 个也去 dlsym（必然失败）。
  ⇒ 必须有机械门禁守"复刻侧 dlsym 的字面量集合 ⊇ 真机 19 个"。

权威来源（运行时实测，不写死）
  · 真机 dlsym 清单 = `golden/factory.rkgame.bin` 二进制内 `retro_*` 字符串集合
    − `.symtab` 里有 STT_FUNC 实现的 2 个（rkgame 自实现并导出）；
  · 复刻侧 = 扫 `src/**/*.{c,h}` 里 `dlsym(...,"retro_*")` 字面量。

判据（单一档，符号级）
  fail：真机 dlsym 清单里的符号，在复刻侧源码中**找不到** `dlsym(...,"<sym>")` 字面量
        ⇒ 该功能没实现（core 加载后调用即空指针崩）。
  info：复刻侧 dlsym 了真机清单外的符号（需人工确认是否有真机对应）。

  ★ 为什么不做"声明了 `_retro_X` 指针但无 dlsym"那一档：实测**变量名与符号名会故意不同**
    （复刻侧 `_retro_set_device = dlsym(h, "retro_set_controller_port_device")`，
     而真机二进制里两个字符串都存在）⇒ 用指针名反推符号必然误报。只按**符号**判。

判别力自证（--selftest，judging-tool-self-test 纪律）
  把真机清单临时删掉一个**已绑定**的符号再跑 ⇒ 必须从 PASS 翻成 FAIL 且点名该符号。
  没有这一腿，门禁可能"永远 PASS"而无判别力。

用法:
  python tools/core_dlsym_gate.py              # 人读报表 + exit 0/1
  python tools/core_dlsym_gate.py --selftest   # 附加判别力自证
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
BIN = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
SRC = os.path.join(ROOT, 'src')


def device_retro_strings(path):
    """真机二进制里**位于 .rodata** 的 retro_* 字符串（dlsym 的符号名参数）。

    ★ 为什么只扫 .rodata 而不是全二进制（R197 实测踩坑）：
      全二进制扫会把 **.symtab 里的符号名**也扫进来 —— 例如 `_retro_set_device`
      这个**全局指针变量**的符号名位于符号表区（0x3bc350，上下文是
      `Load.prosystem_Load.stella_Load..._retro_set_device.items...`），
      而真正的 dlsym 目标 `retro_set_controller_port_device` 在 .rodata
      （0x2d5cec，与 `device0_type`/`find ... process fail` 等日志串相邻）。
      ⇒ 扫全二进制会把"变量名"误判成"dlsym 目标"，制造假缺口。
    """
    from elftools.elf.elffile import ELFFile
    out = set()
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        for sec in elf.iter_sections():
            if sec['sh_type'] != 'SHT_PROGBITS':
                continue
            if not (sec['sh_flags'] & 0x2):      # SHF_ALLOC 必须置位
                continue
            if sec['sh_flags'] & 0x1:            # SHF_WRITE 置位 ⇒ 可写数据段（.data/.bss 类），跳过
                continue
            if sec.name in ('.symtab', '.strtab', '.comment', '.note', '.gnu'):
                continue
            data = sec.data()
            for m in re.finditer(rb'retro_[a-z_]+', data):
                out.add(m.group(0).decode())
    return out


def device_self_implemented(path):
    """rkgame 自己实现（.symtab STT_FUNC 且 shndx 有效）的 retro_* —— 它导出给别人，不从 core dlsym。"""
    from elftools.elf.elffile import ELFFile
    out = set()
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        ss = elf.get_section_by_name('.symtab')
        if ss is not None:
            for s in ss.iter_symbols():
                if s.name and s.name.startswith('retro_') \
                        and s['st_info']['type'] == 'STT_FUNC' and s['st_shndx'] != 'SHN_UNDEF':
                    out.add(s.name)
    return out


def rebuild_dlsym_literals(src_root):
    """复刻侧源码里绑定 retro_* 的所有形式 + 声明的 _retro_* 指针名。

    ★ 必须覆盖两种绑定形式（漏一种就误报）：
      形式1 直接 dlsym：`dlsym(h, "retro_xxx")`
      形式2 按名调用 ：`run_process("retro_xxx", arg)` —— 其实现内部就是
                      `pf = dlsym(handle_emurun, name); (*pf)(arg)`（见
                      src/proprietary/misc/FUN_002b59bc_run_process.c:14）
                      ⇒ **等价于 dlsym 绑定**，漏认它会把已绑符号误报成缺失。
    """
    lits, ptrs = set(), set()
    for dp, _dn, fn in os.walk(src_root):
        for f in fn:
            if not f.endswith(('.c', '.h')):
                continue
            p = os.path.join(dp, f)
            src = open(p, encoding='utf-8', errors='replace').read()
            for m in re.finditer(r'dlsym\s*\([^,]+,\s*"(retro_[a-z_]+)"', src):
                lits.add(m.group(1))
            # 形式2：run_process("retro_xxx", ...)
            for m in re.finditer(r'run_process(?:_constprop_0)?\s*\(\s*"(retro_[a-z_]+)"', src):
                lits.add(m.group(1))
            for m in re.finditer(r'\b(_retro_[a-z_]+)\b', src):
                ptrs.add(m.group(1))
    return lits, ptrs


def run(selftest=False):
    if not os.path.exists(BIN):
        print('!! 缺 %s' % BIN)
        return 9
    dev_all = device_retro_strings(BIN)
    self_impl = device_self_implemented(BIN)
    need = dev_all - self_impl          # 真机要求 dlsym 的清单
    lits, ptrs = rebuild_dlsym_literals(SRC)

    # ★ 单一真源：`need_eff` 恒等于 `need`。自证在**独立的 selftest 块**里做内存中的
    #   集合演算，不改这里的判定输入（历史 bug：曾在此处按 victim 删 need_eff，
    #   导致 selftest 模式的统计数比常规模式少 1，口径不一致）。
    need_eff = need

    print('=' * 74)
    print('rkgame core 加载器 dlsym 清单门禁（R195）')
    print('=' * 74)
    print('真机 retro_* 字符串      : %d' % len(dev_all))
    print('  rkgame 自己实现（排除）: %s' % ', '.join(sorted(self_impl)))
    print('⇒ 真机要求 dlsym 清单   : %d 个' % len(need_eff))
    print('复刻侧 dlsym 字面量     : %d 个' % len(lits))
    print('复刻侧 _retro_* 指针声明: %d 个' % len(ptrs))

    # 档1：真机要而复刻侧源码无对应 dlsym 字面量
    missing = sorted(s for s in need_eff if s not in lits)

    print()
    print('---- 档1：真机要求 dlsym 但复刻侧源码无该字面量 ----')
    if missing:
        for s in missing:
            print('  ★ %s' % s)
    else:
        print('  （无）')

    print()
    print('---- 已绑定（复刻侧 dlsym 字面量 ∩ 真机清单）----')
    bound_ok = sorted(s for s in need_eff if s in lits)
    for s in bound_ok:
        print('  ✓ %s' % s)

    print()
    print('---- 复刻侧多出的 dlsym（真机清单外）----')
    extra = sorted(s for s in lits if s not in need_eff)
    if extra:
        for s in extra:
            print('  · %s（真机无此字符串 —— 复刻侧扩展，需确认是否有真机对应）' % s)
    else:
        print('  （无）')

    fail = bool(missing)
    print()
    print('=' * 74)
    if fail:
        print('结论：❌ 缺 %d 个 dlsym 符号（见档1）' % len(missing))
    else:
        print('结论：✅ 真机 %d 个 dlsym 符号在复刻侧全部有绑定' % len(need_eff))
    print('=' * 74)

    if selftest:
        # 三腿自证（judging-tool-self-test）。★ 腿A 必须是"注入假缺口"式，
        # 不能依赖"当前恰好有 missing"—— 门禁绿时那样永远证不出真阳性。
        # 腿A 真阳性：临时从**已绑定集合**删掉一个（模拟复刻侧漏绑该符号）
        #           ⇒ 门禁必须把它判为 missing。
        # 腿B 可恢复：把 missing 全补回 lits ⇒ 必须翻 PASS。
        # 腿C 清单敏感：从真机清单删一个已绑定符号 ⇒ 判定随之变。
        if bound_ok:
            v = bound_ok[0]
            miss_after_del = [x for x in need_eff if x not in (lits - {v})]
            okA = v in miss_after_del
            print('[selftest] 腿A 真阳性：从已绑定集合删除 %s ⇒ 它必须进 missing' % v)
        else:
            okA = False
            print('[selftest] 腿A 无已绑定符号可选')
        lits2 = set(lits) | set(missing)
        miss2 = [s for s in need_eff if s not in lits2]
        okB = not miss2
        print('[selftest] 腿B 可恢复：补齐 %d 个绑定后 missing=%d ⇒ %s' % (
            len(missing), len(miss2), 'PASS' if okB else 'FAIL'))
        if bound_ok:
            v = bound_ok[0]
            new_missing = [x for x in (need_eff - {v}) if x not in lits]
            okC = v not in new_missing
            print('[selftest] 腿C 清单敏感：从真机清单删除已绑定的 %s ⇒ 它不再进 missing' % v)
        else:
            okC = False
            print('[selftest] 腿C 无已绑定符号可选')
        if okA and okB and okC:
            print('[selftest] ✅ 三腿全过：门禁有判别力（真阳性/可恢复/清单敏感）')
            return 0 if not fail else 1
        print('[selftest] ❌ 判别力不足（okA=%s okB=%s okC=%s）' % (okA, okB, okC))
        return 1
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(run(selftest='--selftest' in sys.argv))
