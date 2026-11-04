#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROJECT-MEMORY.md 的**原子追加器**（与 tools/append_progress.py 同构，目标不同）。

为什么单独一个脚本：PROJECT-MEMORY.md 是项目长期记忆，格式是**小节（#### L. R30x）**，
不需要 PROGRESS.md 的 `> 追加前 old_intact=...` 头（那些是给"唯一工作依据"用的可追溯标记）。
但**原子性要求完全相同**：禁止 `open(path,'w')` 覆盖唯一副本（曾把 sync_mirror.py 变成 0 字节）。
做法：写 <path>.tmp → 校验（前缀一致 + 可解码）→ os.replace 原子替换。
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, 'PROJECT-MEMORY.md')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    args = [a for a in sys.argv[1:] if a != '--check']
    check = len(args) != len(sys.argv[1:])
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    with open(args[0], 'rb') as f:
        body = f.read()
    if not body.endswith(b'\n'):
        body += b'\n'

    old = open(TARGET, 'rb').read()
    old_sha = sha(old)
    new = old + body
    # 防覆盖断言：拼接结果的前缀必须与旧文**逐字节**一致
    if new[:len(old)] != old:
        print('★★ 致命：前缀与旧文不一致（不可能触发；触即说明 old 被并发改写）')
        return 9
    new.decode('utf-8')          # 校验可解码（防半截多字节字符）
    print('dry-run OK：将追加 %d B（旧 %d B → 新 %d B）' % (len(body), len(old), len(new)))
    print('  新 sha = %s' % sha(new))
    if check:
        return 0
    tmp = TARGET + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(new)
    assert os.path.getsize(tmp) == len(new)
    os.replace(tmp, TARGET)
    # 回读校验
    back = open(TARGET, 'rb').read()
    assert back == new, '回读不一致'
    print('OK  %d B → %d B\n  旧 sha = %s\n  新 sha = %s\n  回读一致 = True'
          % (len(old), len(new), old_sha[:16], sha(new)[:16]))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
