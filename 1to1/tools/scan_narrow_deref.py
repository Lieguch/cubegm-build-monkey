#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描「窄指针转型 + 解引用」—— 会静默把**指针低字节**当指针用的高危写法。

## 为什么需要它（第 42 轮实测，真实缺陷）

`src/proprietary/mui/FUN_0002b2b4_mui_setting.c` 里曾写成：

```c
mui_outputxy_t(..., (gh_byte *)*(gh_byte *)puVar15);
```

`puVar15` 是**指针表游标**（工厂机器码 `2b490: ldr r2,[r6,#4]!`，按 +4 步长取**字**），
正确写法是 `*puVar15`（取一个字 = 指针）。而多写的一层 `(gh_byte *)` 使编译器发射
**字节读**（`ldrb`）⇒ 拿到的是**指针的低字节**（0..255）⇒ 再当成指针用。

实测后果（场景 E 定案）：该槽指针低字节 = `0x80`
⇒ `mui_outputxy_t` 的第 6 实参 = `0x80` ⇒ 函数内 `ldrb sl,[r2]`（读字符串首字节）
⇒ **SIGSEGV @0x80**，崩溃点 `mui_outputxy_t+0x84`（`r2 = 0x80`）与之逐位吻合。

这类写法**编译不报错、类型上"合法"、绝大多数时候也不崩**（只有当低字节凑巧是非法地址时
才崩），属于最难查的一类。故作硬门禁。

## 判据

匹配 `<窄类型> *` 的转型**直接作用在一个解引用表达式上**：

    (gh_byte *) * (...)          ← 危险：先解引用（宽度由被转型的表达式决定），再当指针
    (unsigned char *) *(u32 *)p ← 同上

**不**匹配（安全、只是多余的外层转型）：
    (gh_byte *) &X               ← 取地址，值不变
    (gh_byte *) puVar15          ← 裸指针，值不变
    (gh_byte *) 0x3af708         ← 常量

自证（铁律 101）：构造性 —— 把已知的危险样本喂给判据，必须命中；把安全样本喂进去，
必须不命中。两者都对才出结论。

退出码：0 = 无新增；1 = 有新增；2 = 自证失败。
"""
import argparse
import glob
import os
import re
import sys

NARROW = r'(?:gh_byte|gh_u1|unsigned\s+char|signed\s+char|char|undefined1|byte|uint8_t)'

# ★★ 判据必须收窄（第一版太宽，误报 13/15）：危险的本质是**解引用本身是窄宽度**
#   —— 即 `(窄类型 *)  *(窄类型 *) expr`：内层转型决定读取宽度 = 1 字节，
#   于是拿到「指针的低字节」再当指针用。
#   反例（合法，必须不报）：`(char *)*m_search`（m_search 是 char**，解引用得 char*）、
#   `(unsigned char*)*outbuf`（libiconv 同形）、`(gh_byte *)*(gh_u4 *)(p+4)`（内层是字）。
#   ⇒ 只匹配「内外都是窄指针转型」这一种确诊形态：宁可漏报，不可乱报。
PAT_DANGER = re.compile(
    r'\(\s*' + NARROW + r'\s*\*\s*\)\s*\*\s*\(\s*' + NARROW + r'\s*\*\s*\)')
# 安全对照：转型后直接跟 & 或标识符或常量
PAT_SAFE = re.compile(
    r'\(\s*' + NARROW + r'\s*\*\s*\)\s*(?:&|[A-Za-z_(0-9])')


def scan_text(text):
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if '//' in line:
            head = line.split('//', 1)[0]
        else:
            head = line
        if head.lstrip().startswith('*') or head.lstrip().startswith('/*'):
            continue                                   # 注释行不算
        for m in PAT_DANGER.finditer(head):
            out.append((i, m.start(), line.strip()[:150]))
    return out


def scan_tree(root):
    hits = []
    n = 0
    for pat in ('src/**/*.c', 'src/**/*.h'):
        for p in glob.glob(os.path.join(root, pat), recursive=True):
            n += 1
            try:
                txt = open(p, encoding='utf-8', errors='replace').read()
            except OSError:
                continue
            for ln, col, snip in scan_text(txt):
                hits.append((os.path.relpath(p, root), ln, snip))
    return hits, n


def selfcheck():
    """构造性自证：危险样本必须命中、安全样本必须不命中。"""
    danger = [
        'x = f(a, (gh_byte *)*(gh_byte *)puVar15);',
        'y = g((unsigned char *) *(unsigned char *)p);',
        'z = h(a, b, (gh_u1 *)*(gh_byte *)q);',
    ]
    safe = [
        'x = f(a, (gh_byte *)&DAT_003af708);',
        'y = f(a, (gh_byte *)puVar15);',
        'z = (gh_byte *)*puVar15;',                    # ← 本轮的正确修法，必须放行
        'w = (char *)*m_search;',                      # m_search 是 char** ⇒ 合法
        'v = (gh_byte *)*(gh_u4 *)(p + 4);',           # 内层是字 ⇒ 合法
        'u = (unsigned char*)*outbuf;',                # libiconv 同形 ⇒ 合法
    ]
    ok = True
    for t in danger:
        if not scan_text(t):
            print('  [selfcheck] ✗ 危险样本未命中：%s' % t)
            ok = False
    for t in safe:
        if scan_text(t):
            print('  [selfcheck] ✗ 安全样本被误报：%s' % t)
            ok = False
    if ok:
        print('  [selfcheck] 构造性自证 %d 危险 + %d 安全 全部正确 ✓'
              % (len(danger), len(safe)))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--ledger', default=None,
                    help='已知项台账（每行 "file line"）：台账内不判失败；新增一律失败')
    ap.add_argument('--write-ledger', action='store_true')
    a = ap.parse_args()

    if not selfcheck():
        return 2

    hits, nfiles = scan_tree(a.root)
    print('  扫描 %d 个文件，命中 %d 处' % (nfiles, len(hits)))

    if a.write_ledger:
        path = a.ledger or 'tools/narrow_deref_pending.txt'
        with open(path, 'w', encoding='utf-8', newline='\n') as f:
            f.write('# 「窄指针转型 + 解引用」已知项台账（棘轮）\n')
            f.write('# 格式: <file> <line>\n')
            f.write('# 危险语义：`(gh_byte *)* expr` 会把**指针低字节**当指针用（见工具 docstring）。\n')
            for fp, ln, _ in hits:
                f.write('%s %d\n' % (fp, ln))
        print('  已写入台账：%d 项（%s）' % (len(hits), path))
        return 0

    if a.ledger and os.path.exists(a.ledger):
        pend = set()
        for ln in open(a.ledger, encoding='utf-8'):
            ln = ln.strip()
            if ln and not ln.startswith('#'):
                q = ln.split()
                if len(q) >= 2:
                    pend.add((q[0], q[1]))
        cur = {(fp, str(ln)) for fp, ln, _ in hits}
        newv = [h for h in hits if (h[0], str(h[1])) not in pend]
        gone = sorted(pend - cur)
        if gone:
            print('  ★ 台账条目已消失（= 已修好）⇒ 请删行：')
            for fp, ln in gone[:8]:
                print('     %s:%s' % (fp, ln))
        if newv:
            print('  ★★ 新增 %d 处（不在台账内 ⇒ 判失败）：' % len(newv))
            for fp, ln, snip in newv[:20]:
                print('     %s:%d  %s' % (fp, ln, snip))
            return 1
        print('  [PASS] 无新增（台账剩余 %d 项）' % len(pend))
        return 0

    if hits:
        print('  ★ 命中 %d 处：' % len(hits))
        for fp, ln, snip in hits[:20]:
            print('     %s:%d  %s' % (fp, ln, snip))
        return 1
    print('  ✓ 未发现「窄指针转型 + 解引用」写法')
    return 0


if __name__ == '__main__':
    sys.exit(main())
