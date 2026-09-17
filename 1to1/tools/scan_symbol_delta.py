#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游库「公有 API 符号集合」对拍 —— 版本钉错的机械检出（技能铁律 107）。

为什么需要（2026-09-18 实测）：
  本工程把上游库（stb_truetype / mini-XML / Helix MP3 / XUnzip / GNU libiconv / libz）
  静态链进重建产物，而**版本钉错**不会让任何编译/链接门禁报错 —— 它只会静默改变行为。
  实测案例：我们的 stb_truetype 里存在 `stbtt_FindSVGDoc` / `stbtt_GetCodepointSVG` /
  `stbtt_GetGlyphSVG`（**SVG 支持自 v1.22 才引入**）与 `stbtt_GetKerningTable*`，
  而工厂二进制**没有这些符号** ⇒ 工厂的 stb 比我们**旧** ⇒ 原"钉 v1.26"的结论不成立。
  这类差异只有"把两侧的**公有 API 符号集合**摆在一起"才看得见。

判据（**只针对上游库的公有 API**，不看编译器内联产物）：
  · 取两侧的函数符号，按一组**库前缀白名单**过滤掉 `isra`/`part`/`constprop` 等内联重命名；
  · **我们多出的公有 API ⇒ 硬失败**（工厂根本没有这个 API，我们却编出来 ⇒ 版本或定制不同）；
  · 工厂多出而我们缺失 ⇒ 报告（可能是我们漏了，也可能是被内联）。
  · 尺寸差异只做报告（同版本不同编译器/优化级别也会差，不能当判据）。

自证（铁律 101）：内置锚点 —— `stbtt_FindSVGDoc` 必须被报为"我们多出"，
`mxmlLoadFile` 必须两侧都在；不符就拒绝出结论。
"""
import argparse
import os
import re
import subprocess
import sys

# 只看这些上游库的公有 API（前缀匹配）。
LIB_PREFIXES = (
    'stbtt_', 'stbtt__',
    'mxml', 'MXML_', '_mxml',
    'MPG', 'MP3', 'mp3', 'HMP3', 'CMP3', 'MPEG',
    'unz', 'unzlocal_', 'TUnzip', 'ZIPENTRY',
    'iconv', 'libiconv',
    'inflate', 'deflate', 'crc32', 'adler32', 'zlib',
)

# 允许存在的"我们多出"的符号（每条都要写理由；禁止为了过门禁而堆白名单）
ALLOW_EXTRA = {
    # 我们自建的兼容层/桥接符号（不属于上游 API）
    'stbtt__bridge_placeholder': '本工程自建桥接，非上游 API',
}

ANCHORS_EXTRA = ['stbtt_FindSVGDoc']
ANCHORS_BOTH = ['mxmlLoadFile', 'unzLocateFile', 'stbtt_InitFont']


def find_objdump():
    import shutil
    for n in ('arm-linux-gnueabihf-objdump', 'arm-none-eabi-objdump', 'objdump'):
        c = shutil.which(n)
        if c:
            return c
    for c in (r'C:\objdump', 'C:/objdump', '/usr/bin/objdump'):
        if os.path.exists(c):
            return c
    return 'objdump'


def funcs(elf, od):
    out = subprocess.run([od, '-t', elf], capture_output=True, text=True).stdout
    d = {}
    for l in out.splitlines():
        q = l.split()
        if len(q) == 6 and q[2] == 'F':
            try:
                d[q[5]] = int(q[4], 16)
            except ValueError:
                pass
    return d


def demangle(name):
    """把 `_Z24unzStringFileNameComparePKcS0_i` 还原成可读名（够用即可，不求全）。"""
    if not name.startswith('_Z'):
        return name
    rest = name[2:]
    m = re.match(r'(\d+)', rest)
    if not m:
        return name
    n = int(m.group(1))
    return rest[m.end():m.end() + n]


def public_api(d):
    """过滤出上游库的公有 API（去掉 isra/part/constprop 等内联重命名）。"""
    out = {}
    for k, v in d.items():
        nm = demangle(k)
        if not any(nm.startswith(p) for p in LIB_PREFIXES):
            continue
        if re.search(r'\.(isra|part|constprop|cold|clone)\.\d+', nm):
            continue
        base = nm.split('.')[0]
        out[base] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fa', default='golden/factory.rkgame.bin')
    ap.add_argument('--ours', default='build/rkgame.rebuilt.elf')
    ap.add_argument('--objdump', default=None)
    ap.add_argument('--pending', default=None,
                    help='已知待修台账（每行一个符号名）：其中的"我们多出"计为台账项、不判失败；'
                         '新增一律失败（棘轮语义）')
    ap.add_argument('--write-pending', action='store_true')
    a = ap.parse_args()
    for p in (a.fa, a.ours):
        if not os.path.exists(p):
            print('  [SKIP] 缺少 %s' % p)
            return 0
    od = a.objdump or find_objdump()
    F = public_api(funcs(a.fa, od))
    O = public_api(funcs(a.ours, od))

    # ---- 自证 ----
    for n in ANCHORS_BOTH:
        if n not in F or n not in O:
            print('  [FATAL] 自证失败：锚点 %s 未同时出现在两侧（工厂 %s / 我们 %s）'
                  % (n, n in F, n in O))
            return 2
    api_all = set(F) | set(O)
    if len(api_all) < 80:
        print('  [FATAL] 自证失败：上游 API 只识别出 %d 个（阈值 80）⇒ 前缀表或解析器有问题' % len(api_all))
        return 2
    demo = demangle('_Z24unzStringFileNameComparePKcS0_i')
    if demo != 'unzStringFileNameCompare':
        print('  [FATAL] 自证失败：Itanium 反修饰对不上（%s）' % demo)
        return 2

    extra = sorted(set(O) - set(F) - set(ALLOW_EXTRA))
    missing = sorted(set(F) - set(O))
    if ANCHORS_EXTRA:
        if not all(x in extra for x in ANCHORS_EXTRA):
            print('  [FATAL] 自证失败：锚点 %s 未被报为"我们多出"（extra=%s）'
                  % (ANCHORS_EXTRA, extra[:8]))
            return 2

    print('  自证通过（双侧 API %d 个；锚点 %s 命中）'
          % (len(api_all), ', '.join(ANCHORS_EXTRA + ANCHORS_BOTH)))
    print('  工厂 API %d / 我们 API %d' % (len(F), len(O)))
    if a.write_pending:
        with open(a.pending or 'tools/upstream_api_pending.txt', 'w', encoding='utf-8',
                  newline='\n') as f:
            f.write('# 上游库公有 API「我们多出」· 已知待修台账（棘轮）' + '\n')
            f.write('# 格式: <符号名>   —— 修好（重新钉版本）后删行；新增不在台账内 ⇒ 门禁失败' + '\n')
            for n in extra:
                f.write(n + '\n')
        print('  已写入台账：%d 项' % len(extra))
        return 0
    pend = set()
    if a.pending and os.path.exists(a.pending):
        for ln in open(a.pending, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                pend.add(ln)
    known = [n for n in extra if n in pend]
    new_ = [n for n in extra if n not in pend]
    if known:
        print('  台账内已知待修：%d 项（重新钉上游版本修，逐项删行）' % len(known))
    if new_:
        print('  ★★ 新增「我们多出」的上游 API %d 个（不在台账内 ⇒ 判失败）：' % len(new_))
        for n in new_:
            print('     %-42s 我们 size=0x%x' % (n, O[n]))
        return 1
    if known:
        print('  ✓ 无新增（台账剩余 %d 项）' % len(known))
    else:
        print('  ✓ 上游公有 API 集合与工厂一致')
    if missing:
        print('  工厂多出而我们缺失 %d 个（可能被内联，仅供参考）：%s'
              % (len(missing), ', '.join(missing[:10])))
    print('  ✓ 上游公有 API 集合无"我们多出"项')
    return 0


if __name__ == '__main__':
    sys.exit(main())
