#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_trailing_label.py —— 机械门禁：源码里**末尾标签**（label at end of compound statement）。

为什么新增（第 66 轮，由工具链对齐暴露的真缺陷）：
  工厂同款工具链（真实 GCC 6.3，`-std=gnu11`）对
      LAB_000178ec:
    }
  报 `error: label at end of compound statement`；而 **clang 容忍**这个 GNU 扩展
  ⇒ 我们此前一直用 zig/clang 编译，**这个缺陷从未暴露**。
  ⇒ 教训：显式指定 `-std=gnu11` 的**老 GCC** 与 clang 在"扩展宽容度"上不同；
     凡"只在唯一编译器上验过"的源码，都要假定还有同类不可移植写法。

修法：把 `LABEL:` 改成 `LABEL: ;`（C 的空语句；语义不变、不产生代码）。
本门禁只报**确定**的形态（标签后紧跟 `}` 或文件结束），不猜。

用法：
  python tools/scan_trailing_label.py --root .
  python tools/scan_trailing_label.py --selftest
exit: 0 = 无 / 1 = 有 / 2 = 用法错
"""
import argparse
import glob
import io
import os
import re
import sys

RE_LABEL = re.compile(r'^\s*([A-Za-z_]\w*)\s*:\s*(?:/\*.*?\*/)?\s*(?://.*)?$')
RE_ONLY_COMMENT = re.compile(r'^\s*(?:/\*.*?\*/\s*|//.*)?$')


def strip_comments(text):
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    return re.sub(r'//[^\n]*', ' ', text)


def scan_text(text):
    """→ [(行号, 标签名)]：标签的**下一条非空非注释行**是 `}` 或文件结束。"""
    lines = strip_comments(text).split('\n')
    out = []
    for i, ln in enumerate(lines):
        m = RE_LABEL.match(ln)
        if not m:
            continue
        name = m.group(1)
        if name in ('case', 'default', 'public', 'private', 'protected'):
            continue
        # 跳过紧随其后的空行/纯注释行
        j = i + 1
        while j < len(lines) and RE_ONLY_COMMENT.match(lines[j]) and lines[j].strip() == '':
            j += 1
        if j >= len(lines):
            out.append((i + 1, name))          # 文件结束
            continue
        nxt = lines[j].strip()
        if nxt.startswith('}'):
            out.append((i + 1, name))
    return out


def selftest():
    chk = []

    def c(label, got, want):
        chk.append((label, got, want))

    bad = 'void f(void){\n  int a=1;\n  goto L;\nL:\n}\n'
    c('缺陷态 末尾标签 ⇒ 报出', [n for _l, n in scan_text(bad)], ['L'])
    good = 'void f(void){\n  int a=1;\n  goto L;\nL: ;\n}\n'
    c('正例 末尾标签后有空语句 ⇒ 不报', scan_text(good), [])
    mid = 'void f(void){\nL:\n  return;\n}\n'
    c('正例 标签后还有语句 ⇒ 不报', scan_text(mid), [])
    two = 'void f(void){\nA:\nB:\n}\n'
    c('缺陷态 连续两个末尾标签 ⇒ 都报', [n for _l, n in scan_text(two)], ['A', 'B'])
    sw = 'void f(int x){switch(x){\ncase 1:\n  break;\n}}\n'
    c('正例 switch 的 case 不误报', scan_text(sw), [])
    cmt = 'void f(void){\n  goto L;\nL:\n  /* 注释 */\n}\n'
    c('缺陷态 标签与 `}` 之间只有注释 ⇒ 仍报', [n for _l, n in scan_text(cmt)], ['L'])
    eof = 'void f(void){\nL:\n'
    c('缺陷态 标签在文件末尾 ⇒ 报出', [n for _l, n in scan_text(eof)], ['L'])
    return chk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--selftest', '--self-test', dest='self_test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        chk = selftest()
        bad = 0
        for label, got, want in chk:
            ok = got == want
            print('  %s %s' % ('✓' if ok else '✗', label))
            if not ok:
                print('      got=%r want=%r' % (got, want))
                bad += 1
        print('=== 合计 %d 条，失败 %d 条 ===' % (len(chk), bad))
        return 2 if bad else 0

    root = a.root
    files = []
    for pat in ('src/proprietary/*/*.c', 'src/compat/*.c', 'src/upstream/**/*.c'):
        files.extend(glob.glob(os.path.join(root, pat), recursive=True))
    files = sorted(set(files))
    n = 0
    for f in files:
        try:
            txt = io.open(f, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        hits = scan_text(txt)
        if hits:
            n += len(hits)
            print('  %s' % os.path.relpath(f, root))
            for ln, name in hits:
                print('      ★ 第 %d 行 `%s:` 是**复合语句的最后一个东西** ⇒ '
                      '真实 GCC(`-std=gnu11`) 会报 `label at end of compound statement`。'
                      '修法：改成 `%s: ;`' % (ln, name, name))
    if n:
        print('★ FAIL：%d 处末尾标签。clang 容忍而老 GCC 不容忍 ⇒ '
              '不修就会在工厂同款工具链上编不过。' % n)
        return 1
    print('  PASS：%d 个 C 文件，无末尾标签' % len(files))
    return 0


if __name__ == '__main__':
    sys.exit(main())
