#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""state_snapshot_info.py —— 打印 G1 状态快照的头部自校验（magic/范围/体长）

用法：python tools/state_snapshot_info.py <state_*.bin> [...]

判据（fail-loud）：magic 必须是 `CGMST001`；`hi > lo`；体长必须恰为 `hi - lo`。
任何一条不符即打印 BAD 并以非 0 退出 —— 因为"快照坏了却当成好快照用"会让
`--from-state` 静默退化成"没状态"，那是假绿。
"""
import struct
import sys


def inspect(path):
    raw = open(path, 'rb').read()
    if len(raw) < 16:
        return path, 'TOO-SHORT', None, False
    magic = raw[:8]
    lo, hi = struct.unpack('<II', raw[8:16])
    body = len(raw) - 16
    ok = (magic == b'CGMST001') and hi > lo and body == hi - lo
    return path, magic.decode('latin1'), (lo, hi, body), ok


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    bad = 0
    for p in argv:
        try:
            path, magic, rng, ok = inspect(p)
        except OSError as e:
            print('  %-44s 读不到：%s' % (p, e))
            bad += 1
            continue
        if rng is None:
            print('  %-44s magic=%s 文件过短' % (path, magic))
            bad += 1
            continue
        lo, hi, body = rng
        print('  %-44s magic=%s lo=0x%08x hi=0x%08x body=%d %s'
              % (path, magic, lo, hi, body, 'OK' if ok else 'BAD'))
        if not ok:
            bad += 1
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
