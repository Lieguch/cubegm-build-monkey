#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修掉 `tools/ub_census.py` 剩下的 5 个 UB 命中（同一类：Ghidra 把一块缓冲拆小/写越界）。

为什么必须修完：UB 会让优化器**静默删代码**（实证 `UpdateROM` 被删 864 B）。
新门禁 `link_full.sh exit 18` 是 fail-closed ⇒ 不自欺地把这 5 个挂在那里。

全部改动都是"把假尺寸恢复成真尺寸"+ 用显式转换保持原语义，不改逻辑。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(ROOT, "src", "proprietary")
G = os.path.join(ROOT, "src", "compat", "globals.h")

EDITS = []


def patch(path, pairs, tag):
    p = os.path.join(ROOT, path)
    s = io.open(p, encoding="utf-8").read()
    for old, new in pairs:
        if old not in s:
            print("  !! %s 未命中: %r" % (tag, old[:70]))
            return False
        s = s.replace(old, new, 1)
    io.open(p, "w", encoding="utf-8", newline="\n").write(s)
    print("  ✓ %s" % tag)
    return True


ok = True

# ---- 1) gpsp_unzip.c：声明 296 B，实际 memset 0x130 = 304 B ----
ok &= patch("src/proprietary/misc/FUN_002b4e20_gpsp_unzip.c", [(
    "  gh_u1 auStack_140 [296];",
    "  /* 根修（UB）：Ghidra 声明 296 B，函数体 `memset(auStack_140, 0, 0x130)` 实际写 304 B\n"
    "     ⇒ 越界 = UB ⇒ 优化器可删码。恢复真实尺寸。 */\n"
    "  gh_u1 auStack_140 [0x130];")], "gpsp_unzip.c auStack_140 296->0x130")

# ---- 2) run_game.c：`int local_158` 却 memset 0x130 / 当字符串缓冲用 ----
ok &= patch("src/proprietary/core/FUN_002b7510_run_game.c", [
    ("  int local_158;",
     "  /* 根修（UB）：这是**一块 0x130 字节栈缓冲**（Ghidra 误声明为 4 字节 int）。\n"
     "     `memset(&local_158,0,0x130)` / `GetZipItemA(...,&local_158)` /\n"
     "     `extract_basepath((char*)&local_158,...)` 都按缓冲用 ⇒ 原声明使 memset 越界 = UB。 */\n"
     "  gh_u1 local_158[0x130];"),
    ("if (1 < local_158) {", "if (1 < *(int *)(void *)local_158) {"),
], "run_game.c local_158 -> 0x130 缓冲")

# ---- 3) FilePreEmu.c：同形 ----
ok &= patch("src/proprietary/core/FUN_00016f08_FilePreEmu.c", [
    ("  int local_158;",
     "  /* 根修（UB）：同 run_game.c —— 这是 0x130 字节栈缓冲，非 4 字节 int。 */\n"
     "  gh_u1 local_158[0x130];"),
    ('RARCH_LOG("zipcount %d\\n",local_158);',
     'RARCH_LOG("zipcount %d\\n",*(int *)(void *)local_158);'),
], "FilePreEmu.c local_158 -> 0x130 缓冲")

# ---- 4) mui_DisplayGameSum.c：sprintf 写 8 字节进 4 字节标量 ----
ok &= patch("src/proprietary/mui/FUN_0001bf80_mui_DisplayGameSum.c", [
    ("  gh_u4 uStack_98;",
     "  /* 根修（UB）：`sprintf((char*)&uStack_98, \"%3d/%3d\", ...)` 最多写 7 字节 + NUL，\n"
     "     而 Ghidra 只声明 4 字节 gh_u4 ⇒ 越界 = UB。恢复成 16 字节缓冲（保对齐）。 */\n"
     "  gh_u1 uStack_98[16];"),
    ("    uStack_98 = 0x2f2d2020;", "    *(gh_u4 *)(void *)uStack_98 = 0x2f2d2020;"),
    ('sprintf((char *)&uStack_98,"%3d/%3d",iVar3 + 1,iVar2 + 1);',
     'sprintf((char *)uStack_98,"%3d/%3d",iVar3 + 1,iVar2 + 1);'),
    ("(gh_byte *)&uStack_98)", "(gh_byte *)uStack_98)"),
], "DisplayGameSum.c uStack_98 -> 16 B 缓冲")

# ---- 5) mui_LoadSetting.c + globals.h：对象 4 B，却 memset 0x50 ----
ok &= patch("src/compat/globals.h", [(
    "/* @0x003af2bc undefined4 */ extern void * DAT_003af2bc;  /* 修正：承载 UI 缓冲指针(puVar12) */",
    "/* @0x003af2bc **0x50 字节对象**（不是 4 字节指针）——\n"
    "   根修（UB）：`memset(&DAT_003af2bc, 0, 0x50)` 写 80 字节，而声明只有 4 字节 ⇒ 越界 = UB。\n"
    "   首个字段是 `void*`（`DAT_003af2bc = puVar12`），故用缓冲 + 显式转换。 */\n"
    "extern gh_u1 DAT_003af2bc[0x50];")], "globals.h DAT_003af2bc -> 0x50 缓冲")
ok &= patch("src/proprietary/mui/FUN_000171f8_mui_LoadSetting.c", [
    ("        memset(&DAT_003af2bc,0,0x50);", "        memset(DAT_003af2bc,0,0x50);"),
    ("          DAT_003af2bc = puVar12;",
     "          *(void **)(void *)DAT_003af2bc = puVar12;"),
], "mui_LoadSetting.c DAT_003af2bc 用法")

print("ALL OK" if ok else "有未命中项")
sys.exit(0 if ok else 2)
