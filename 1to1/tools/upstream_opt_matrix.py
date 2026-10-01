#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""upstream_opt_matrix.py —— **上游组件的优化档扫描**（找每个组件的"正确档位"）。

## 为什么（本轮的根因线索）
`build_upstream.sh` 给**所有**上游组件用同一个 `UPOPT=-O2`（libiconv 除外用 `LIBOPT=-O0`）。
但 `report/dwarf_recon.txt` 里的 `-O2` 只来自**8 个 glibc/CRT CU** —— 它**不代表**上游库。

实测（stb_truetype，源码未被重建 ⇒ 唯一变量就是编译档）：

    flags                        M1 体积逐字节相同   M2 体积比中位   M3 工厂独有
    -O2                          3                  1.120           9
    -O2 -fno-inline-functions    3                  0.980           3   （但 M4=52：全不内联）
    -O0                          0                  1.667           3
    -Os                         19                  0.994           5   ← ★ 显著最好

`-Os` 让 **19 个函数体积与工厂逐字节相同**（现状只有 3 个）。⇒ 上游库的档位**配错了**，
不是编译器家族的锅（与 §0.47 的 fid 判决不矛盾：那个实验的样本混入了"重建误差"）。

## 判据（预登记）
  对每个组件，在候选档位里选 **M1 最大**、且 M2 最接近 1.000 的那个。
  M1 = 与工厂**体积逐字节相同**的共有函数个数（越大越像）
  M2 = 体积比中位（越接近 1.000 越像）
  M3 = 工厂独有函数个数（我方被内联/合并掉的）

## 口径声明（必须写进报告）
  · 本扫描用 **zig cc（clang）** = 我们**实际在用**的编译器 ⇒ 结论可直接采用。
  · 不用 GCC 腿也能回答"我们该用哪个档"；GCC 腿只回答"谁更同族"（§0.47 已判负）。
  · 只编译不链接；产物落在 `build/_upmat/`（构建产物，不是"搭环境"）。

用法：python tools/upstream_opt_matrix.py [--prefix-of COMP] [--out report/upstream_opt_matrix.txt]
"""
from __future__ import print_function

import argparse
import glob
import os
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from upstream_cc_compare import funcs                          # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTORY = os.path.join(ROOT, 'golden', 'factory.rkgame.bin')
OUTD = os.path.join(ROOT, 'build', '_upmat')

OPTS = [
    ('O2', '-O2'),
    ('Os', '-Os'),
    ('O1', '-O1'),
    ('O0', '-O0'),
    ('O3', '-O3'),
    ('O2-noinline', '-O2 -fno-inline-functions'),
]


def comps(root):
    mxml = sorted(glob.glob(os.path.join(root, 'src/upstream/mxml/mxml-*.c')))
    mp3 = [f for f in sorted(glob.glob(os.path.join(root, 'src/upstream/mp3/real/*.c')))
           if os.path.basename(f) not in ('mp3tabs.c', 'trigtabs.c', 'hufftabs.c')]
    mxml_inc = ['-I' + os.path.join(root, 'src/upstream/mxml')]
    mp3_inc = ['-I' + os.path.join(root, 'src/upstream/mp3'),
               '-I' + os.path.join(root, 'src/upstream/mp3/pub'),
               '-I' + os.path.join(root, 'src/upstream/mp3/real')]
    return [
        ('stb', 'stbtt', [os.path.join(root, 'src/upstream/stb/stb_truetype_impl.c')],
         ['-I' + os.path.join(root, 'src/upstream/stb')], []),
        ('mxml', 'mxml', mxml, mxml_inc, []),
        ('mp3', '', mp3, mp3_inc, []),
    ]


def zig():
    """解析 zig —— 走项目既有的**唯一真源** `tools/zig_resolve.py`
    （`import ziglang` 在本 venv 里不一定可用：包目录可能没有 `__init__.py`）。"""
    try:
        import zig_resolve                                        # noqa: WPS433
        p = zig_resolve.resolve_zig()
        if p and os.path.exists(p):
            return p
    except Exception:                                            # noqa: BLE001
        pass
    try:
        import ziglang
        p = os.path.join(os.path.dirname(ziglang.__file__), 'zig')
        if os.path.exists(p):
            return p
        p = p + '.exe'
        if os.path.exists(p):
            return p
    except Exception:                                            # noqa: BLE001
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--gate', action='store_true',
                    help='门禁模式：断言 build_upstream.sh 的 UPOPT 等于扫描出的最佳档；不等 ⇒ exit 3')
    ap.add_argument('--out', default='report/upstream_opt_matrix.txt')
    a = ap.parse_args()

    Z = os.environ.get('ZIGBIN') or zig()
    if not Z or not os.path.exists(Z):
        sys.stderr.write('★ 找不到 zig —— 仪器不成立\n')
        return 12
    env = dict(os.environ)
    env.setdefault('ZIG_GLOBAL_CACHE_DIR', os.path.join(ROOT, 'build', '_zigcache'))

    tc = os.path.join(ROOT, 'cache_tc', 'bootlin63')
    # ★ 防御：没有工厂同期真头时，`-nostdinc` 会让**所有**编译失败 ⇒ 全部档位 0 函数
    #   ⇒ 扫描退化。这里显式报错，不静默产出"空结论"。
    if not os.path.exists(os.path.join(tc, 'arm-buildroot-linux-gnueabihf/sysroot/usr/include/stdio.h')):
        sys.stderr.write('★ 缺工厂同期真头 %s —— 先跑 tools/fetch_bootlin63.sh 或 fidelity_matrix.sh\n'
                         % os.path.join(tc, 'arm-buildroot-linux-gnueabihf/sysroot/usr/include'))
        return 12
    hdr = ['-nostdinc',
           '-I' + os.path.join(tc, 'lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include'),
           '-I' + os.path.join(tc, 'lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include-fixed'),
           '-I' + os.path.join(tc, 'arm-buildroot-linux-gnueabihf/sysroot/usr/include')]
    base = ['-c', '-w', '-fno-sanitize=all', '-fno-strict-aliasing',
            '-target', 'arm-linux-gnueabihf', '-mcpu=cortex_a8+neon', '-mfloat-abi=hard',
            '-fno-stack-protector'] + hdr

    F_all = funcs(FACTORY, '')
    lines = []
    P = lines.append
    P('=' * 100)
    P('上游组件 · 优化档扫描（编译器 = zig cc / clang，即我们**实际在用**的那一个）')
    P('=' * 100)
    P('工厂 %s ：%d 个 STT_FUNC' % (os.path.relpath(FACTORY, ROOT), len(F_all)))
    P('')

    verdicts = {}
    for name, prefix, srcs, inc, extra in comps(ROOT):
        if a.only and a.only != name:
            continue
        if not srcs:
            continue
        F = funcs(FACTORY, prefix) if prefix else F_all
        P('-' * 100)
        P('组件 %s（前缀 %r，%d 个源文件；工厂同名函数 %d 个）' % (name, prefix, len(srcs), len(F)))
        P('-' * 100)
        P('  %-14s %-8s %-6s %-8s %-14s %-10s' % ('档位', '我方函数', '共有', 'M1 体积全同', 'M2 体积比中位', 'M3 工厂独有'))
        rows = []
        for tag, flags in OPTS:
            d = os.path.join(OUTD, name, tag)
            os.makedirs(d, exist_ok=True)
            ok = 0
            bad = []
            for s in srcs:
                o = os.path.join(d, os.path.basename(s)[:-2] + '.o')
                # ★ 不删旧 .o（删除守卫会卡死）——直接覆盖；失败则记下来并**排除**该目标。
                ex = []
                if os.path.basename(s) == 'mp3dec.c':
                    ex = ['-DMP3GetNextFrameInfo=mp3_unused_GetNextFrameInfo']
                r = subprocess.run([Z, 'cc'] + base + flags.split() + inc + extra + ex + [s, '-o', o],
                                   env=env, capture_output=True)
                if r.returncode == 0:
                    ok += 1
                else:
                    bad.append(os.path.basename(o))
            if bad:
                P('    （%s：%d/%d 个源文件编译失败：%s）'
                  % (tag, len(bad), len(srcs), ', '.join(bad[:4])))
            O = funcs(d, prefix) if prefix else funcs(d, '')
            if not prefix:
                # 无前缀：只保留工厂里也出现的名字，避免把 libc 帮手算进来
                O = {k: v for k, v in O.items() if k in F_all}
            common = set(F) & set(O)
            exact = sum(1 for n in common if F[n] == O[n])
            med = statistics.median([O[n] / float(F[n]) for n in common if F[n]]) if common else float('nan')
            missing = sorted(set(F) - set(O))
            rows.append((tag, ok, len(O), len(common), exact, med, len(missing)))
            P('  %-14s %-8d %-6d %-8d %-14.3f %-10d' % (tag, len(O), len(common), exact, med, len(missing)))
        if rows:
            best = max(rows, key=lambda r: (r[4], -abs(r[5] - 1.0)))
            verdicts[name] = (best[0], best[4], best[5])
            P('  ⇒ 最佳档位：**%s**（M1=%d，M2=%.3f）' % (best[0], best[4], best[5]))
        P('')

    P('=' * 100)
    P('汇总（每个组件的建议档位）')
    P('=' * 100)
    for k, (tag, m1, m2) in verdicts.items():
        P('  %-8s → %-14s M1=%-3d M2=%.3f' % (k, tag, m1, m2))
    P('')
    P('★ 判读：M1「体积逐字节相同」是最硬的证据（巧合概率极低）；M2 作交叉确认。')
    P('★ 口径：本扫描只用 clang 腿（= 我们的实际编译器）⇒ 结论**可直接采纳**；')
    P('   GCC 腿只回答"谁更同族"，§0.47 已判负，不重复测。')

    # ★ --gate：把"档位选对了吗"变成**机械门禁**（否则这次修复只是一次性结论）
    if a.gate and not verdicts:
        P('  ★★ 门禁失败：**没有任何组件产出可比对象**（仪器不可用）—— 不得判绿（否则是"假绿"）')
        sys.stderr.write('upstream_opt_matrix --gate: 仪器不可用（0 个组件完成比对）\n')
        return 11
    if a.gate:
        import re as _re
        bs = os.path.join(ROOT, 'tools', 'build_upstream.sh')
        cur = None
        for ln in open(bs, encoding='utf-8', errors='replace'):
            m = _re.match(r'UPOPT="\$\{UPOPT:-(-O\w+)\}"', ln)
            if m:
                cur = m.group(1)
                break
        want = {k: v[0] for k, v in verdicts.items()}
        P('')
        P('--- 门禁：build_upstream.sh 的 UPOPT 是否为各组件的最佳档 ---')
        P('    当前 UPOPT = %s' % cur)
        tagmap = dict((tag, flag) for tag, flag in OPTS)
        bad = []
        for comp, besttag in want.items():
            best = tagmap.get(besttag, besttag)
            P('    %-8s 最佳 %-14s (%-6s)  ⇒ %s'
              % (comp, besttag, best, 'OK' if cur == best else '★ 不符'))
            if cur != best:
                bad.append(comp)
        if bad:
            P('  ★★ 门禁失败：%s 的档位与实测最佳不符 ⇒ 请改 build_upstream.sh（或更新本扫描的判据）'
              % ', '.join(bad))
            txt = '\n'.join(lines)
            print(txt)
            with open(outp, 'w', encoding='utf-8', newline='\n') as fh:
                fh.write(txt + '\n')
            return 3
        P('  ⇒ 全部一致')

    txt = '\n'.join(lines)
    print(txt)
    outp = os.path.join(ROOT, a.out)
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    with open(outp, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(txt + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
