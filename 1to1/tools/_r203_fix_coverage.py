#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R203 收尾：修正 PROGRESS.md §1「覆盖率硬数字」表格（旧 788/47 口径 → 785/50 全量分类）。

原子改写：写 .tmp → 校验 → os.replace（遵守红线：禁止 open(w) 直接覆盖唯一副本）。
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'PROGRESS.md')

s = io.open(P, encoding='utf-8', newline='').read()  # newline='' 保留原始 \r\n

MARK = '## 1. 覆盖率硬数字'
assert s.count(MARK) == 1, 'marker 非唯一'
i = s.index(MARK)
j = s.index('\n## ', i + len(MARK))  # 下一个二级标题结束本段

NEW = '''## 1. 覆盖率硬数字

> ★ 2026-10-18（R203 审计重算）：产物 `.symtab` 按 `STT_FUNC + size>0` 命中 **785**，
> OBJECT 命中 **0** ⇒ 覆盖率 **94.0%**（785/835），缺失 **50**。旧表"788/47"是含 OBJECT
> 的不同口径 + 陈旧产物，已废弃。真正待补 = 2 个 stb 符号（根因陈旧产物，非源码缺失，见 §5 R203）。

| 指标 | 值 | 证据 |
| --- | --- | --- |
| 工厂具名符号 | **835** | `factory.funcs.json` 键数 |
| 产物中已定义（STT_FUNC 且 size>0） | **785** | 产物 `.symtab` 遍历（OBJECT 命中 0） |
| **符号覆盖率** | **94.0%**（785/835） | 产物 `.symtab` ∩ 工厂符号集 |
| 产物缺失符号 | **50**（6.0%） | 同上差集（全量分类见下） |
| ├ CRT 样板（工具链提供，工厂 size=0） | 6 | `_start` / `call_weak_fn` / `register_tm_clones` / `deregister_tm_clones` / `frame_dummy` / `__do_global_dtors_aux` |
| ├ 编译器内建（libgcc 提供） | 3 | `.divsi3_skip_div0_test` / `__aeabi_idiv` / `__aeabi_uidiv` |
| ├ GCC 分片标记（`.part`/`.isra`/`.constprop`） | 12 | base 函数已在产物中，分片并入（如 `code_convert.constprop.22` ← `code_convert`） |
| ├ 音效族（工厂 `STT_NOTYPE size=0`，非代码） | **25** | `__SetKeySound*` / `__DialogboxSound*` / `__Effect1` 等 |
| └ **真实缺口** | **4** | `load_state`(4B 尾跳板) / `save_state`(4B 尾跳板) + `stbtt__csctx_rline_to`(84B) / `stbtt__cuberoot`(72B) |

分类合计 6 + 3 + 12 + 25 + 4 = **50**。其中 `load_state`/`save_state` 工厂侧为 1 条指令尾跳板
（`b @retro_load_state`），我方已实现实体 `retro_load_state`(352B)/`retro_save_state`(368B)
⇒ **等价非缺口**。真正待补仅 `stbtt__csctx_rline_to` + `stbtt__cuberoot` 2 个，根因是本机
产物陈旧（10-02 早于 stb 源码 10-04），非源码缺失。
'''

if '\r\n' in s:
    NEW = NEW.replace('\n', '\r\n')

s2 = s[:i] + NEW + s[j:]
assert '785/835' in s2, '新口径 785/835 未写入'
assert s2.count('## 1. 覆盖率硬数字') == 1, 'marker 数量异常'

tmp = P + '.tmp'
with io.open(tmp, 'w', encoding='utf-8', newline='') as f:
    f.write(s2)
os.replace(tmp, P)
print('OK 已改写 PROGRESS.md §1：%d -> %d 字节' % (len(s), len(s2)))