#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shim 输出文案的「可 JSON 化」检查。

## 为什么需要它（2026-09-19 第 48 轮实测事故）

`behav_capture.sh` 把 guest 的 stdout / stderr 逐行收进 `behav_*.json`。
JSON **不允许**字符串里出现裸控制字符（U+0000..U+001F，除 \\t \\n \\r）。

事故链：

1. shim 的 key2 探针文案里我写了 `PK\\x05\\x06`（**真转义**）⇒ 输出里带 ENQ/ACK 两个控制字节；
2. 该行进入 stderr 事件 ⇒ `behav_rebuild.json` **非法**；
3. `behav_diff.py` 抛 `json.decoder.JSONDecodeError: Invalid control character`；
4. 而 CI 仍然报 **success**（`rc` 被记录但没有据此报错）
   ⇒ **场景 B / E / F 三个全部静默失去判定**。

⇒ 本检查：扫描 shim 源码的**字符串字面量**，报告其中的真控制字符转义。

## 判据的关键（容易写错的地方）

必须区分反斜杠个数：

| 写法 | 反斜杠数 | C 编译器解释 | 危险 |
|---|---|---|---|
| `"PK\\x05\\x06"` | 1（奇数） | 控制字符 ENQ/ACK | ★ 是 |
| `"PK\\\\x05\\\\x06"` | 2（偶数） | 字面文本 `\\x05\\x06` | 否 |

只把**奇数个反斜杠 + xHH** 视为真转义。

## 用法

    python tools/check_shim_charset.py --root .            # 检查（0=通过）
    python tools/check_shim_charset.py --root . --verbose
"""
import argparse
import os
import re
import sys

NL = chr(10)
BS = chr(92)
Q = chr(34)

# 字符串字面量（允许内部转义），不跨行匹配拼接 —— 逐段扫已足够。
STR_RE = re.compile(Q + r'(?:[^"' + BS + BS + r']|' + BS + BS + r'.)*' + Q)
# (反斜杠+)+xHH —— 反斜杠组用于判定奇偶
HEX_RE = re.compile(r'(' + BS + BS + r'+)x([0-9a-fA-F]{1,2})')
OCT_RE = re.compile(r'(' + BS + BS + r'+)([0-7]{3})')

ALLOWED = (0x09, 0x0A, 0x0D)


def raw_ctrl_in_strings(src):
    """返回 [(行号, 转义文本, 片段)]：字符串字面量里的**真**控制字符转义。"""
    hits = []
    for m in STR_RE.finditer(src):
        seg = m.group(0)
        ln = src[:m.start()].count(NL) + 1
        for e in HEX_RE.finditer(seg):
            if len(e.group(1)) % 2 == 0:
                continue                      # 偶数个反斜杠 ⇒ 字面文本，安全
            v = int(e.group(2), 16)
            if 0x01 <= v <= 0x1F and v not in ALLOWED:
                hits.append((ln, 'x' + e.group(2), seg[:72]))
        for e in OCT_RE.finditer(seg):
            if len(e.group(1)) % 2 == 0:
                continue
            v = int(e.group(2), 8)
            if 0x01 <= v <= 0x1F and v not in ALLOWED:
                hits.append((ln, e.group(2), seg[:72]))
    return hits


def selfcheck():
    """构造性自证：坏样本必须命中、好样本必须放行（铁律：检查器先自证）。"""
    bad = Q + 'a' + BS + 'x05b' + Q                 # "a\x05b"    → 1 个反斜杠，真转义
    good = Q + 'a' + BS + BS + 'x05b' + Q           # "a\\x05b"   → 2 个反斜杠，字面文本
    nb = len(raw_ctrl_in_strings(bad))
    ng = len(raw_ctrl_in_strings(good))
    print('  [selfcheck] 坏样本命中 = %d（应 >=1）| 好样本命中 = %d（应 0）' % (nb, ng))
    if nb < 1 or ng != 0:
        sys.exit('  [FATAL] 检查器自证失败 ⇒ 判据不可信，拒绝出结论')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.')
    ap.add_argument('--shim', default=None, help='默认 <root>/tools/guest_shim/fake_mem.c')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    shim = a.shim or os.path.join(a.root, 'tools', 'guest_shim', 'fake_mem.c')
    if not os.path.exists(shim):
        print('  [SKIP] 找不到 %s（CI 上若无该文件则跳过）' % shim)
        return 0

    selfcheck()
    src = open(shim, 'rb').read().decode('utf-8', errors='replace')
    hits = raw_ctrl_in_strings(src)
    n_str = len(STR_RE.findall(src))
    print('  扫描 %s：字符串字面量 %d 段，裸控制字符转义 %d 处' % (shim, n_str, len(hits)))
    if hits:
        print()
        print('  ★★ 发现裸控制字符（会把 behav_*.json 变成非法 JSON ⇒ 场景判定静默失效）：')
        for ln, esc, frag in hits[:20]:
            print('     %5d| %-6s %s' % (ln, esc, frag))
        print()
        print('  修法：改用**可打印的十六进制文本**表达字节值，')
        print('        或写成双反斜杠的字面文本（如 PK' + BS + BS + 'x05' + BS + BS + 'x06 ⇒ 输出 PK' + BS + 'x05' + BS + 'x06）。')
        return 1
    print('  [PASS] shim 文案可安全 JSON 化（无裸控制字符）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
