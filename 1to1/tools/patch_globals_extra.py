#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_globals_extra.py — globals.h 「生成后补丁区」（幂等 + 按声明去重 + 保留换行风格）。

★ 血泪教训（2026-09-13）
------------------------
`gen_compat.py` **不能单独重跑**：它只生成主声明块，globals.h 还需要三类补充：

  ① `#include "named_array_blobs.h"` —— 13 个数组全局的 `_blob` 宏（gen_named_array_blobs.py 产出）
  ② 2 个工厂大对象（`asc2_1608` / `default_core_list`）+ 2 个「被 Ghidra 误渲染成符号地址的
     整数常量」兜底声明（`DAT_00061a80` / `DAT_000f4240`）
  ③ 重名拆分别名（P3 二期④）：`handle_emurun` / `diff_prev_global`

漏掉任一项都会让编译通过率从 **100% 崩到 48%**（实测 103/213）。

本脚本把这三类补丁做成幂等：已存在同名声明则不再重复添加；
读写均用 `newline=''` 保留原文件换行风格（避免整文件 diff 噪声）。
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'src', 'compat', 'globals.h')

# (声明行, 该行引入的标识符)
EXTRA = [
    ('/* @0x003b1d34 pointer */ extern void * PTR_asc2_1608_003b1d34;',
     'PTR_asc2_1608_003b1d34'),
    ('/* @0x002e0928 .rodata 1520B (symtab g O 000005f0) */ extern unsigned char asc2_1608[1520];',
     'asc2_1608'),
    ('/* @0x003b1e34 pointer */ extern void * PTR_default_core_list_003b1e34;',
     'PTR_default_core_list_003b1e34'),
    ('/* @0x003b0254 .data 6800B (symtab g O 00001a90) */ extern unsigned char default_core_list[6800];',
     'default_core_list'),
    ('/* fallback */ extern unsigned char DAT_00061a80[];', 'DAT_00061a80'),
    ('/* fallback */ extern unsigned char DAT_000f4240[];', 'DAT_000f4240'),
    ('/* @0x003cf988 undefined4 */ extern void * handle_emurun;   '
     '/* EmuRun.c 的 static handle（dlopen 句柄） */', 'handle_emurun'),
    ('/* @0x003e1a38 undefined4 */ extern unsigned int diff_prev_global;  '
     '/* 全局份（经 GOT 引用） */', 'diff_prev_global'),
]

ANCHOR = '#include "named_array_blobs.h"'
HEAD = ('/* ============================================================\n'
        ' * ★ 补丁区（由 tools/patch_globals_extra.py 幂等注入）\n'
        ' *   gen_compat.py 只生成上面的主块，本区是它覆盖不到的必要补充。\n'
        ' * ============================================================ */')


def has_decl(s, name):
    return re.search(r'extern [^;\n]*\b%s\b\s*(?:\[[^\]]*\])?\s*;' % re.escape(name), s) is not None


def main():
    s = open(PATH, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'

    todo = [ln for ln, nm in EXTRA if not has_decl(s, nm)]
    need_anchor = ANCHOR not in s
    need_head = '★ 补丁区' not in s
    if not todo and not need_anchor and not need_head:
        print('补丁区已完整，跳过（幂等）')
        return 0

    block = []
    if need_head:
        block.append(HEAD)
    block += todo
    if need_anchor:
        block += ['', '/* 13 个数组全局的 _N_M_ 成员覆盖结构 + 指针 cast 宏（须在本头声明之后） */',
                  ANCHOR]
    block = nl.join(block) + nl

    if ANCHOR in s:
        # ★ 踩坑：str.partition 返回的 tail **不包含分隔符**（'aXb'.partition('X') == ('a','X','b')）
        #   —— 早前写成 head + block + tail 会把 #include 整行吃掉：
        #   症状是 42 个文件报 `use of undeclared identifier 'game_blob'`（blob 宏全部消失）。
        head, _sep, tail = s.partition(ANCHOR)
        s = head.rstrip('\r\n') + nl + block + ANCHOR + tail
    else:
        idx = s.rfind('#endif')
        if idx < 0:
            print('!! 未找到 #endif，请人工检查', file=sys.stderr)
            return 1
        s = s[:idx] + block + ANCHOR + nl + s[idx:]

    if ANCHOR not in s or not has_decl(s, 'handle_emurun') or not has_decl(s, 'diff_prev_global'):
        print('!! 补丁自检失败：include 或拆分声明缺失', file=sys.stderr)
        return 1

    open(PATH, 'w', encoding='utf-8', newline='').write(s)
    print('已注入 %d 条声明（含 include=%s）→ %s'
          % (len(todo), need_anchor, os.path.relpath(PATH, ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
