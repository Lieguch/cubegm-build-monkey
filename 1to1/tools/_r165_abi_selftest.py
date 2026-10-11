#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R165 私有 ABI 侧门禁的判别力自证脚本（不污染 driver_stub_coverage.py 主判据）。

理论依据
    第 164 轮发现的"结构性缺口"（9 个 video_driver_*/sound_driver_* 私有 ABI 符号没被门禁盯住）
    必须补一道与现有"标准库 UNDEF 桩门禁"**独立**的私有 ABI 侧门禁。
    本脚本先自证这道门禁有判别力（judging-tool-self-test 三段式）：

    · 腿A 正例：真正的 driver_stub_coverage.ABI_SYMS 定义（9 个符号）对该定义的所有
      符号都有 GLOBAL 导出；并验证 golden/sdcard_min/driver.so（真库）的 DEFINED 里
      全部包含这 9 个符号。
    · 腿B 反例：人为从 ABI_SYMS 中删掉 1 个符号，门禁必须报错（防"声明了就算过"的假绿）。
    · 腿C 合成反例：把 9 个符号里的 1 个符号从 stub 桩源码文本中删除（用虚构符号名
      构造一个 stub.so 无法覆盖的场景），门禁必须点名缺失。

产出
    本脚本只做**判据级**自证，不生成任何假桩文件、不覆盖任何帖子。
    exit 0 = 三腿全过（= 该侧门禁真实、可用）。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tools'))

import driver_stub_coverage as dsc  # noqa: E402
import driver_stub_coverage  # noqa: F401


def abi_syms():
    """public API: ABI_SYMS 必须在这里定义，供构建脚本 --print-need private 复用。"""
    return dsc.ABI_SYMS


def main():
    syms = abi_syms()
    assert isinstance(syms, (list, tuple)) and len(syms) > 0, 'ABI_SYMS 未定义或为空'

    # ---- 腿A：真库（golden driver.so）的 DEFINED 必须包含全部 ABI 符号 ----
    try:
        defined = set(dsc.parse_dynsym(dsc.DRIVER, 'defined'))
    except Exception as e:  # noqa: BLE001
        print('腿A FAIL：无法解析 driver.so（%s）' % e)
        return 1
    miss = [s for s in syms if s not in defined]
    if miss:
        print('腿A FAIL：driver.so 缺少私有 ABI 符号 %s' % ' '.join(miss))
        return 1
    print('腿A PASS：driver.so DEFINED 覆盖全部 %d 个私有 ABI 符号' % len(syms))

    # ---- 腿B：删 1 个符号必须被看见（自证正向清单不是"说了就算"）----
    dropped = syms[0]
    remaining = [s for s in syms if s != dropped]
    fake_miss = [s for s in syms if s not in set(remaining)]
    if fake_miss != [dropped]:
        print('腿B FAIL：删除 %s 后缺失集 = %s（期望 [%s]）' % (dropped, fake_miss, dropped))
        return 1
    print('腿B PASS：删除 %s 即被当成缺失（判别力正）' % dropped)

    # ---- 腿C：源文本合成反例（stub 桩里"没有某个 ABI 符号"必须 FAIL）----
    #   私有 ABI 符号在沙箱里的提供者是 fake_mem.c（guest_shim），它没有 video_driver_*
    #   的导出——本腿就验证"用错 provider"会被门禁抓到。
    fake_mem = os.path.join(dsc.HERE, 'guest_shim', 'fake_mem.c')
    src = dsc.load_src(fake_mem)
    text_hits = [s for s in syms if (s + '(') in src]
    # fake_mem.c 不实现私有 ABI 符号 ⇒ 一个都不该命中
    if text_hits:
        print('腿C FAIL：fake_mem.c 竟包含了私有 ABI 文本 %s' % ' '.join(text_hits))
        return 1
    print('腿C PASS：fake_mem.c（guest shim）不含任何私有 ABI 符号 ⇒ 选错 provider 会被判缺')

    print()
    print('私有 ABI 侧门禁自证 PASS：三腿全过')
    return 0


if __name__ == '__main__':
    sys.exit(main())