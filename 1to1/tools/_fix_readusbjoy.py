#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ReadUSBJoy 的 UB 根修：把被 Ghidra 拆成 4 份的一块 8 字节缓冲合并回去。

## 根因（2026-09-27，与 UpdateROM 同类但成因不同）

Ghidra 把 `read(iVar1, auStack_40, 8)` 的目标块拆成 4 个独立声明：
    gh_u1 auStack_40 [4];   short local_3c;   char local_3a;   gh_byte local_39;
于是源码里**只有 auStack_40 被 write 写过**（read 只写了 4 字节可见），
`local_3c` / `local_3a` / `local_39` 在编译器看来**从未被写** ⇒ 读未初始化 = **UB**。

实测后果：`-O0` = 14744 B（完整） / `-Os` = **520 B**（工厂 1196 B，0.435x）
⇒ 优化器据此大量删码。clang 原话见 `tools/ub_census.py`：
    warning: variable 'local_3c' is uninitialized when used here [-Wuninitialized]

## 布局取证（不是猜）

Linux `struct js_event` = `__u32 time; __s16 value; __u8 type; __u8 number;` ⇒ 8 字节，
偏移 0/4/6/7。Ghidra 的栈名序号**随地址升高而减小**，故：
    auStack_40(0x40) → 偏移 0   （time，4B）
    local_3c (0x3c) → 偏移 4   （value，short）
    local_3a (0x3a) → 偏移 6   （type，1B）
    local_39 (0x39) → 偏移 7   （number，1B）
与 `read(..., 8)` 的 8 字节、以及 `local_3c` 作 `short`、`local_3a` 与 `'\x01'/'\x02'` 比较、
`local_39` 当按钮号索引 —— **逐项吻合**。
"""
import io
import re
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "src", "proprietary", "input", "FUN_0000c150_ReadUSBJoy.c")

OLD_DECL = """  gh_u1 auStack_40 [4];
  short local_3c;
  char local_3a;
  gh_byte local_39;
"""
NEW_DECL = """  /* ★★ 2026-09-27 根修（UB）：Ghidra 把**一块 8 字节缓冲**（Linux `struct js_event`：
   *   time(4) / value(2) / type(1) / number(1)）拆成了 4 个独立声明，
   *   `read(iVar1, auStack_40, 8)` 只写了被看见的那一部分 ⇒ 其余三个字段在编译器看来
   *   **从未被写** ⇒ 读未初始化 = UB ⇒ 优化器删码。
   *   实测：-O0=14744B（完整） / -Os=**520B**（工厂 1196B，0.435x）。
   *   修法：恢复成一块真缓冲 + 三个按偏移的视图（偏移由 `struct js_event` 布局取证）。 */
  gh_u1 ev_buf[8];
#define ev_value  (*(short *)(void *)(ev_buf + 4))
#define ev_type   (*(unsigned char *)(void *)(ev_buf + 6))
#define ev_number (*(unsigned char *)(void *)(ev_buf + 7))
"""


def main():
    s = io.open(P, encoding="utf-8").read()
    if OLD_DECL not in s:
        print("!! 声明块未命中（可能已修过）")
        return 2
    s = s.replace(OLD_DECL, NEW_DECL, 1)
    # read 的目标
    before = s
    s = s.replace("read(iVar1,auStack_40,8)", "read(iVar1,ev_buf,8)", 1)
    assert s != before, "read 调用未命中"
    # 三个视图的整体重命名（只在函数体内出现，用词边界）
    n = {}
    for old, new in (("local_3c", "ev_value"), ("local_3a", "ev_type"),
                     ("local_39", "ev_number")):
        s, k = re.subn(r"\b%s\b" % old, new, s)
        n[old] = k
    io.open(P, "w", encoding="utf-8", newline="\n").write(s)
    print("重命名：", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
