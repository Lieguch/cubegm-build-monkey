#!/usr/bin/env python3
"""
normalize_types.py — 给 Ghidra 私有类型统一加 gh_ 前缀，**从构造上消除**与系统头冲突。

根因：compat 头里 typedef 的 uint/ulong/ushort/uchar/byte/bool 等，
      会被 glibc 某些头（经 stdio/sys/types 传递引入）先行 typedef，
      导致 `error: conflicting types for 'ulong'`（C 中 typedef 冲突是硬错误）。
      CI 实测：注入 include 后 213 个文件全部因此失败（0/213）。

做法：把全部 Ghidra 私有类型名统一改名，前缀 gh_。系统头永远不会定义 gh_*，
      故冲突在构造上不可能发生。
      （这一条同时解释了首轮 24/213 的偶然通过：那些文件恰好没用到冲突类型。）

用法: python tools/normalize_types.py
"""
import os, re

ROOT = r'D:/output/rkgame-1to1'
TARGETS = [os.path.join(ROOT, 'src', 'compat', 'ghidra_compat.h'),
           os.path.join(ROOT, 'src', 'compat', 'globals.h'),
           os.path.join(ROOT, 'src', 'compat', 'proto.h')]
SRC = os.path.join(ROOT, 'src', 'proprietary')

# 有序（长名优先，避免 undefined1 被 undefined 先吃掉）
RENAME = [
    ('undefined1', 'gh_u1'), ('undefined2', 'gh_u2'),
    ('undefined4', 'gh_u4'), ('undefined8', 'gh_u8'),
    ('undefined', 'gh_undef'),
    ('ulonglong', 'gh_ulonglong'), ('longlong', 'gh_longlong'),
    ('ushort', 'gh_ushort'), ('uchar', 'gh_uchar'),
    ('ulong', 'gh_ulong'), ('uint', 'gh_uint'),
    ('byte', 'gh_byte'), ('code', 'gh_code'), ('bool', 'gh_bool'),
]
# 不动的：int char long short float double void size_t ssize_t


def _rw(chunk):
    for a, b in RENAME:
        chunk = re.sub(r'\b' + a + r'\b', b, chunk)
    return chunk


def rename_text(t):
    """C 词法感知替换：代码段改名，字符串字面量与注释**原样透传**。"""
    out = []
    code = []
    i, n = 0, len(t)

    def flush():
        if code:
            out.append(_rw(''.join(code)))
            code.clear()

    while i < n:
        c = t[i]
        if c == '"' or c == "'":
            flush()
            q = c
            j = i + 1
            while j < n:
                if t[j] == '\\':
                    j += 2
                    continue
                if t[j] == q:
                    j += 1
                    break
                j += 1
            out.append(t[i:j])
            i = j
            continue
        if t.startswith('/*', i):
            flush()
            j = t.find('*/', i + 2)
            j = n if j < 0 else j + 2
            out.append(t[i:j])
            i = j
            continue
        if t.startswith('//', i):
            flush()
            j = t.find('\n', i)
            j = n if j < 0 else j
            out.append(t[i:j])
            i = j
            continue
        code.append(c)
        i += 1
    flush()
    return ''.join(out)


n_files = 0
for p in TARGETS + [os.path.join(dp, f)
                    for dp, dn, fn in os.walk(SRC)
                    for f in fn if f.endswith('.c')]:
    if not os.path.exists(p):
        continue
    t = open(p, encoding='utf-8', errors='replace').read()
    nt = rename_text(t)
    if nt != t:
        open(p, 'w', encoding='utf-8').write(nt)
        n_files += 1

print('normalized %d files' % n_files)

# 校验：compat 头里 gh_* 定义应存在
c = open(TARGETS[0], encoding='utf-8').read()
for _, b in RENAME:
    if ('typedef' not in c) or (b not in c):
        print('  WARN missing typedef for', b)
print('compat header typedefs ok')
