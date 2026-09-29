#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ruler_baseline.py —— 行为尺「基线」的唯一权威取值器（纪律 50 的正确实现）。

## 为什么存在（2026-09-29）
`compiler_align_exp.sh` / `header_align_exp.sh` / `buildfact_align_exp.sh` / `_ca_all.sh`
四份脚本把 clang 基线**硬编码**成 `DIVERGE 45`。这个数字**必然过期**：
主链换链接驱动（arm C）后权威值是 **44**。后果是**判决方向被污染** ——
一个 GCC 臂只要拿到 44 就会被判「采用」，而它其实**没改善**。

## 判据（本工具的全部逻辑）
基线**不是**一个手抄的数字，而是「**当前交付产物自己在行为尺上的成绩**」。
所以本工具：
  1) 取 `build/rkgame.rebuilt.elf` 的 sha256（前 16 位，与报告同口径）；
  2) 在 `report/` 下扫描所有 `.txt`，找出「被测产物 sha256 == 当前产物 sha」的报告；
  3) 取其中 mtime 最新的一份，解析 `共有函数` / `汇总：PASS x ｜ DIVERGE y ｜ TRUNC z ｜ SKIP w`；
  4) 打印机器可读的一行：`BASE <sha16> <共有> <PASS> <DIVERGE> <TRUNC> <SKIP> <报告路径>`。
**产物一变，旧报告自动失配 ⇒ 基线自动失效**（宁可不给，也不给过期的）。

## 退出码
0 = 取到（stdout 单行 `BASE ...`）
7 = 取不到（**fail-closed**：没有与当前产物 sha 匹配的报告）。不得回退到硬编码。
9 = 前置缺失（产物不存在 / report 目录不存在）。

用法:
    python3 tools/ruler_baseline.py                 # 打印基线行
    python3 tools/ruler_baseline.py --field div     # 只打印 DIVERGE 数字
    python3 tools/ruler_baseline.py --artifact X    # 对别的产物取基线（实验臂用不到）
"""
import argparse
import glob
import hashlib
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEF_ART = os.path.join(ROOT, 'build', 'rkgame.rebuilt.elf')
REPORT_DIR = os.path.join(ROOT, 'report')

RE_OURS = re.compile(r'被测产物[：:]\s*(\S+)\s*\(sha256\s+([0-9a-fA-F]{4,64})\)')
# ★ 2026-09-29 修（仪器必须跟着口径走）：汇总行在 2026-09-29 新增了第 5 桶
#   `REFDEAD(参照侧早死)`，插在 TRUNC 与 SKIP 之间。旧正则要求 `TRUNC n ｜ SKIP` **紧邻**，
#   于是**新版报告一律匹配不上** ⇒ 本工具静默回落到昨天的旧 stdout 捕获（数字 44，已过期）。
#   ⇒ 正则改为「REFDEAD 段可选」，并把它的值一并取出。
RE_SUM = re.compile(
    r'汇总：PASS\s+(\d+)\s*｜\s*DIVERGE\s+(\d+)'
    r'\s*｜\s*TRUNC[^0-9]*(\d+)'
    r'(?:\s*｜\s*REFDEAD[^0-9]*(\d+))?'
    r'\s*｜\s*SKIP\s+(\d+)')
RE_SHARED = re.compile(r'共有函数\s+(\d+)')


def sha16(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--artifact', default=DEF_ART)
    ap.add_argument('--report-dir', default=REPORT_DIR)
    ap.add_argument('--field', choices=['div', 'pass', 'shared'], default=None)
    ap.add_argument('--self-test', action='store_true',
                    help='只跑正则/解析的自证锚点（不读任何本项目数据）')
    a = ap.parse_args()

    if a.self_test:
        return self_test()

    if not os.path.isfile(a.artifact):
        print('!! 产物不存在：%s' % a.artifact, file=sys.stderr)
        return 9
    if not os.path.isdir(a.report_dir):
        print('!! report 目录不存在：%s' % a.report_dir, file=sys.stderr)
        return 9

    want = sha16(a.artifact)
    hits = []
    for p in glob.glob(os.path.join(a.report_dir, '*.txt')):
        try:
            t = io.open(p, encoding='utf-8', errors='replace').read()
        except Exception:
            continue
        m = RE_OURS.search(t)
        if not m:
            continue
        got = m.group(2).lower()
        # 报告里可能只写前 16 位；按较短者对齐比较
        n = min(len(got), len(want))
        if n < 8 or got[:n] != want[:n]:
            continue
        s = RE_SUM.search(t)
        if not s:
            continue
        shared = RE_SHARED.search(t)
        hits.append(dict(
            path=p, mtime=os.path.getmtime(p), sha=want,
            shared=int(shared.group(1)) if shared else -1,
            pa=int(s.group(1)), dv=int(s.group(2)), tr=int(s.group(3)),
            rf=int(s.group(4)) if s.group(4) else -1, sk=int(s.group(5)),
        ))

    if not hits:
        print('!! 没有找到与当前产物 sha 匹配的行为尺报告（产物 sha16=%s）' % want, file=sys.stderr)
        print('   修：先对 build/rkgame.rebuilt.elf 跑一次权威行为尺，例如', file=sys.stderr)
        print('       python3 tools/diff_exec.py --batch --steps 3000 \\', file=sys.stderr)
        print('           --ours build/rkgame.rebuilt.elf --out report/_final_diff.txt', file=sys.stderr)
        print('   ★ 不允许回退到硬编码基线（纪律 50）。', file=sys.stderr)
        return 7

    h = max(hits, key=lambda x: x['mtime'])
    if a.field == 'div':
        print(h['dv'])
    elif a.field == 'pass':
        print(h['pa'])
    elif a.field == 'shared':
        print(h['shared'])
    else:
        # ★ 字段顺序不可变：$5 必须是 DIVERGE（下游 `ca_judge.sh`/`_ca_all.sh` 用 awk 取 $5）。
        #   REFDEAD 追加在**末尾**（$8），旧读取方无感。
        print('BASE %s %s %s %s %s %s %s %s' % (
            h['sha'], h['shared'], h['pa'], h['dv'], h['tr'], h['sk'],
            h['rf'], os.path.relpath(h['path'], ROOT)))
    return 0


def self_test():
    """纯函数自证：正则必须同时吃下**旧 4 桶**与**新 5 桶**汇总行，
    且 REFDEAD 缺失时按 -1 表示（不得当成 0 —— "没有这一栏" ≠ "这一栏是 0"）。"""
    chk = 0
    bad = 0

    def c(name, got, want):
        nonlocal chk, bad
        chk += 1
        if got != want:
            bad += 1
            print('  ✗ %s  got=%r want=%r' % (name, got, want))
        else:
            print('  ✓ %s' % name)

    old = '汇总：PASS 732 ｜ DIVERGE 45 ｜ TRUNC(不可判) 5 ｜ SKIP 0'
    new = '汇总：PASS 737 ｜ DIVERGE 40 ｜ TRUNC(不可判) 5 ｜ REFDEAD(参照侧早死) 0 ｜ SKIP 0'
    m = RE_SUM.search(old)
    c('旧 4 桶可解析', (int(m.group(1)), int(m.group(2)), int(m.group(3)),
                       m.group(4), int(m.group(5))), (732, 45, 5, None, 0))
    m = RE_SUM.search(new)
    c('新 5 桶可解析（REFDEAD 在 TRUNC 与 SKIP 之间）',
      (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5))),
      (737, 40, 5, 0, 0))
    c('REFDEAD 非零也解析', int(RE_SUM.search(
        new.replace('REFDEAD(参照侧早死) 0', 'REFDEAD(参照侧早死) 34')).group(4)), 34)
    c('缺 REFDEAD ⇒ None（不得当 0）', RE_SUM.search(old).group(4), None)
    c('两臂 sha16 正则取到的是 sha 段',
      RE_OURS.search('  被测产物：build\\rkgame.rebuilt.elf (sha256 b21a3f12cdb2a84e)').group(2),
      'b21a3f12cdb2a84e')
    print('  合计 %d 条，失败 %d 条' % (chk, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
