#!/usr/bin/env python3
"""
behav_diff.py — 行为差分门禁（P4 主门禁的比对端）

比对 behav_capture.sh 产出的两份行为指纹（原厂 vs 重建）。

判定维度与权重：
  B1 退出码一致          必须
  B2 日志语义事件序列一致  必须（剥离时间戳/地址/长度）
  B3 新增/变更文件路径一致  必须
  B4 帧缓冲采样哈希一致    若两侧均非 none 则必须
  B5 shm 心跳一致         若两侧均 >0 则必须

用法:
  behav_diff.py factory.json rebuild.json [--detail]
"""
import json, sys, difflib


def load(p):
    return json.load(open(p, encoding='utf-8'))


def main():
    if len(sys.argv) < 3:
        print(__doc__); return 1
    a, b = load(sys.argv[1]), load(sys.argv[2])
    detail = '--detail' in sys.argv
    fails = []
    checks = []

    def chk(name, ok, note=''):
        checks.append((name, ok, note))
        if not ok:
            fails.append(name)

    # B1 退出码
    chk('B1 exit_code', a['exit_code'] == b['exit_code'],
        '%s vs %s' % (a['exit_code'], b['exit_code']))

    # B2 日志语义事件序列
    ea, eb = a.get('events', []), b.get('events', [])
    same_ev = ea == eb
    chk('B2 log_events', same_ev, '%d vs %d 行' % (len(ea), len(eb)))

    # B3 新增文件路径（取路径部分，忽略哈希差异）
    fa = sorted(x.split('|')[0] for x in a.get('new_files', []))
    fb = sorted(x.split('|')[0] for x in b.get('new_files', []))
    chk('B3 new_files', fa == fb, '%d vs %d 个' % (len(fa), len(fb)))

    # B4 帧缓冲
    ha, hb = a.get('frame_hash', 'none'), b.get('frame_hash', 'none')
    if ha != 'none' and hb != 'none':
        chk('B4 frame_hash', ha == hb, '%s vs %s' % (ha, hb))
    else:
        checks.append(('B4 frame_hash', True, 'SKIP (一侧不可读)'))

    # B5 shm
    sa, sb = int(a.get('shm_heartbeat', 0)), int(b.get('shm_heartbeat', 0))
    if sa > 0 and sb > 0:
        chk('B5 shm', sa == sb, '%d vs %d' % (sa, sb))
    else:
        checks.append(('B5 shm', True, 'SKIP (一侧无 shm)'))

    print('=' * 64)
    print('行为差分门禁  %s  vs  %s' % (a.get('label'), b.get('label')))
    print('=' * 64)
    for n, ok, note in checks:
        print('  [%s] %-18s %s' % ('PASS' if ok else 'FAIL', n, note))
    print('-' * 64)
    print('  门禁结果: %s (%d 项失败)' % ('PASS' if not fails else 'FAIL', len(fails)))

    if not same_ev and detail:
        print('\n--- 日志语义事件差异 ---')
        for ln in list(difflib.unified_diff(ea, eb, 'factory', 'rebuild', lineterm=''))[:80]:
            print(' ', ln)
    if fa != fb and detail:
        print('\n--- 新增文件差异 ---')
        print('  仅原厂:', sorted(set(fa) - set(fb))[:10])
        print('  仅重建:', sorted(set(fb) - set(fa))[:10])
    return 0 if not fails else 2


if __name__ == '__main__':
    sys.exit(main())
