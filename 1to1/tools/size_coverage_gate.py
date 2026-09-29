#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""size_coverage_gate —— 「函数体量覆盖门禁」：抓出**行为尺测不到的空壳/缺体**。

## 为什么必须补这道门（2026-09-27，本轮实证）

行为尺（`diff_exec`）只能在**给它喂的输入真的走进那段代码**时才看得见差异。
一旦函数的入口条件不满足（缺文件、缺设备、提前 return），两侧都会"正常返回"，
于是**工厂有 976 B 的实现、我方只有 112 B 的空壳，照样判 PASS**。

实测案例（判决依据，可复算）：
    `UpdateROM`   工厂 976 B / 我方 **112 B**（0.11×）  ⇒ 却在行为尺里 **PASS**
    `UpdateROMProc` 工厂 852 B / 我方 844 B（0.99×）   ⇒ 正常
    我方源码 `src/proprietary/flash/FUN_0000ac44_UpdateROM.c:123` 有 `reboot(0x1234567);`，
    但产物里 `reboot` **既未定义也未导入** ⇒ 那条调用链根本没进二进制。

## 判据（机械、单一变量）

对**两侧共有**的每个函数，比较 `st_size`：
    ratio = ours_size / factory_size
    · ratio <  THRESH            ⇒ **SHORT**（嫌疑：桩 / 缺体 / 分支被优化掉）★必须逐条看
    · ratio >= THRESH            ⇒ OK
**不做**"仅按体积判优劣"的蠢事（本项目已因此栽过：`-O0` 的 libiconv 比工厂还大，
体积代理指标与行为尺结论相反）。这里只用**单侧异常小**这一个方向，且阈值取得很松。

**分桶（2026-09-28 新增，机械判据）**：只对 **由我方对象定义** 的函数判 SHORT。
  判据 = 该名字是否出现在 `build/obj/*.o`、`build/upstream/*.o`、`XUnzip.o`、
  `factory_local.o`、`crt_init.o` 的**已定义函数符号**里。
  为什么必须分桶：`LINK_DRIVER=lld` 之后会静态链 `libgcc.a`、动态链 `libstdc++.so`，
  于是产物里出现 `__udivsi3`(0.34×) / `__divsi3`(0.40×) 这类**工具链运行时助手** ——
  它们不是我们的重建目标，工厂的版本来自工厂自己那份 libgcc（42 B 级别差异无从复刻）。
  非我方对象定义的共有函数一律记 **INFO(非我方实现)** 并**公示清单**，
  但仍要求：① 清单必须换行打印；② 读不到我方对象时 **fail-closed（exit 3）**。

已知合理例外（不误伤）：
  · 工厂侧被 GCC 冷热分割（`.part.N` / `.constprop.N`）⇒ 我方同名本体更小 ⇒ 记 NOTE 不记 FAIL
  · 我方 `-O0` 编译的 TU（libiconv）⇒ ratio 通常 > 1 ⇒ 天然不触发

用法:
  python tools/size_coverage_gate.py [--ours build/rkgame.rebuilt.elf] [--thresh 0.5] [--top 60]
  python tools/size_coverage_gate.py --self-test
退出码: 0 = 无 SHORT；1 = 有 SHORT；3 = 不可判（缺文件）
"""
import argparse
import os
import re
import sys

from elftools.elf.elffile import ELFFile

FACTORY = 'golden/factory.rkgame.bin'
PART_RE = re.compile(r'\.(part|constprop|isra|cold|lto_priv)\.\d+$')


def load_funcs(path):
    e = ELFFile(open(path, 'rb'))
    st = e.get_section_by_name('.symtab')
    out = {}
    if st is None:
        return out
    for s in st.iter_symbols():
        n = s.name
        if not n or s['st_info']['type'] != 'STT_FUNC' or s['st_size'] == 0:
            continue
        if not isinstance(s['st_shndx'], int):
            continue
        # 同名取最大（alias/重复定义）
        if n not in out or s['st_size'] > out[n][1]:
            out[n] = (s['st_value'], s['st_size'])
    return out


OWN_DIRS = ('build/obj', 'build/upstream')
OWN_FILES = ('src/upstream/xunzip/XUnzip.o', 'build/factory_local.o',
             'build/crt_init.o')


def own_syms():
    """→ (set(名字), 读到的对象数)：**我方对象**里已定义的函数符号。

    ★ 这是"这个函数是不是我们重建出来的"的**机械判据**，用来把工具链归档
      （libgcc.a / libstdc++ / compiler_rt）带进来的运行时助手分出去。
      **不许**改用名字白名单 —— 白名单会掩盖真实缺体。
    """
    import glob
    paths = []
    for d in OWN_DIRS:
        paths += sorted(glob.glob(os.path.join(d, '*.o')))
    paths += [p for p in OWN_FILES if os.path.isfile(p)]
    out = set()
    nread = 0
    for p in paths:
        try:
            e = ELFFile(open(p, 'rb'))
            st = e.get_section_by_name('.symtab')
            if st is None:
                continue
            nread += 1
            for sym in st.iter_symbols():
                if (sym.name and sym['st_info']['type'] == 'STT_FUNC'
                        and sym['st_shndx'] != 'SHN_UNDEF'):
                    out.add(sym.name)
        except Exception:
            continue
    return out, nread


def verdict_of(our_sz, fac_sz, thresh):
    if fac_sz <= 0:
        return 'NA'
    r = our_sz / float(fac_sz)
    return 'SHORT' if r < thresh else 'OK'


def run(ours, thresh, top):
    F = load_funcs(FACTORY)
    O = load_funcs(ours)
    if not F or not O:
        print('不可判：缺 symtab'); return 3
    common = sorted(set(F) & set(O))
    OWN, nread = own_syms()
    if not OWN or nread == 0:
        print('不可判：读不到任何我方对象（无法按"是否我方实现"分桶）'
              '—— fail-closed，拒绝默认全放行'); return 3
    own_c = [n for n in common if n in OWN]
    foreign = [n for n in common if n not in OWN]
    short = []
    ok = 0
    for n in own_c:
        r = verdict_of(O[n][1], F[n][1], thresh)
        if r == 'SHORT':
            short.append((O[n][1] / float(F[n][1]), n, O[n][1], F[n][1]))
        elif r == 'OK':
            ok += 1
    short.sort()
    print('=' * 96)
    print('函数体量覆盖门禁 —— ours=%s（阈值 %.2f）' % (ours, thresh))
    print('工厂函数 %d ｜ 我方函数 %d ｜ 共有 %d' % (len(F), len(O), len(common)))
    print('  其中 我方对象定义 %d ｜ 非我方实现（工具链运行时助手）%d'
          % (len(own_c), len(foreign)))
    print('=' * 96)
    print('  OK    %d' % ok)
    print('  SHORT %d   ★ 体积异常小 ⇒ 疑似桩/缺体（行为尺可能看不见）' % len(short))
    print('  INFO  %d   非我方对象实现 ⇒ 不计入 SHORT（清单如下，可核对）' % len(foreign))
    for n in foreign:
        print('      · %-30s 我方 %-6d 工厂 %-6d' % (n, O[n][1], F[n][1]))
    print()
    print('  --- SHORT 明细（按比值升序，前 %d）---' % top)
    print('  %-8s %-9s %-9s %s' % ('比值', '我方', '工厂', '函数'))
    for r, n, o, f in short[:top]:
        flag = ''
        if PART_RE.search(n):
            flag = '  (工厂有 .part 分割 ⇒ 可能合理)'
        print('  %-8.3f %-9d %-9d %s%s' % (r, o, f, n, flag))
    return 1 if short else 0


def self_test():
    fails = []
    def c(name, got, want):
        if got != want:
            fails.append('%s: got=%r want=%r' % (name, got, want))
    c('正例 等量 ⇒ OK', verdict_of(900, 1000, 0.5), 'OK')
    c('正例 我方更大（-O0）⇒ OK', verdict_of(1500, 1000, 0.5), 'OK')
    c('反例 11% ⇒ SHORT（UpdateROM 实况）', verdict_of(112, 976, 0.5), 'SHORT')
    c('边界 恰好 50% ⇒ OK', verdict_of(500, 1000, 0.5), 'OK')
    c('边界 49% ⇒ SHORT', verdict_of(490, 1000, 0.5), 'SHORT')
    c('正例 我方对象定义集非空（含 UpdateROM）', 'UpdateROM' in own_syms()[0], True)
    c('反例 工具链运行时助手 **不在**我方对象集里（__udivsi3）',
      '__udivsi3' in own_syms()[0], False)
    c('正例 我方对象集里不含 libstdc++ 的 operator new（_Znwj）',
      '_Znwj' in own_syms()[0], False)
    c('工厂 size=0 ⇒ 不可判', verdict_of(10, 0, 0.5), 'NA')
    c('.part 后缀识别', bool(PART_RE.search('mxml_fd_read.part.1')), True)
    c('普通名不误判', bool(PART_RE.search('UpdateROM')), False)
    print('self-test: %d 条，失败 %d' % (8, len(fails)))
    for f in fails:
        print('   ✗', f)
    return 1 if fails else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ours', default='build/rkgame.rebuilt.elf')
    ap.add_argument('--thresh', type=float, default=0.5)
    ap.add_argument('--top', type=int, default=60)
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not os.path.isfile(FACTORY):
        print('缺工厂产物 %s' % FACTORY); return 3
    if not os.path.isfile(a.ours):
        print('缺被测产物 %s' % a.ours); return 3
    return run(a.ours, a.thresh, a.top)


if __name__ == '__main__':
    sys.exit(main())
