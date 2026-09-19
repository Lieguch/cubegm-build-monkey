#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_gamedirs.py — 合成 `/sdcard/cubegm/NNN/` 游戏目录 + 占位游戏文件

背景（第 49 轮，逐条有源码/实测证据）：
  · `file_info_list` 的**真正填充路径**是 `dir_serial_list`
    （`src/proprietary/misc/FUN_0002142c_dir_serial_list.c:69`）：
        pcVar4 = strcpy(&file_info_list + iVar3, pdVar8->d_name);
        *(gh_uint *)(pcVar4 + 0x100) = (gh_uint)(*ppdVar7)->d_type;   /* 记录 d_type */
    即 readdir 扫目录后把**目录项名字**拷进数组。
  · 而 `mui_DisplayThumbnail` / `mui_type` 用 `mui_extract_basepath`（取 `strrchr('/')` 之前）
    拼 `sprintf("%s/%s/%s.dat", root_path, basepath, basepath)`。
  · 沙箱 `/sdcard/cubegm/` 顶层**没有** `000/` `002/` `004/` 三个游戏目录（只有 `cores/`）
    ⇒ `dir_serial_list` 列不出条目 ⇒ basepath 空 ⇒ 运行期反复 `open /sdcard//.dat fail`（实测 29 行）。

本工具按 `cores/filelist.xml` 的 `name=` 列表合成这些目录与占位文件：
  · 占位文件写成**最小合法 ZIP**（22 B 的 EOCD），不是 0 字节 —— 它们是 `.zip`，
    后续若被 `OpenZipU` 打开，0 字节会报"不是压缩包"，合法空 ZIP 只是"找不到条目"，噪声更小；
  · 只造**名字**（让 readdir 列得出来），不伪造内容 —— 不越"可得真值源"的边界。
"""
import argparse
import os
import re
import sys

# 22 字节的空 ZIP 结尾记录（EOCD）
EOCD = b'PK' + bytes([5, 6]) + b'\x00' * 18


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--golden', required=True, help='golden 环境目录（读 cores/filelist.xml）')
    ap.add_argument('--work', required=True, help='铺好的运行目录（= CGM_WORK）')
    ap.add_argument('--dry', action='store_true', help='只报告，不落盘')
    a = ap.parse_args()

    fl = os.path.join(a.golden, 'cores', 'filelist.xml')
    if not os.path.isfile(fl):
        print('FATAL 找不到 %s' % fl)
        return 1
    with open(fl, encoding='utf-8', errors='replace') as f:
        names = re.findall(r'name="([^"]+)"', f.read())
    if not names:
        print('FATAL %s 里没有 name=' % fl)
        return 1

    dirs = {}
    made = 0
    for n in names:
        rel = n.replace('\\', '/')
        d = os.path.dirname(rel)
        if not d:
            print('FATAL 条目没有目录前缀（dir_serial_list 需要 NNN/ 形态）: %r' % n)
            return 1
        dirs[d] = dirs.get(d, 0) + 1
        if a.dry:
            continue
        p = os.path.join(a.work, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if not os.path.exists(p):
            with open(p, 'wb') as fh:
                fh.write(EOCD)
            made += 1

    print('   [GAMEDIRS] 目录 %d 个 / 条目 %d 个；新建占位文件 %d 个（各 22 B 空 ZIP）'
          % (len(dirs), len(names), made))
    for d, c in sorted(dirs.items()):
        print('   [GAMEDIRS]   %s/ : %d 项' % (d, c))

    if a.dry:
        return 0
    # 自证：readdir 必须能看到这些目录与文件（否则整块静默无效）
    bad = [d for d in dirs if not os.path.isdir(os.path.join(a.work, d))]
    if bad:
        print('FATAL 目录未被创建: %s' % bad)
        return 1
    seen = sum(len(os.listdir(os.path.join(a.work, d))) for d in dirs)
    if seen < len(names):
        print('FATAL readdir 只看到 %d 个条目（期望 %d）' % (seen, len(names)))
        return 1
    print('   [GAMEDIRS] 自证：readdir 共看到 %d 个条目 ✓' % seen)
    return 0


if __name__ == '__main__':
    sys.exit(main())
