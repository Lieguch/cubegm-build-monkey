#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mmio_trace_diff —— 运行期 MMIO 访存契约对拍（PLAN-DECISIVE.md §2.1 支柱 A 的门禁）。

为什么需要它
------------
`tools/mmio_width_audit.py` 是**静态**判据：只看反汇编里 narrow 访存的计数。
它看不到**运行期**的三件事：
    · 顺序（工厂"先写 [base]=0 再读 [base+0x2C]"，我们可能反了）
    · 偏移（访问了工厂从不访问的寄存器）
    · 是否真的被执行到（静态看得到、运行期未必走到）
而 `tools/guest_shim/fake_mem.c` 已经把设备页设成 PROT_NONE + SIGSEGV/SIGBUS 处理器，
**每次寄存器访问都会陷入 sfc_fault，宽度/方向/偏移/PC 全部已知**
⇒ 把它落成 `MMIO seq=N off=0x.. w=.. dir=R|W pc=0x..` 就能**逐项对拍**。

判据（先写死，避免事后凑结论）
------------------------------
比对的锚点是**同一 seq 位置**（= 执行序）：
    M1  偏移一致      off 必须相同；不同 ⇒ `OFF-DIFF`
    M2  方向一致      dir 必须相同；不同 ⇒ `DIR-DIFF`（顺序/语义被改）
    M3  宽度不窄化    w 不得**小于**工厂；小于 ⇒ `WIDTH-NARROW`（★ 本轮 SIGBUS 的类型）
    M4  条数一致      seq 总数应相同；不同 ⇒ 报告差集（不直接判 FAIL，见下）
★ M3 是**硬**判据；M1/M2 也硬；M4 只报提示 —— 因为工厂与我们可能因提前崩溃而条数不同，
  而这恰恰是有用信息（谁先死）。

退出码：0 = 无违规 / 1 = 有违规 / 2 = 输入不可读（**绝不静默通过**）

自证（必须能区分三种态）
------------------------
    ① 正常态：工厂 vs 修复后 ⇒ 期望 0 违规
    ② 缺陷态：工厂 vs **修复前**（已知 `ldrh`，w=2）⇒ 期望报出 `WIDTH-NARROW @off=0x2c`
    ③ 反证态：同一文件自比 ⇒ 必须 0 违规

用法
    python tools/mmio_trace_diff.py --factory f.txt --rebuild r.txt [--verbose]
"""
import argparse
import collections
import io
import re
import sys

LINE = re.compile(r'MMIO seq=(\d+)\s+off=0x([0-9a-fA-F]+)\s+w=(\d+)\s+dir=([RW])\s+pc=0x([0-9a-fA-F]+)')


def parse(path):
    try:
        t = io.open(path, encoding='utf-8', errors='replace').read()
    except OSError as e:
        print('  ★ 读不到 %s: %s' % (path, e))
        return None
    out = []
    for m in LINE.finditer(t):
        out.append(dict(seq=int(m.group(1)), off=int(m.group(2), 16), w=int(m.group(3)),
                        dir=m.group(4), pc=int(m.group(5), 16)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--factory', required=True)
    ap.add_argument('--rebuild', required=True)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    f = parse(a.factory)
    r = parse(a.rebuild)
    if f is None or r is None:
        print('  结论: 输入不可读 ⇒ 硬失败（不允许静默通过）')
        return 2
    print('  工厂 MMIO 访问条数 = %d' % len(f))
    print('  重建 MMIO 访问条数 = %d' % len(r))
    if not f:
        print('  结论: 工厂侧零条 ⇒ 判据不可用（trace 没生效），硬失败')
        return 2

    viol = []
    n = min(len(f), len(r))
    for i in range(n):
        A, B = f[i], r[i]
        if A['off'] != B['off']:
            viol.append(('OFF-DIFF', i, '工厂 off=0x%x vs 重建 off=0x%x' % (A['off'], B['off'])))
        if A['dir'] != B['dir']:
            viol.append(('DIR-DIFF', i, '工厂 dir=%s vs 重建 dir=%s @off=0x%x'
                         % (A['dir'], B['dir'], A['off'])))
        if B['w'] < A['w']:
            viol.append(('WIDTH-NARROW', i, '★ off=0x%x 工厂 w=%d vs 重建 w=%d'
                         % (A['off'], A['w'], B['w'])))

    cnt = collections.Counter(v[0] for v in viol)

    print()
    print('  === 逐项对拍（锚点 = 同一 seq / 执行序）===')
    if not viol:
        print('    ✓ 前 %d 条完全一致（偏移 / 方向 / 宽度）' % n)
    else:
        show = viol if a.verbose else viol[:20]
        for kind, i, msg in show:
            print('    [%s] seq=%d  %s' % (kind, i, msg))
        if len(viol) > len(show):
            print('    ...（另 %d 条，加 --verbose 看全）' % (len(viol) - len(show)))

    if len(f) != len(r):
        print()
        print('  === 条数差（提示，不直接判 FAIL）===')
        print('    工厂 %d vs 重建 %d ⇒ 差 %+d 条；'
              '通常意味着**一方提前崩溃/提前退出**，是有用信息' % (len(f), len(r), len(r) - len(f)))

    print()
    print('  === 汇总 ===')
    for k in ('WIDTH-NARROW', 'DIR-DIFF', 'OFF-DIFF'):
        print('    %-14s %d' % (k, cnt.get(k, 0)))
    bad = sum(cnt.values())
    if bad:
        print('  结论: ★ FAIL —— %d 项违规（WIDTH-NARROW 是本轮真机 SIGBUS 的类型）' % bad)
        return 1
    print('  结论: PASS —— 访存契约（偏移/方向/宽度）逐项一致')
    return 0


if __name__ == '__main__':
    sys.exit(main())
