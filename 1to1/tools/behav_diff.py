#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""behav_diff.py — 行为差分门禁（P5 主门禁的比对端）

比对 behav_capture.sh 产出的两份行为指纹（原厂 vs 重建）。

判定维度：
  P0 前置：两侧 workdir 必须相同（否则比的是路径差异）；两侧二进制必须**不同**
  B0 非空洞：参考侧必须有可观测行为，否则 INCONCLUSIVE(3)
  B1 退出码一致            必须
  B2 语义事件序列一致      必须（stdout/stderr/menu.log，已剥离时间戳/地址/长数字）
  B3 新增文件路径一致      必须
  B4 变更文件路径一致      必须
  B5 menu.log 内容 sha 一致 两侧都有日志时必须（真机日志名 = menu.log）
  B6 帧缓冲采样哈希一致     若两侧均非 none 则必须
  B7 shm 心跳一致          若两侧均 >0 则必须

退出码：0 = PASS；2 = FAIL；3 = INCONCLUSIVE（环境不足以驱动参考实现）

用法:
  behav_diff.py factory.json rebuild.json [--detail]
"""
import json
import os
import sys
import difflib


def load(p):
    return json.load(open(p, encoding='utf-8'))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    pa, pb = sys.argv[1], sys.argv[2]
    a, b = load(pa), load(pb)
    detail = '--detail' in sys.argv
    fails = []
    checks = []
    hard = []          # 前置硬条件（不满足直接 FAIL，不再谈行为）

    def chk(name, ok, note=''):
        checks.append((name, ok, note))
        if not ok:
            fails.append(name)

    la = int(a.get('log_lines', 0) or 0)
    ev_a = len(a.get('events', []))
    so_a = int(a.get('stdout_lines', 0) or 0)

    print('=' * 68)
    print('行为差分门禁  %s  vs  %s' % (a.get('label'), b.get('label')))
    print('=' * 68)
    print('  参考端 %s' % pa)
    print('     binary=%s  sha=%s' % (a.get('binary'), a.get('binary_sha256_16')))
    print('     workdir=%s  exit=%s  stdout=%s 行  log=%s/%s 行'
          % (a.get('workdir'), a.get('exit_code'), a.get('stdout_lines'),
             a.get('log_file'), a.get('log_lines')))
    print('  重建端 %s' % pb)
    print('     binary=%s  sha=%s' % (b.get('binary'), b.get('binary_sha256_16')))
    print('     workdir=%s  exit=%s  stdout=%s 行  log=%s/%s 行'
          % (b.get('workdir'), b.get('exit_code'), b.get('stdout_lines'),
             b.get('log_file'), b.get('log_lines')))
    print('-' * 68)

    # ---- P0 前置条件 ----
    wa, wb = a.get('workdir'), b.get('workdir')
    if wa != wb:
        hard.append('P0a workdir 不一致：%s vs %s（差分比的是路径差异，不是代码差异）' % (wa, wb))
    sa, sb = a.get('binary_sha256_16'), b.get('binary_sha256_16')
    if sa and sb and sa == sb:
        hard.append('P0b 两侧二进制 sha 相同（%s）—— 等于拿同一份二进制自比，差分无意义' % sa)
    if os.path.abspath(pa) == os.path.abspath(pb):
        hard.append('P0c 两侧指纹文件是同一个路径')
    for h in hard:
        print('  [FAIL] %s' % h)
    if hard:
        print('-' * 68)
        print('  门禁结果: FAIL（%d 项前置条件不满足）' % len(hard))
        return 2

    # ---- B0 非空洞前置检查（★ 拒绝「两边都什么都没发生」的假通过）----
    # ★ 不能用 log_lines 判断：运行目录里**预置**了 menu.log，log_lines 恒 ≥1。
    #   以 behav_capture 写的显式 observed 字段为准（stdout/stderr/新增/变更文件）。
    if 'observed' in a:
        empty_a = not a.get('observed')
    else:                                    # 兼容旧指纹
        empty_a = (la < 1 and ev_a < 1 and so_a < 1)
    if empty_a:
        print('  [INCONCLUSIVE] B0 参考侧（工厂）无任何可观测行为：')
        print('      observed=%s  log_lines=%d  events=%d  stdout_lines=%d  stderr_lines=%s  exit_code=%s'
              % (a.get('observed'), la, ev_a, so_a, a.get('stderr_lines'), a.get('exit_code')))
        print('  重建侧: observed=%s  log_lines=%d  events=%d  stdout_lines=%d  stderr_lines=%s  exit_code=%s'
              % (b.get('observed'), b.get('log_lines', 0), len(b.get('events', [])),
                 b.get('stdout_lines', 0), b.get('stderr_lines'), b.get('exit_code')))
        print('  ⇒ 环境不足以驱动参考实现，本差分**无意义**（不是 PASS，也不是 FAIL）')
        print('     排查方向：① 目标二进制是否可执行（chmod +x）；② stdout 是否被全缓冲吃掉；')
        print('               ③ work 目录里的资源（setting.xml / cores/config.xml）是否就位。')
        return 3

    # ---- B1..B7 ----
    chk('B1 exit_code', a.get('exit_code') == b.get('exit_code'),
        '%s vs %s' % (a.get('exit_code'), b.get('exit_code')))

    ea, eb = a.get('events', []), b.get('events', [])
    same_ev = ea == eb
    chk('B2 events', same_ev, '%d vs %d 行' % (len(ea), len(eb)))

    fa = sorted(x.split('|')[0] for x in a.get('new_files', []))
    fb = sorted(x.split('|')[0] for x in b.get('new_files', []))
    chk('B3 new_files', fa == fb, '%d vs %d 个' % (len(fa), len(fb)))

    ga = sorted(x.split('|')[0] for x in a.get('changed_files', []))
    gb = sorted(x.split('|')[0] for x in b.get('changed_files', []))
    chk('B4 changed_files', ga == gb, '%d vs %d 个' % (len(ga), len(gb)))

    ha, hb = a.get('log_sha256_16'), b.get('log_sha256_16')
    if ha and hb and ha != 'none' and hb != 'none':
        chk('B5 log_sha', ha == hb, '%s(%s) vs %s(%s)'
            % (ha, a.get('log_file'), hb, b.get('log_file')))
    else:
        checks.append(('B5 log_sha', True, 'SKIP (一侧无日志文件)'))

    fha, fhb = a.get('frame_hash', 'none'), b.get('frame_hash', 'none')
    if fha != 'none' and fhb != 'none':
        chk('B6 frame_hash', fha == fhb, '%s vs %s' % (fha, fhb))
    else:
        checks.append(('B6 frame_hash', True, 'SKIP (一侧不可读)'))

    sma, smb = int(a.get('shm_heartbeat', 0)), int(b.get('shm_heartbeat', 0))
    if sma > 0 and smb > 0:
        chk('B7 shm', sma == smb, '%d vs %d' % (sma, smb))
    else:
        checks.append(('B7 shm', True, 'SKIP (一侧无 shm)'))

    for n, ok, note in checks:
        print('  [%s] %-18s %s' % ('PASS' if ok else 'FAIL', n, note))
    print('-' * 68)
    print('  门禁结果: %s (%d 项失败)' % ('PASS' if not fails else 'FAIL', len(fails)))

    if not same_ev and detail:
        print('\n--- 语义事件差异（factory → rebuild）---')
        for ln in list(difflib.unified_diff(ea, eb, 'factory', 'rebuild', lineterm=''))[:120]:
            print('  ' + ln)
    if fa != fb and detail:
        print('\n--- 新增文件差异 ---')
        print('  仅原厂:', sorted(set(fa) - set(fb))[:10])
        print('  仅重建:', sorted(set(fb) - set(fa))[:10])
    if ga != gb and detail:
        print('\n--- 变更文件差异 ---')
        print('  仅原厂:', sorted(set(ga) - set(gb))[:10])
        print('  仅重建:', sorted(set(gb) - set(ga))[:10])

    return 0 if not fails else 2


if __name__ == '__main__':
    sys.exit(main())
