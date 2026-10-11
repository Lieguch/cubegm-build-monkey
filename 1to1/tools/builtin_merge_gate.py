#!/usr/bin/env python3
"""builtin_merge_gate.py — 「分配类 builtin 合并」门禁（静态形态留痕）。

★ 为什么需要（第 150/151 轮血泪）：
  clang 会把源码里的
      p = malloc(n);  memset(p, 0, n);
  合并成 `calloc(n, 1)`（标准优化）；工厂 gcc 6.2 **不合并**，保留两步。
  ⇒ 运行期 `calls_ext` 出现 `calloc` vs `malloc`+`memset` 的差异（真实差异，非噪声）。
  第 150 轮实测 `-fno-builtin-malloc` 可精确对齐工厂形态（三元组 0/3/1 逐项相同）。

★ 口径纪律（第 145/148/151 轮连续踩坑，这里定死）：
  分配调用在两侧都**必须经 PLT 槽解析**才能拿到名字：
    · 工厂（BFD/gold）PLT 条目**具名** ⇒ objdump 直接显示 `<malloc@plt>`；
    · 我方（ld.lld + zig）PLT 条目**无具名符号** ⇒ 同一调用只是 `bl 0x4015d0`。
  ⇒ **只 grep 助记符会得到"两侧都是 0"的假象**（本门禁第一版就这样错的）。
  ⇒ 唯一真源 = `diff_exec.Bin.plt_map`（第 150 轮实测：工厂 105 / 我方 104 槽），
     本门禁**只调用它**，不另写一套 PLT 解析（纪律：同一规则禁止写两处）。

⚠ **只登记，不判失败**：clang 的合并是合法优化，真判据是 `diff_exec` 的运行期
  `calls_ext`；本门禁是静态形态留痕，供人工复核时快速定位。

用法:
  python3 tools/builtin_merge_gate.py --func TestLibz0 [--func ...]
  python3 tools/builtin_merge_gate.py --all
退出: 0（始终；理由见上）
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

ALLOC = ('calloc', 'malloc', 'memset', 'realloc', 'free')
FUNC_SPLIT = re.compile(r'^[0-9a-f]{8} <([^>]+)>:')
# `bl 0x4015d0`（匿名目标）或 `bl 9778 <malloc@plt>`（具名）
# ★★ 第 151 轮第三次栽在 objdump 文本上：目标地址是 **6 位**十六进制（'4014f0'，
#   无前导零），我原先写死  ⇒ 正则匹配不到任何 bl ⇒ 统计恒 0。
#   ⇒ 地址一律用 ，不假设宽度（同第 145/148 轮：别对工具输出做定宽假设）。
CALL_RE = re.compile(r'\b(?:bl|blx)\s+([0-9a-f]{4,8})(?:\s+<([^>]+)>)?')


def alloc_counts(binpath, wanted=None):
    """{函数名: {分配函数名: 次数}}；名字经 plt_map 解析（唯一真源）。"""
    import diff_exec as de
    b = de.Bin(binpath)
    dis = subprocess.run(['arm-linux-gnueabihf-objdump', '-d', binpath],
                         capture_output=True, text=True,
                         errors='replace').stdout
    res = {}
    cur = None
    for ln in dis.splitlines():
        h = FUNC_SPLIT.match(ln)
        if h:
            cur = h.group(1)
            res.setdefault(cur, {})
            continue
        if not cur:
            continue
        m = CALL_RE.search(ln)
        if not m:
            continue
        nm = m.group(2)
        # ★★ 第 151 轮实测踩坑：ld.lld 会让 objdump 把 PLT 目标显示成**伪符号名**
        #   `<__f_bss_pad_base+0x1f4f0>` —— 它带 `+0x` 偏移，**不是**真符号名。
        #   若直接采信它，就永远拿不到 `malloc`/`calloc` 真实名（本门禁第一版因此全 0）。
        #   ⇒ 判据：名字里含 `+0x` ⇒ 一律回落到 `plt_map`（唯一真源）。
        # ★★ 口径必须**两侧对称**（第 151 轮实测）：工厂侧 objdump 显示
        #   `<malloc@plt>`（真名），我方显示 `<__f_bss_pad_base+0x1f4f0>`（伪名）。
        #   若工厂侧采信真名、我方走 plt_map ⇒ **两侧口径不对称**，会出现
        #   「工厂 0 / 我方 N」这种假差异（第 151 轮第一版实测就是这样）。
        #   ⇒ 两侧**一律优先查 plt_map**（唯一真源），查不到才用 objdump 显示名。
        via_plt = b.plt_map.get(int(m.group(1), 16))
        nm = via_plt if via_plt is not None else nm
        if nm in ALLOC:
            res[cur][nm] = res[cur].get(nm, 0) + 1
    if wanted:
        return {k: v for k, v in res.items() if k in wanted}
    return {k: v for k, v in res.items() if v}


def fmt(d):
    return ' '.join('%s=%d' % (k, d[k]) for k in sorted(d)) if d else '(无)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ours', default=os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf'))
    ap.add_argument('--factory', default=os.path.join(ROOT, 'golden', 'factory.rkgame.bin'))
    ap.add_argument('--func', action='append', default=None)
    ap.add_argument('--all', action='store_true')
    a = ap.parse_args()

    print('== builtin_merge_gate（第 151 轮引入）==')
    print('  口径：分配调用名**经 plt_map 解析**（唯一真源 = diff_exec.Bin.plt_map）')
    print('  ⚠ 只登记形态差异，**不判失败**（合并是合法优化；真判据是 calls_ext）')
    print('')

    if a.all:
        F = alloc_counts(a.factory)
        O = alloc_counts(a.ours)
        keys = sorted(set(F) | set(O))
        n = 0
        for k in keys:
            f, o = F.get(k, {}), O.get(k, {})
            if f == o:
                continue
            n += 1
            print('  %-34s F[%s]  O[%s]' % (k, fmt(f), fmt(o)))
        print('')
        print('  形态不同的函数 = %d / %d' % (n, len(keys)))
        return 0

    if not a.func:
        print('  请给 --func NAME 或 --all')
        return 0
    want = set(a.func)
    F, O = alloc_counts(a.factory, want), alloc_counts(a.ours, want)
    print('  %-30s %-32s %-32s %s' % ('函数', '工厂', '我方', ''))
    for k in sorted(want):
        f, o = F.get(k, {}), O.get(k, {})
        print('  %-30s %-32s %-32s %s'
              % (k, fmt(f), fmt(o), '一致' if f == o else '★差异'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
