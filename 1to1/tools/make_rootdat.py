#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_rootdat.py — 合成 `/sdcard/root.dat`（一个 ZIP，内含 `fileinfo.txt`）

背景（第 49 轮，逐条有机器码/源码证据）：
  · `mui_menu`（`src/proprietary/mui/FUN_00023204_mui_menu.c:63-74`）：
        if (DAT_003af2ac == NULL) {
            sprintf(buf, "%s/root.dat", root_path);      /* root.dat 是 ZIP 包 */
            hz = OpenZipU(buf, 0, 2);
            if (hz == 0 || FindZipItemA(hz, "fileinfo.txt", ...) != 0) {
                RARCH_LOG("find %s fail!\\n", buf);        /* 失败：DAT_003af2ac 保持 NULL */
            } else { DAT_003af2ac = malloc(...); UnzipItem(...); }
        }
        ...
        iVar2 = mui_do_file_list(iVar11, DAT_003af2ac);    /* NULL 传进去就在 +0xf0 崩 */
    ⇒ 沙箱缺 `/sdcard/root.dat` 时，两侧同形态崩在 mui_do_file_list+0xf0 的 `ldrb r0,[r0]`。

  · 内容格式的真值源 = `mui_do_file_list` 的解析循环（C 明码）：
        分隔符：','(0x2c) / ';'(0x3b) / '\\n'(10) / '\\r'(13)
        每项 → `libiconv`(GB2312→utf-8) → `mui_extract_basepath`（取 strrchr('/') 之前的部分）
             → `strtol(local_8c, NULL, 10)`        ← ★ basepath 被当**十进制数**解析
       `mui_DisplayThumbnail` 随后 `sprintf(buf, "%s/%s/%s.dat", root_path, basepath, basepath)`
    ⇒ 每项必须形如 `NNN/<文件名>`（首段是数字目录名），否则 basepath 为空 ⇒ `/sdcard//.dat`（实测）。

  · 而 `golden/sdcard_min/cores/filelist.xml`（8654 B）的 `name="002/Targa (Europe) (Proto).zip"`
    正是这个形态 ⇒ 它就是 `fileinfo.txt` 的**可得真值源**。

用法：
    make_rootdat.py --mode filelist --golden <golden_dir> --out /sdcard/root.dat
    make_rootdat.py --mode fileinfo --golden <golden_dir> --out /sdcard/root.dat
"""
import argparse
import os
import re
import sys
import zipfile

ENTRY = 'fileinfo.txt'


def build_filelist(golden):
    """从 cores/filelist.xml 提取 name= 列表（真值源）。"""
    p = os.path.join(golden, 'cores', 'filelist.xml')
    with open(p, encoding='utf-8', errors='replace') as f:
        t = f.read()
    names = re.findall(r'name="([^"]+)"', t)
    return ','.join(names).encode('utf-8'), 'filelist.xml(%d 个 name=)' % len(names)


def build_fileinfo(golden):
    """旧口径：直接拿 golden 顶层 `fileinfo`（49 B = "0,0,...,0"）当 fileinfo.txt。

    ⚠ 已实测**不成立**：单项是 `0`，`mui_extract_basepath` 取不到 '/' ⇒ basepath 为空
      ⇒ 运行期日志 `open /sdcard//.dat fail`（反复出现）。保留只为"对照实验"，
      不要当作正确内容。
    """
    p = os.path.join(golden, 'fileinfo')
    with open(p, 'rb') as f:
        return f.read(), 'fileinfo(%d B, 已实测不成立)' % os.path.getsize(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=('filelist', 'fileinfo'), default='filelist')
    ap.add_argument('--golden', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    if a.mode == 'filelist':
        content, desc = build_filelist(a.golden)
    else:
        content, desc = build_fileinfo(a.golden)

    if not content:
        print('FATAL %s 提取到 0 字节内容（源=%s）' % (a.mode, desc))
        return 1

    d = os.path.dirname(os.path.abspath(a.out))
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with zipfile.ZipFile(a.out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(ENTRY, content)

    # 自洽校验：必须能被 zipfile 读回且条目名正确（防止造出坏包）
    with zipfile.ZipFile(a.out) as z:
        bad = z.testzip()
        got = z.read(ENTRY)
    if bad is not None or got != content:
        print('FATAL 合成后回读不一致（bad=%s）' % bad)
        return 1

    items = content.decode('utf-8', 'replace').split(',')
    print('   [ROOTDAT] mode=%s 源=%s' % (a.mode, desc))
    print('   [ROOTDAT] built %s（%d B, %d 项, 首项=%r）'
          % (a.out, os.path.getsize(a.out), len(items), items[0][:48]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
