#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""执行集合差集 —— 比 stdout 前缀门禁更早、更细地暴露两侧分歧。

## 为什么需要它（2026-09-17 场景 E 实测）

行为门禁（`behav_diff.py`）比对的是两侧 **stdout 的最长公共前缀**，
于是有一类分歧它**看不见**：两侧都不打印、但**走的代码路径不同**。

实测：场景 E 的 stdout 前缀 18/18 PASS，而 `tools/qemu_coverage.py` 的两份报告
一对比就露出：

| 方向 | 函数 |
|---|---|
| **仅我们执行**（工厂没执行） | `mui_outputxy_t`(904B 字体渲染)、`mui_DispBlock`、`get_item_from_line`、`UnzipItem`、`strtrim`/`strtriml`/`strtrimr` |
| **仅工厂执行** | `ClearBuffer` |

机制：`mui_InitFont` 失败后，工厂**不再调用** `mui_outputxy_t`，我们**照样调用**
⇒ 把无效字体传进去 ⇒ 崩在 `stbtt_GetFontVMetricsOS2+0x8`（`ldrd r8,[r0,#4]`、`r0` 无效）。
⇒ 执行集合差集是**定位分歧机制的第一手证据**，比 stdout 更早命中。

## 用法

    python tools/exec_set_diff.py --factory report/qemu_c/coverage_factory.txt \
                                  --ours    report/qemu_c/coverage_rebuild.txt \
                                  --out     report/qemu_c/exec_set_diff.txt
退出码：0 = 集合一致；1 = 有差异（**观测项**，是否升级为门禁由调用方决定 ——
场景 E 目前本就存在真实分歧，故 CI 里先只打印、不判失败）。
"""
import argparse
import os
import re
import sys

BLOCK = re.compile(r'已执行函数明细（(\d+) 个）：\n(.*?)\n   未执行', re.S)
LINE = re.compile(r'\s+(\S+)\s+(\d+) B\s+(\S+)')


def parse(path):
    if not os.path.exists(path):
        return None
    s = open(path, encoding='utf-8', errors='replace').read()
    m = BLOCK.search(s)
    if not m:
        return None
    out = []
    for ln in m.group(2).splitlines():
        mm = LINE.match(ln)
        if mm:
            out.append((mm.group(1), int(mm.group(2)), mm.group(3)))
    return out


def exits(scen_dir):
    """读取同场景目录下三个 `behav_*.json` 的 exit_code（缺则 None）。

    ★ 为什么差集工具要读它：见 main() 里"解读前置条件"块 —— 执行集合是**无序集合**，
      不含"谁先退出"。参照侧提前退出会让重建侧"凭空中多出"一整套函数。
    """
    import json
    out = {}
    for lb in ('factory', 'rebuild', 'control'):
        try:
            with open(os.path.join(scen_dir, 'behav_%s.json' % lb), encoding='utf-8') as f:
                out[lb] = json.load(f).get('exit_code')
        except Exception:
            out[lb] = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', required=True)
    ap.add_argument('--ours', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--label', default='')
    a = ap.parse_args()

    A = parse(a.factory)
    B = parse(a.ours)
    if A is None or B is None:
        print('  [skip] 覆盖率报告缺失或不可解析（factory=%s / ours=%s）'
              % (A is not None, B is not None))
        return 0

    na = {n: (s, m) for n, s, m in A}
    nb = {n: (s, m) for n, s, m in B}
    only_ours = sorted(set(nb) - set(na))
    only_factory = sorted(set(na) - set(nb))

    L = []
    L.append('== 执行集合差集%s ==' % (('（' + a.label + '）') if a.label else ''))
    L.append('  工厂已执行 %d 个 / 我们已执行 %d 个' % (len(A), len(B)))
    L.append('')
    L.append('  ★ 仅我们执行（工厂没执行）%d 个：' % len(only_ours))
    for n in only_ours:
        s, m = nb[n]
        L.append('     %-38s %6d B  %s' % (n, s, m))
    L.append('')
    L.append('  ★ 仅工厂执行（我们没执行）%d 个：' % len(only_factory))
    for n in only_factory:
        s, m = na[n]
        L.append('     %-38s %6d B  %s' % (n, s, m))
    L.append('')
    L.append('  合计差异 = %d（仅我们 %d + 仅工厂 %d）'
             % (len(only_ours) + len(only_factory), len(only_ours), len(only_factory)))
    L.append('')
    # ★★ 解读前置条件（2026-09-20 加，GAP 16.47）—— 把纪律写进仪器，而不是只留在文档里。
    scen = os.path.dirname(a.factory)
    ex = exits(scen)

    def _alive(v):
        if v is None:
            return '?'
        return '活着' if v < 128 else '被信号终止'

    L.append('  ★★ 解读前置条件（**先读这一块，再看上面的清单**）：')
    L.append('     执行集合是**无序集合**，不含"谁先退出" —— 参照侧一旦提前退出（崩溃/被杀/环境缺件），')
    L.append('     重建侧就会"凭空中多出"一整套它**本该也执行**的函数，看着像"我们走错了分支"。')
    L.append('     本场景终止：factory=%s(%s)  rebuild=%s(%s)  control=%s(%s)'
             % (ex['factory'], _alive(ex['factory']), ex['rebuild'], _alive(ex['rebuild']),
                ex['control'], _alive(ex['control'])))
    if ex['factory'] is not None and ex['rebuild'] is not None and ex['factory'] != ex['rebuild']:
        if ex['control'] == ex['factory']:
            L.append('     ⚠️ 两侧终止形态不同，且**控制组与 factory 同判 %s ⇒ 参照侧失败可复现** ——'
                     % ex['control'])
            L.append('        本场景的「仅我们执行」清单**不能当作重建侧的分支分歧证据**，')
            L.append('        它更可能是"参照侧环境缺陷导致其早逝"的影子。')
        else:
            L.append('     ⚠️ 两侧终止形态不同，且控制组（%s）与 factory（%s）**不同判**'
                     % (ex['control'], ex['factory']))
            L.append('        ⇒ 参照侧存在不确定性，本场景的一切差集结论都**不可信**，先修环境。')
    elif ex['factory'] is not None and ex['factory'] >= 128:
        L.append('     ⚠️ 参照侧本身就被信号终止（%s）⇒ 上面的清单只能说明"双方死法不同"，不能说明对错。'
                 % ex['factory'])
    L.append('')
    L.append('  ★ 读法：差异 ≠ 一定是缺陷 —— 但我们"多执行"的分支往往就是分歧机制所在：')
    L.append('    先看"仅我们执行"里有没有**打印/渲染/文件操作**类函数（它们会改变可观测状态），')
    L.append('    再回到调用者源码核对：工厂在该条件下是否真的不调用它（条件是同一分支吗）。')
    txt = '\n'.join(L) + '\n'
    print(txt, end='')
    if a.out:
        os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
        open(a.out, 'w', encoding='utf-8', newline='\n').write(txt)
    return 1 if (only_ours or only_factory) else 0


if __name__ == '__main__':
    sys.exit(main())
