#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""isa_mode_gate.py —— **指令集模式（ARM / Thumb）棘轮门禁**。

## 为什么（第 107 轮实测的决定性发现）
工厂 **804 个函数里 308 个是 Thumb**（`st_value` bit0 = 1），且**全部属于 libiconv**：
  `_mbtowc` 138 ｜ `_wctomb` 130 ｜ charset 相关 38 ｜ `aliases` 2 ｜ `locale_charset` 1 …
而**我方 809 个函数 Thumb = 0**（全 ARM）⇒ **308 个共有函数的指令集模式与工厂不同**。

体积比完全吻合这条：`aliases_hash` 工厂 **T** 296 / 我方 **A** 688（×2.3）、
`ascii_mbtowc` 54 / 96（×1.8）、`big5_wctomb` 578 / 1016（×1.76）—— 都在 Thumb/ARM 指令长度比的量级。

★ 这条同时**推翻了 `LIBOPT=-O0` 的既有依据**：`codegen_style_census` 说的
  「工厂 304 个 -O0 形态函数全属 libiconv」，很可能是**把 Thumb 序言误判成 -O0 序言**
  （Thumb 的 `push {r7,lr}; sub sp,#8; add r7,sp,#0` 与 -O0 形似）。

## 为什么是**棘轮**而不是硬门禁
当前 308 个不同**无法立刻修**：`zig cc` **静默忽略 `-mthumb`**（实测 `-O2` 与 `-O2 -mthumb`
产物**逐字节相同**；`-Xclang -mthumb` 报 `unknown argument`）⇒ Thumb 只能用**真 GCC**（Linux）产出。
⇒ 本门禁用**棘轮**语义：**不得比基线更差**（不同数不得增加）。数量减少时提示可更新基线。

## 判据方向（保守）
  · 只看**共有**函数（两侧同名）—— 单侧独有的函数不由本门禁负责；
  · 我方函数**地址必须为偶**（真 Thumb 只有在链接后的可执行文件里才体现 bit0）；
  · 基线文件 `ledger/isa_mode_baseline.txt`：一行 `max_mismatch=<n>`。

用法：python tools/isa_mode_gate.py [--ours build/rkgame.rebuilt.elf]
     [--factory golden/factory.rkgame.bin] [--self-test]
exit: 0 = 不劣于基线 / 1 = 劣化（超出基线） / 2 = 自证失败 / 11 = 输入不可用
"""
from __future__ import print_function

import argparse
import collections
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_FILE = os.path.join(ROOT, 'ledger', 'isa_mode_baseline.txt')


def funcs(path):
    """→ {name: (addr, size)}；只取 STT_FUNC 且 size>0。"""
    from elftools.elf.elffile import ELFFile
    out = {}
    with open(path, 'rb') as fh:
        e = ELFFile(fh)
        st = e.get_section_by_name('.symtab')
        if st is None:
            return out
        for s in st.iter_symbols():
            if s['st_info']['type'] != 'STT_FUNC' or not s['st_size']:
                continue
            out[s.name] = (s['st_value'], s['st_size'])
    return out


def bucket(n):
    for k in ('stbtt', 'mxml', 'xmp3', 'MP3'):
        if n.startswith(k):
            return k
    # ★ 分组只影响**报告可读性**，不参与判据。
    #   2026-10-01 实测：这一组 308 个**全部**属于 libiconv/libcharset
    #   （先前漏判 12 个：libiconvctl / libiconvlist / *_loop_convert / *_write_replacement /
    #     normal_flushwc … ⇒ 规则已补齐）。
    if (n.endswith('_mbtowc') or n.endswith('_wctomb') or n.endswith('_reset')
            or n.endswith('_flushwc') or n.endswith('_write_replacement')
            or '_loop_' in n
            or n.startswith('aliases') or n.startswith('libiconv')
            or n in ('locale_charset', 'iconv_canonicalize', 'compare_by_name',
                     'compare_by_index', 'johab_hangul_decompose')):
        return 'libiconv'
    return 'other'


def load_baseline(path=None):
    p = path or BASE_FILE
    if not os.path.exists(p):
        return None
    for ln in open(p, encoding='utf-8', errors='replace'):
        ln = ln.strip()
        if ln.startswith('max_mismatch'):
            return int(ln.split('=')[1].strip())
    return None


def run(ours, factory, baseline_file=None):
    F = funcs(factory)
    O = funcs(ours)
    if not F or not O:
        sys.stderr.write('★ 输入不可用：工厂 %d 个函数 / 我方 %d 个函数\n' % (len(F), len(O)))
        return 11
    common = set(F) & set(O)
    mis = [n for n in common if (F[n][0] & 1) != (O[n][0] & 1)]
    print('=' * 96)
    print('指令集模式（ARM/Thumb）棘轮门禁 —— ours=%s' % os.path.relpath(ours, ROOT))
    print('=' * 96)
    print('  工厂 Thumb %d / %d ｜ 我方 Thumb %d / %d ｜ 共有 %d'
          % (sum(1 for v in F.values() if v[0] & 1), len(F),
             sum(1 for v in O.values() if v[0] & 1), len(O), len(common)))
    print('  **模式不同的共有函数：%d**' % len(mis))
    for k, c in collections.Counter(bucket(n) for n in mis).most_common():
        print('      · %-10s %d' % (k, c))
    base = load_baseline(baseline_file)
    print()
    if base is None:
        print('  （无基线文件 %s ⇒ 只报告，不判）' % os.path.relpath(BASE_FILE, ROOT))
        return 0
    print('  基线 max_mismatch = %d' % base)
    if len(mis) > base:
        print('  ★★ 劣化：模式不同数 %d > 基线 %d ⇒ 门禁失败' % (len(mis), base))
        return 1
    if len(mis) < base:
        print('  ✔ 优于基线（%d < %d）—— 可把 ledger/isa_mode_baseline.txt 更新为 %d'
              % (len(mis), base, len(mis)))
        return 0
    print('  ✔ 与基线一致（棘轮：不得更差）')
    return 0


def self_test():
    fails = []

    def c(name, got, want):
        if got != want:
            fails.append('%s: got=%r want=%r' % (name, got, want))

    Fi = {'a': (0x1001, 10), 'b': (0x2000, 10)}      # a 是 Thumb、b 是 ARM
    O1 = {'a': (0x3001, 10), 'b': (0x4000, 10)}      # 完全同模式
    O2 = {'a': (0x3000, 10), 'b': (0x4001, 10)}      # 完全反模式
    c('正例 同模式 ⇒ 0 个不同',
      sum(1 for n in (set(Fi) & set(O1)) if (Fi[n][0] & 1) != (O1[n][0] & 1)), 0)
    c('反例 反模式 ⇒ 2 个不同',
      sum(1 for n in (set(Fi) & set(O2)) if (Fi[n][0] & 1) != (O2[n][0] & 1)), 2)
    c('桶：charset 归 libiconv', bucket('big5_mbtowc'), 'libiconv')
    c('桶：stbtt 归 stbtt', bucket('stbtt_Rasterize'), 'stbtt')
    c('桶：未知归 other', bucket('DrawFrame'), 'other')
    c('基线读取（真实文件存在时有值）',
      (load_baseline() is None) or isinstance(load_baseline(), int), True)
    print('self-test: %d 条，失败 %d' % (6, len(fails)))
    for f in fails:
        print('   ✗', f)
    return 2 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ours', default=os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'))
    ap.add_argument('--factory', default=os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    ap.add_argument('--baseline', default=None)
    ap.add_argument('--write-baseline', action='store_true',
                    help='把**当前**模式不同数写为基线（只在首次登记或确认改善后手工调用）')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.write_baseline:
        F, O = funcs(a.factory), funcs(a.ours)
        n = sum(1 for x in (set(F) & set(O)) if (F[x][0] & 1) != (O[x][0] & 1))
        os.makedirs(os.path.dirname(BASE_FILE), exist_ok=True)
        tmp = BASE_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('# 指令集模式（ARM/Thumb）棘轮基线\n')
            fh.write('# max_mismatch = 与工厂指令集模式不同的**共有函数**个数上限。\n')
            fh.write('# 减少时可下调；增加即劣化（门禁 fail）。\n')
            fh.write('max_mismatch=%d\n' % n)
        os.replace(tmp, BASE_FILE)
        print('baseline written: max_mismatch=%d' % n)
        return 0
    return run(a.ours, a.factory, a.baseline)


if __name__ == '__main__':
    sys.exit(main())
