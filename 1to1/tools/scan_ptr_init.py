"""统计 globals.h 里只声明、无任何赋值的 PTR_* 指针（回退 1:1 后的系统性缺口扫描）。

实现要点：**线性扫描**而非对每个符号跑一次正则 ——
前一版对 N 个符号各跑一次 `re.search` over 全仓 blob，在本仓（数千文件）会超时。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GH = os.path.join(ROOT, 'src', 'compat', 'globals.h')


def read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


t = read(GH)
ptrs = sorted(set(re.findall(r'\b(PTR_[A-Za-z0-9_]+)\b', t)))
print('globals.h 里的 PTR_* 标识: %d 个' % len(ptrs))

# 一次性把除 globals.h 外的所有源码拼成一个大字符串（只读一次）
parts = []
nfile = 0
for root, dirs, files in os.walk(os.path.join(ROOT, 'src')):
    for f in files:
        if not f.endswith(('.c', '.cpp', '.h', '.S')):
            continue
        p = os.path.join(root, f)
        if os.path.abspath(p) == os.path.abspath(GH):
            continue
        s = read(p)
        if s:
            parts.append(s)
            nfile += 1
blob = '\n'.join(parts)
print('参与扫描的源文件: %d（合计 %.1f MB）' % (nfile, len(blob) / 1048576.0))

# 线性扫描：先找出所有 "PTR_xxx" 出现处，再就地判断其后是否跟着 '='（排除 '=='）或前置 '&'
missing = []
present = []
for nm in ptrs:
    i = 0
    found = False
    while True:
        j = blob.find(nm, i)
        if j < 0:
            break
        found = True
        k = j + len(nm)
        # 跳过空白
        while k < len(blob) and blob[k] in ' \t\r\n':
            k += 1
        if k < len(blob) and blob[k] == '=' and (k + 1 >= len(blob) or blob[k + 1] != '='):
            break                      # 赋值
        # 取址：往前看最近的非空白字符是 '&'
        b = j - 1
        while b >= 0 and blob[b] in ' \t\r\n':
            b -= 1
        if b >= 0 and blob[b] == '&':
            break                      # &PTR_x
        i = j + 1
    (present if found else missing).append((nm, found))

only_decl = [nm for nm, found in present if not found]
print('出现过（被赋值/取址/传参）: %d' % len(present))
print('★ 全仓找不到任何引用: %d 个' % len(missing))
for nm, _ in missing:
    print('    [零引用] %s' % nm)
print('★ 只出现但无赋值/取址: %d 个' % len(only_decl))
for nm in only_decl:
    print('    %s' % nm)
