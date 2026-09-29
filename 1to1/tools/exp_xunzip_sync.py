#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""exp_xunzip_sync.py —— 用**按当前源码重编**的 XUnzip 对象重链，验证是否净收敛。

背景（§0.30-D）
---------------
交付产物带的 XUnzip 对象是**陈旧的**：与工厂精确相同符号数只有 **3/62**，
而磁盘上的 `src/upstream/xunzip/XUnzip.o`（Sep 27）是 **13/62**。
把当前 `unzip.cpp` 重新编出来（`build/_exp/XUnzip.sync.o`）得 **14/62**，
其中 `_Z14timet2filetimel` 从 312 B 收敛到 **12 B = 工厂**。

本脚本只做**验证**：用 `DIAG_XUNZIP=` 指向重编对象重链（**不改 `src/`**），
输出 `build/_exp/rkgame.syncx.elf`，供行为尺对账。
是否把重编对象落进 `src/`（入库）**留待用户确认**（CI 有"XUnzip.o 必须入库"的契约）。
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import exp_zero_fimg as E                                   # noqa: E402

SYNC_OBJ = os.path.join(E.EXP, 'XUnzip.sync.o')
OUT = os.path.join(E.EXP, 'rkgame.syncx.elf')
LOG = os.path.join(E.EXP, 'link_syncx.log')


def main():
    if not os.path.exists(SYNC_OBJ):
        raise SystemExit('!! 缺 %s（先用 zig cc -std=gnu++98 -fno-exceptions 编 unzip.cpp）' % SYNC_OBJ)
    env = dict(os.environ)
    env['PATH'] = E.tool_path()
    env.update(CC='%s cc' % E.ZIG, SYSROOT='', PY=E.PY, EXTRA_LDFLAGS='',
               LINK_DRIVER='lld',
               ZIG_GLOBAL_CACHE_DIR=os.path.join(E.ROOT, 'build', '_zigcache_ab'),
               DIAG_XUNZIP=SYNC_OBJ)
    with open(LOG, 'w', encoding='utf-8', errors='replace') as fh:
        p = subprocess.run(['sh', os.path.join(E.ROOT, 'tools', 'link_full.sh'), OUT],
                           cwd=E.ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
    print('link rc = %d   (日志 %s)' % (p.returncode, os.path.relpath(LOG, E.ROOT)))
    if p.returncode != 0 or not os.path.exists(OUT):
        print('★ 链接失败，尾部：')
        for ln in E.gates_from_log(LOG):
            print('   %s' % ln)
        return p.returncode
    print('产物 %d B   sha256=%s' % (os.path.getsize(OUT), E.sha256(OUT)[:16]))
    for seg in ('text', 'rodata'):
        r = E.verify_seg_in_artifact(OUT, seg)
        if r:
            print('   [内容校验] %-16s 非零 %9d / %9d' % (E.SEG_SEC[seg], r[0], r[1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
