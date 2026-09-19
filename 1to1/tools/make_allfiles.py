#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_allfiles.py — 按独立逆向资料的确切格式合成 `cubegm/allfiles.lst`

外部依据（`github.com/LiamJ74/R36S-V2.6_Wiki`，同族固件的独立逆向 Wiki，非本人推断）：
  · 位置：SD 卡 `cubegm/allfiles.lst`（"Master game index"）
  · 格式（逐字）：`Platform/filename.ext|Display Name|UPPERCASE NAME|Chinese Name|Abbreviated`
  · 运行时：`rkgame` 启动时 **"loads ... game lists from allfiles.lst / filelist.csv"**
    —— 即读**列表文件**，不是实时 readdir。
  · 症状对应：菜单里看不到游戏时的官方解释就是 **"allfiles.lst is out of sync with actual ROM files"**。
  · 新条目占位规则（逐字）："New entries use the ROM basename as a placeholder for all name fields."

本机铁证（用于确定 Platform 段）：
  · `golden/sdcard_min/cores/filelist.xml` 的条目形如 `name="002/Targa (Europe) (Proto).zip"`
    ⇒ 本机（RK3036G/SF3000 系）用 `NNN/` 数字目录，而 R36S 用平台英文名 ⇒ **Platform 段取 `NNN`**。
  · 两侧共用同一份；只造索引（不造 ROM 内容），不越"可得真值源"的边界。
"""
import argparse
import os
import re
import sys

NL = '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--golden', required=True)
    ap.add_argument('--work', required=True, help='铺好的运行目录（= CGM_WORK，allfiles.lst 落在这里）')
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()

    fl = os.path.join(a.golden, 'cores', 'filelist.xml')
    with open(fl, encoding='utf-8', errors='replace') as f:
        names = re.findall(r'name="([^"]+)"', f.read())
    if not names:
        print('FATAL %s 里没有 name=' % fl)
        return 1

    lines = []
    for n in names:
        rel = n.replace('\\', '/')
        base = os.path.basename(rel)
        stem = base[:-4] if base.lower().endswith('.zip') else os.path.splitext(base)[0]
        # 逗号会破坏列表（wiki 明示脚本会重命名去逗号）⇒ 与官方同步脚本同策略
        stem = stem.replace(',', ' ')
        lines.append('%s|%s|%s|%s|%s' % (rel, stem, stem.upper(), stem, stem[:12]))

    out = os.path.join(a.work, 'allfiles.lst')
    blob = (NL.join(lines) + NL).encode('utf-8')

    if not a.dry:
        with open(out, 'wb') as f:
            f.write(blob)

    # 自证：① 行数 == 条目数；② 每行 5 段；③ 首段都能 split 出目录名（dir_serial_list 需要 NNN/ 形态）
    if not a.dry:
        with open(out, 'rb') as f:
            back = f.read()
        if back != blob:
            print('FATAL allfiles.lst 回读不一致')
            return 1
        got = back.decode('utf-8').rstrip(NL).split(NL)
        if len(got) != len(names):
            print('FATAL 行数 %d != 条目数 %d' % (len(got), len(names)))
            return 1
        bad = [l for l in got if len(l.split('|')) != 5 or '/' not in l.split('|')[0]]
        if bad:
            print('FATAL %d 行格式不符（首例: %r）' % (len(bad), bad[0]))
            return 1

    print('   [ALLFILES] built %s（%d 行 / %d B；格式 Platform/filename.ext|Display|UPPER|Chinese|Abbrev）'
          % (out, len(lines), len(blob)))
    print('   [ALLFILES] 首行: %s' % lines[0])
    print('   [ALLFILES] 末行: %s' % lines[-1])
    return 0


if __name__ == '__main__':
    sys.exit(main())
