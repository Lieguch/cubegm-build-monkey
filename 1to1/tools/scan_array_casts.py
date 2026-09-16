#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态门禁：揪出「把**数组名**直接转型成窄整数」这类 Ghidra 误渲染。

## 血泪来历（P5 深窗口抓到的第二个真实语义分歧）

工厂侧 `spi_driver_init()` 里的判断原指令是：

    ldrb r3, [r6]      ; r6 = &spi_id  ⇒ 读 spi_id 的**第一个字节**
    cmp  r3, #11

Ghidra 把它渲染成 C 的 `(gh_byte)spi_id`。当 `spi_id` 被我们声明为**数组**
（`extern unsigned char spi_id[3];`）时，这个表达式的真实语义变成
**「取 spi_id 地址的最低位字节」**（指针→整数转换），而不是读内存！

后果（实测）：
  · 重建侧读到 `0xc8`（= 0x003e1ac8 的低字节）而不是 `0x0b`
  · ⇒ 两处 `spi_id[0] == 0xb` 判断全部走错分支
  · ⇒ `spi_driver_init()` 返回 0（而不是 1）
  · ⇒ main() 不去 `main_Menu()`，观测窗口少 4 行
  · 而且**编译/链接/ABI/布局/符号审计全部是绿的** —— 只有行为差分能发现。

## 判据

  `(窄整数类型) 数组名` 且数组名**后面不是 `[`**（`arr[i]` 的元素访问是合法的），
  窄类型 = 1 或 2 字节（char / unsigned char / short / gh_byte / gh_u1 / gh_u2 …）。

  ★ 宽类型（如 `(gh_uint)environment_str`）**不报**：那是「把数组地址当整数存」，
    在工厂里确实存在且合法（例如 `environment()` 把字符串地址写进调用者的结构体）。

用法:
  python tools/scan_array_casts.py [src_root]
退出码: 0 = 干净；2 = 有命中（打印文件:行:号）
"""
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

NARROW = r"(?:gh_byte|gh_u1|gh_s1|char|signed\s+char|unsigned\s+char|" \
         r"gh_u2|gh_s2|short|unsigned\s+short|signed\s+short|" \
         r"uint8_t|int8_t|uint16_t|int16_t)"


def arrays_from_globals(path):
    """从 globals.h 收集所有**数组**声明名。"""
    names = set()
    if not os.path.exists(path):
        return names
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.search(r"\bextern\b[^;]*?\b([A-Za-z_]\w*)\s*\[\s*\d*\s*\]\s*;", line)
        if m:
            names.add(m.group(1))
    return names


def strip_comments(txt):
    """去掉 // 与 /* */ 注释（保留字符串字面量），避免把**说明文字**当成代码命中。

    ★ 血泪：第一版扫描器报了 1 处「命中」—— 结果是我自己写在源码里的**解释性注释**
      （注释里正好引用了 `(gh_byte)spi_id` 这个错误写法）。门禁的第一版就出假阳性。
    """
    out = []
    i, n = 0, len(txt)
    while i < n:
        c = txt[i]
        if c == '"' or c == "'":
            q = c
            out.append(c)
            i += 1
            while i < n:
                out.append(txt[i])
                if txt[i] == chr(92):
                    i += 1
                    if i < n:
                        out.append(txt[i])
                elif txt[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == '/' and i + 1 < n and txt[i + 1] == '/':
            while i < n and txt[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and txt[i + 1] == '*':
            j = txt.find('*/', i + 2)
            i = n if j < 0 else j + 2
            out.append(' ')
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'src')
    globals_h = os.path.join(src, 'compat', 'globals.h')
    arrs = arrays_from_globals(globals_h)
    print('数组声明 : %d 个（来自 %s）' % (len(arrs), os.path.relpath(globals_h, ROOT)))
    if not arrs:
        print('!! 未解析到任何数组声明 —— 脚本会静默空转，请检查 globals.h 格式')
        return 2

    #  (窄类型) 名字   且名字后面不是 '[' 也不是 '('
    pat = re.compile(r"\(\s*" + NARROW + r"\s*\)\s*([A-Za-z_]\w*)\s*(.)", re.S)
    hits = []
    files = sorted(glob.glob(os.path.join(src, 'proprietary', '**', '*.c'), recursive=True))
    for f in files:
        txt = strip_comments(open(f, encoding='utf-8', errors='replace').read())
        for m in pat.finditer(txt):
            name, nxt = m.group(1), m.group(2)
            if name not in arrs:
                continue
            if nxt == '[':          # arr[i] 元素访问：合法
                continue
            if nxt == '(':          # 函数调用：不是变量
                continue
            ln = txt.count('\n', 0, m.start()) + 1
            line = txt.splitlines()[ln - 1].strip()
            hits.append((os.path.relpath(f, ROOT).replace(os.sep, '/'), ln, line))

    print('受检文件 : %d 个（src/proprietary/**/*.c）' % len(files))
    if hits:
        print()
        print('!! 命中 %d 处「数组名被转型成窄整数」（= 指针→整数，几乎必然是 Ghidra 误渲染）:'
              % len(hits))
        for f, ln, line in hits:
            print('   %s:%d' % (f, ln))
            print('        %s' % line[:150])
        print()
        print('   修法：把 `(窄类型)arr` 改成 `arr[0]`（原指令是 ldrb/ldrh 读内存时）。')
        print('   依据：先回汇编看那条指令是不是 `ldrb rX,[rY]`（rY = arr 的地址）。')
        return 2

    print('结论     : PASS（无「数组名→窄整数」误渲染）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
