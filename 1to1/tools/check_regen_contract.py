#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_regen_contract —— 数据模块「重生成契约」门禁。

为什么需要它（2026-09-23 实测踩到的两颗地雷）
--------------------------------------------
`tools/regen_data.sh`（= gen_data_module.py + gen_local_alias.py）会**重写**已提交的
`linker/factory.ld` 与 `src/data/factory_image.S`。而这两份文件里含**多次手工修复**的成果，
生成器一旦没跟上，**每跑一次 regen 就静默回退一次**：

  地雷 1（GAP 16.69）：③ 运行时区曾被钉在 `.data 0x01000000 / .bss 0x02000000 / .text 0x05000000`。
    lld 会把「`.fini_array`（在 .rodata 末尾）」和「钉在 0x01000000 的 .data」并进同一个 RW 段，
    p_filesz 跨过 11.1 MB 空洞 ⇒ PT_LOAD 2→9、文件 3.9MB→17.3MB、**真机 exec 直接失败、零日志**。
  地雷 2（GAP 16.71）：RELRO 族必须从 `.data` 里拆出来、排在 `.data` **之前**，且 `.data` 页对齐；
    否则 `.data` 整段落进 `PT_GNU_RELRO` ⇒ 进程写自己的全局变量即 SIGSEGV。
  地雷 3（历史记录）：`--missing` 若误用**分类后的 MISSING**而不是**全量 UNDEF**，
    别名会从 934 塌缩到 17 ⇒ 大量工厂地址失去供应。
  地雷 4：Windows 上 `open(..., 'w')` 把 .S/.ld 写成 CRLF，与仓库的 LF 不一致。

本门禁不重跑 regen（regen 需要工厂 ELF，CI 里没有），而是**断言已提交产物的不变量**。
配套（更强，但只能本地跑）：跑完 `regen_data.sh` 后与提交版本 diff 应为 0 —— 本次已实测通过。

自证（--self-test）：正例（好样本）必须全过，反例（四类坏样本）必须各自被点出。
"""
import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LD = os.path.join(ROOT, 'linker', 'factory.ld')
IMG = os.path.join(ROOT, 'src', 'data', 'factory_image.S')
LOCAL = os.path.join(ROOT, 'src', 'data', 'factory_local.S')

# 别名数棘轮（只许增）：实测 2026-09-23 = 1109（含补供应的 9 个 DAT_003b01xx）
ALIAS_MIN_IMAGE = 1100
ALIAS_MIN_LOCAL = 5

# ★ 禁止在 .ld 里出现的「钉死运行时区地址」（GAP 16.69 的回退特征）
FORBIDDEN_PIN = ['0x01000000', '0x02000000', '0x05000000']


def check(text_ld, text_img, ld_cr, img_cr, local_cr):
    """返回 (ok, [问题...], [信息...])。纯函数，便于自证。"""
    bad, info = [], []

    # ① GAP 16.69：不允许钉死运行时区地址
    for pin in FORBIDDEN_PIN:
        # 只查 SECTIONS 里作为**段起始地址**出现的形式（`.data 0x01000000 :`）
        if re.search(r'^\s*\.\w[\w.]*\s+' + re.escape(pin) + r'\s*:', text_ld, re.M):
            bad.append('GAP 16.69 回退：factory.ld 里又出现钉死地址 %s' % pin)

    # ② GAP 16.71：RELRO 族必须独立、排在 .data 之前，且 .data 页对齐
    for sec in ('.data.rel.ro', '.got', '.dynamic'):
        if not re.search(r'^\s*' + re.escape(sec) + r'\s', text_ld, re.M):
            bad.append('GAP 16.71 回退：factory.ld 缺少独立输出段 %s' % sec)
    m_ro = re.search(r'^\s*\.data\.rel\.ro\s', text_ld, re.M)
    m_da = re.search(r'^\s*\.data\s', text_ld, re.M)
    if m_ro and m_da and m_ro.start() > m_da.start():
        bad.append('GAP 16.71 回退：.data.rel.ro 没有排在 .data 之前')
    if not re.search(r'^\s*\.data\s+ALIGN\(0x1000\)', text_ld, re.M):
        bad.append('GAP 16.71 回退：.data 未页对齐（RELRO 会侵入 .data ⇒ 写全局变量 SIGSEGV）')

    # ③ 别名数棘轮（防「用 MISSING 重生成导致别名塌缩」）
    n_img = len(re.findall(r'^\s*\.set\s+[A-Za-z_]', text_img, re.M))
    info.append('factory_image.S 别名 %d 个（下限 %d）' % (n_img, ALIAS_MIN_IMAGE))
    if n_img < ALIAS_MIN_IMAGE:
        bad.append('别名塌缩：factory_image.S 只有 %d 个别名（< %d）' % (n_img, ALIAS_MIN_IMAGE))

    # ④ 行尾必须纯 LF
    for name, cr in (('linker/factory.ld', ld_cr), ('src/data/factory_image.S', img_cr)):
        if cr:
            bad.append('%s 含 %d 个 CR —— 文本产物必须是纯 LF' % (name, cr))
    if local_cr:
        bad.append('src/data/factory_local.S 含 %d 个 CR —— 必须是纯 LF' % local_cr)

    # ⑤ 必须存在的关键小段（防止整段被删）
    if 'ENTRY(_start)' not in text_ld:
        bad.append('factory.ld 缺 ENTRY(_start)')
    if '.fimg_bss_pad' not in text_ld:
        bad.append('factory.ld 缺 .fimg_bss_pad（bss 之后必须仍是已映射内存）')
    return (not bad), bad, info


def load(path):
    if not os.path.exists(path):
        return '', 0
    b = open(path, 'rb').read()
    return b.replace(b'\r\n', b'\n').decode('utf-8', 'replace'), b.count(b'\r')


def run():
    ld, lcr = load(LD)
    img, icr = load(IMG)
    _, kcr = load(LOCAL)
    ok, bad, info = check(ld, img, lcr, icr, kcr)
    print('=' * 96)
    print('数据模块「重生成契约」门禁')
    print('=' * 96)
    for x in info:
        print('  · %s' % x)
    if bad:
        for x in bad:
            print('  ★ %s' % x)
        print('\n  结论：FAIL（%d 项）—— regen 会静默回退这些修复，先修生成器' % len(bad))
    else:
        print('  结论：PASS（16.69 / 16.71 / 别名棘轮 / LF / 关键段 全部成立）')
    return 0 if ok else 2


def self_test():
    print('=' * 96)
    print('自证：先验仪器，再看它的结论')
    print('=' * 96)
    good_ld = ('ENTRY(_start)\nSECTIONS\n{\n'
               '  .fimg_bss_pad 0x003e2000 : { *(.fimg_bss_pad) }\n'
               '  .data.rel.ro ALIGN(4) : { *(.data.rel.ro) }\n'
               '  .got ALIGN(4) : { *(.got) }\n'
               '  .dynamic ALIGN(4) : { *(.dynamic) }\n'
               '  .data ALIGN(0x1000) : { *(.data) }\n}\n')
    good_img = '\n'.join('\t.set SYM_%d, __f_data_base + 0x%x' % (i, i) for i in range(ALIAS_MIN_IMAGE))
    ok = True

    def chk(tag, got_ok, want_ok):
        nonlocal ok
        good = (got_ok == want_ok)
        ok = ok and good
        print('   %-52s ok=%-6s %s' % (tag, got_ok, '✓' if good else '★ FAIL'))

    r = check(good_ld, good_img, 0, 0, 0)
    chk('正例  合规样本 → 通过', r[0], True)

    bad_ld = good_ld.replace('.data ALIGN(0x1000)', '.data 0x01000000')
    chk('反例  钉死 0x01000000 → 被点出', check(bad_ld, good_img, 0, 0, 0)[0], False)

    bad_ld2 = good_ld.replace('  .data.rel.ro ALIGN(4) : { *(.data.rel.ro) }\n', '')
    chk('反例  删掉 .data.rel.ro 独立段 → 被点出', check(bad_ld2, good_img, 0, 0, 0)[0], False)

    bad_ld3 = good_ld.replace('.data ALIGN(0x1000)', '.data ALIGN(4)')
    chk('反例  .data 不页对齐 → 被点出', check(bad_ld3, good_img, 0, 0, 0)[0], False)

    chk('反例  .S 含 CR → 被点出', check(good_ld, good_img, 0, 3, 0)[0], False)

    chk('反例  别名塌缩(17 个) → 被点出',
        check(good_ld, '\n'.join('\t.set A_%d, X' % i for i in range(17)), 0, 0, 0)[0], False)

    chk('反例  缺 .fimg_bss_pad → 被点出',
        check(good_ld.replace('.fimg_bss_pad 0x003e2000 : { *(.fimg_bss_pad) }\n', ''),
              good_img, 0, 0, 0)[0], False)

    print()
    print('   自证结论：%s' % ('全部通过 —— 仪器可用' if ok else '★ 有 FAIL —— 仪器不可信'))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        if not self_test():
            return 2
        print()
    return run()


if __name__ == '__main__':
    sys.exit(main())
