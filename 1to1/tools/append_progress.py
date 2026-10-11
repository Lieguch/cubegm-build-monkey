#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROGRESS.md 的**原子、防覆盖**追加器（第 152 轮起常驻 tools/）。

## 为什么必须用脚本而不是编辑器/`>>`
PROGRESS.md 是本项目的**唯一工作依据**，规则是「只追加、不改既有内容」。
手工编辑有两条真实事故路径：
  ① 手滑改/删了既有段落 ⇒ 后续轮次读到的"待办"已经不是原来的意思；
  ② 写到一半中断 ⇒ 文件被截断成半截（`open(path,'w')` 打开**当场截断**）。
本脚本两条都堵死：
  · **只追加**：把待追加内容拼到旧全文**末尾**，并断言 `new[:len(old)] == old`；
  · **原子**：写 `<path>.tmp` → 校验 → `os.replace`（操作系统级原子替换）；
  · **哈希留痕**：打印旧/新 sha256 与 `old_intac=True`，写进新段落的第一行。

## 用法
  python3 tools/append_progress.py <段落文件>            # 追加到 PROGRESS.md
  python3 tools/append_progress.py -                    # 从 stdin 读段落
  python3 tools/append_progress.py <段落文件> --check    # 只校验不写（dry-run）

段落文件里**不要**自己写 `> 追加前 ...` 那一行 —— 本脚本会自动在开头补。
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, 'PROGRESS.md')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    args = sys.argv[1:]
    check = False
    if '--check' in args:
        check = True
        args.remove('--check')
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    src = args[0]
    if src == '-':
        body = sys.stdin.buffer.read()
    else:
        with open(src, 'rb') as f:
            body = f.read()
    if not body.endswith(b'\n'):
        body += b'\n'

    old = open(TARGET, 'rb').read()
    old_sha = sha(old)

    header = ('> 追加前 `old_intact=True`（旧文 %d B / sha %s…）；'
              '由 `tools/append_progress.py` 原子追加。\n' % (len(old), old_sha[:16])).encode('utf-8')
    new = old + b'\n' + header + body
    if new[:len(old)] != old:
        print('★★ 致命：拼接结果的前缀与旧文不一致（不可能触发；触即说明 old 被并发改动）',
              file=sys.stderr)
        return 3

    if check:
        print('dry-run OK：将追加 %d B（旧 %d B → 新 %d B）' % (len(body) + len(header) + 1, len(old), len(new)))
        print('  新 sha = %s' % sha(new))
        return 0

    tmp = TARGET + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(new)
        f.flush()
        os.fsync(f.fileno())
    # 再读一次 .tmp 确认落盘内容确实是我们写的（防截断）
    again = open(tmp, 'rb').read()
    if again != new:
        print('★★ .tmp 落盘内容与预期不一致（%d vs %d B）—— 不替换' % (len(again), len(new)),
              file=sys.stderr)
        os.remove(tmp)
        return 4
    os.replace(tmp, TARGET)

    now = open(TARGET, 'rb').read()
    print('OK  %d B → %d B' % (len(old), len(now)))
    print('   旧 sha = %s' % old_sha)
    print('   新 sha = %s' % sha(now))
    print('   old_intact = %s' % (now[:len(old)] == old))
    return 0


if __name__ == '__main__':
    sys.exit(main())
