#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""patch_uicfg.py — 给 `ui_cn.zip` 里的 `ui.cfg` 补上 `GameList_count`

背景（第 49 轮，逐条有源码/机器码证据）：
  · `mui_LoadConfig`（`src/proprietary/mui/FUN_0001f580_mui_LoadConfig.c:143-149`）：
        get_value_from_items("GameList_count",local_128,configitems,uVar2);
        if (local_128[0] == '\\0') { DAT_003af394 = 0xb; }          /* 缺字段 ⇒ 默认 11 */
        else { __isoc99_sscanf(local_128,"%d",&DAT_003af394); }
  · `DAT_003af394`（每屏列表项数）是**所有列表循环的统一上界**：
        mui_do_file_list.c  :68   if ((iVar9 < param_1) || (DAT_003af394 <= iVar10))
        dir_serial_list.c   :82   (iVar11 < DAT_003af394)          ← 目录扫描的填充条件
        mui_menu.c / mui_type.c / DisplayPage_list.c …
    ⇒ 它为 0 时，`file_info_list`（readdir 填充）与 root.dat 的 `fileinfo.txt`（文本解析填充）
      **两条路径都不会被消费** ⇒ 缩略图路径退化成 `/sdcard//.dat`（场景 I/J/K 实测 29 行）。
  · `configitems` 来自 `get_items_from_zipfile("<ui_xx.zip>", …)` —— 即 UI 资源包里的 `ui.cfg`；
    而 `golden/sdcard_min/ui_cn.zip/ui.cfg`（242 B）只有 `[Setting]` / `Recover*`，
    **没有 `GameList_count`**。

本工具**只补这一个键**（值取程序自身的默认 11，不自行编造数值），其余条目与注释保持原样：
  · `ui.cfg` 文本 = 原样 + 追加一行 `GameList_count=11`（若已存在则不重复追加）；
  · 其余 zip 条目按内容原样重打包（逻辑内容逐字节保留）。
"""
import argparse
import os
import sys
import zipfile

KEY = 'GameList_count'
DEFAULT_N = 11          # 与程序内置默认一致（0xb），不自行编造


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', required=True, help='ui_cn.zip 的路径（就地改写）')
    ap.add_argument('--value', type=int, default=DEFAULT_N)
    ap.add_argument('--entry', default='ui.cfg')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    if not os.path.isfile(a.zip):
        print('FATAL 找不到 %s' % a.zip)
        return 1
    with zipfile.ZipFile(a.zip) as z:
        items = z.infolist()
        names = [i.filename for i in items]
        if a.entry not in names:
            print('FATAL %s 里没有 %s（现有条目: %s）' % (a.zip, a.entry, names[:8]))
            return 1
        raw = {i.filename: z.read(i.filename) for i in items}

    cfg = raw[a.entry].decode('utf-8', 'replace')
    if KEY in cfg:
        print('   [UICFG] %s 已含 %s ⇒ 无需改动（幂等）' % (a.entry, KEY))
        return 0

    before_len = len(raw[a.entry])
    # 行尾风格保持原样：若原文含 \r\n 就用 \r\n
    nl = '\r\n' if '\r\n' in cfg else '\n'
    if not cfg.endswith(('\n', '\r')):
        cfg += nl
    cfg += '%s=%d%s' % (KEY, a.value, nl)
    raw[a.entry] = cfg.encode('utf-8')

    if a.dry:
        print('   [UICFG] (dry) 会在 %s 追加 %s=%d' % (a.entry, KEY, a.value))
        return 0

    tmp = a.zip + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for i in items:
            z.writestr(i.filename, raw[i.filename])
    os.replace(tmp, a.zip)

    # 自证：条目集合不变 + ui.cfg 里确实有那个键
    with zipfile.ZipFile(a.zip) as z:
        after = [i.filename for i in z.infolist()]
        got = z.read(a.entry).decode('utf-8', 'replace')
    if after != names:
        print('FATAL 条目集合被改变: %s -> %s' % (names, after))
        return 1
    if KEY not in got:
        print('FATAL 追加后仍找不到 %s' % KEY)
        return 1
    line = [l for l in got.replace('\r', '').split('\n') if l.startswith(KEY)]
    print('   [UICFG] %s 追加 %r（ui.cfg %d B -> %d B；zip 条目 %d 个不变）'
          % (a.entry, line[0] if line else KEY, before_len, len(raw[a.entry]), len(after)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
