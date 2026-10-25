#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""obj_manifest.py —— 专有对象「内容级」新鲜度清单（write / check）

## 为什么需要（R285 真实事故）
`link_full.sh` 只 glob `build/obj/*.o`，**不检查这些对象是不是当前源码编出来的**。
我手工单跑 `link_full.sh`（没跑 `link_audit.sh`）⇒ 链到了 R275 之前口径的旧对象
⇒ 产物导入 `bcmp`（新口径带 `-fno-builtin-strcmp`，不出 bcmp）且 diff_exec 把
`mui_InitFont` 误判为发散。判据不报错，只给出错误结论 —— 这类问题最贵。

## 判据（内容级，不用 mtime）
write：对 objdir 里每个 `X.o`，找 `srcdir/**/X.c`，记录
    `X.o <TAB> sha256(obj)[:16] <TAB> sha256(src)[:16]`
check：逐条重算两侧哈希；任一不符/缺失/无清单 ⇒ 非 0。

## 用法
  python obj_manifest.py write build/obj           # link_audit 成功后调用
  python obj_manifest.py check build/obj           # link_full 开头调用
  python obj_manifest.py check build/obj --allow-missing   # 诊断/实验路径显式放行
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRCROOT = os.path.join(ROOT, 'src')
MANIFEST = '.obj_manifest.tsv'


def sha16(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()[:16]


def find_src(stem):
    """在 src/ 下找 <stem>.c（唯一命中才返回）。"""
    hits = []
    for dirpath, _dirs, files in os.walk(SRCROOT):
        if stem + '.c' in files:
            hits.append(os.path.join(dirpath, stem + '.c'))
    return hits[0] if len(hits) == 1 else None


def do_write(objdir):
    objs = sorted(f for f in os.listdir(objdir) if f.endswith('.o'))
    lines = ['# obj\tsha16(obj)\tsha16(src)\tsrc']
    missing = []
    for o in objs:
        stem = o[:-2]
        src = find_src(stem)
        if src is None:
            missing.append(o)
            continue
        rel = os.path.relpath(src, ROOT).replace(os.sep, '/')
        lines.append('%s\t%s\t%s\t%s' % (o, sha16(os.path.join(objdir, o)), sha16(src), rel))
    out = os.path.join(objdir, MANIFEST)
    tmp = out + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines) + '\n')
    os.replace(tmp, out)
    print('  [manifest] 写入 %s：%d 个对象%s' %
          (out, len(objs) - len(missing),
           ('，%d 个无对应源码（不纳入）' % len(missing)) if missing else ''))
    return 0


def do_check(objdir, allow_missing=False):
    mf = os.path.join(objdir, MANIFEST)
    if not os.path.exists(mf):
        msg = '★★ 缺对象清单 %s ⇒ 无法证明对象与源码同源（禁止链接旧对象）' % mf
        if allow_missing:
            print('  [manifest] WARN %s（--allow-missing 放行）' % msg)
            return 0
        print('  [manifest] FAIL %s' % msg)
        print('             修法：先跑 CC=... PY=... sh tools/link_audit.sh report/link_audit.txt')
        return 2
    bad_obj, bad_src, n = [], [], 0
    for line in open(mf, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        parts = line.rstrip('\n').split('\t')
        if len(parts) != 4:
            continue
        o, hob, hsrc, rel = parts
        n += 1
        op = os.path.join(objdir, o)
        sp = os.path.join(ROOT, rel)
        if not os.path.exists(op) or sha16(op) != hob:
            bad_obj.append(o)
        if not os.path.exists(sp) or sha16(sp) != hsrc:
            bad_src.append(rel)
    if bad_obj or bad_src:
        print('  [manifest] FAIL 对象与源码不同源：%d 项对象改动 / %d 项源码改动' %
              (len(bad_obj), len(bad_src)))
        for o in bad_obj[:5]:
            print('     obj 变更: %s' % o)
        for s in bad_src[:5]:
            print('     src 变更: %s' % s)
        print('             修法：重跑 tools/link_audit.sh 后再链接（禁止链旧对象）')
        return 3
    print('  [manifest] OK %d 个对象与源码逐一同源' % n)
    return 0


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ('write', 'check'):
        print(__doc__)
        return 1
    mode, objdir = sys.argv[1], sys.argv[2]
    if not os.path.isdir(objdir):
        print('  [manifest] FAIL 对象目录不存在：%s' % objdir)
        return 2
    if mode == 'write':
        return do_write(objdir)
    return do_check(objdir, '--allow-missing' in sys.argv)


if __name__ == '__main__':
    sys.exit(main())
