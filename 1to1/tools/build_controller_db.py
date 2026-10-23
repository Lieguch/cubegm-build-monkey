#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_controller_db.py —— 把 RetroArch 官方**全量** udev autoconfig 合成一张设备端可读的表

## 为什么要这个（用户约束，2026-10-22）
「手柄驱动必须全量内置、自动匹配；**绝对不能**新手柄每次新加文件」。
RetroArch 官方仓库 `libretro/retroarch-joypad-autoconfig` 的 `udev/` 目录就是全量表
（官方打包 `https://buildbot.libretro.com/assets/frontend/autoconfig.zip`，
实测 1116 条目、其中 `udev/*.cfg` **439** 个）。
本工具把它们合成**一个文本文件** `cubegm/controller_db.txt`：
  · 设备端只读一个文件，不需要解 zip、不需要任何手工步骤；
  · 新增手柄由官方上游更新后**重新生成本文件**即可（脚本一条命令）。

## 上游格式（已核实 docs.libretro.com/guides/controller-autoconfiguration）
```
input_device      = "Microsoft X-Box One pad"
input_driver      = "udev"
input_vendor_id   = 1118          # ★ 十进制
input_product_id  = 721           # ★ 十进制
input_b_btn       = "0"           # ★ 该设备的第 N 个按键（序号，不是 keycode）
input_up_btn      = "h0up"        # 方向键走 hat：h0up/h0down/h0left/h0right
input_l2_axis     = "+2"          # 轴：+N / -N
```

## 输出格式（设备端 C 解析，见 src/upgrade/evdev_gamepad.c）
每行一个 profile：
```
<vid:4hex|----> <pid:4hex|----> <name 用 %20 编码的空格> k=v k=v ...
```
- vid/pid 缺失时写 `----`（这类只能按 name 匹配）
- 键名沿用上游短名：`b a y x l r l2 r2 l3 r3 sel st up dn lf rt`（+轴 `lx+ lx- ly+ ly- rx+ rx- ry-`）
- `%20` 编码避免名字里的空格破坏按空格切分；C 侧只需把 `%20` 还原成空格

## 用法
  python tools/build_controller_db.py --zip build/_exp/pads/autoconfig.zip --out golden/sdcard_min/controller_db.txt
  python tools/build_controller_db.py --zip <zip> --out <txt> --stats
"""
import argparse
import os
import sys
import zipfile

# 上游键名 → 我们 db 里的短名（只收与 rkgame 位域有关的；label 类一律丢弃）
KEYMAP = {
    'input_b_btn': 'b', 'input_a_btn': 'a', 'input_y_btn': 'y', 'input_x_btn': 'x',
    'input_l_btn': 'l', 'input_r_btn': 'r', 'input_l2_btn': 'l2', 'input_r2_btn': 'r2',
    'input_l3_btn': 'l3', 'input_r3_btn': 'r3',
    'input_select_btn': 'sel', 'input_start_btn': 'st',
    'input_up_btn': 'up', 'input_down_btn': 'dn', 'input_left_btn': 'lf', 'input_right_btn': 'rt',
    'input_up_axis': 'up_ax', 'input_down_axis': 'dn_ax', 'input_left_axis': 'lf_ax', 'input_right_axis': 'rt_ax',
    'input_l_x_plus_axis': 'lx+', 'input_l_x_minus_axis': 'lx-',
    'input_l_y_plus_axis': 'ly+', 'input_l_y_minus_axis': 'ly-',
    'input_r_x_plus_axis': 'rx+', 'input_r_x_minus_axis': 'rx-',
    'input_r_y_plus_axis': 'ry+', 'input_r_y_minus_axis': 'ry-',
    'input_l2_axis': 'l2_ax', 'input_r2_axis': 'r2_ax',
}


def parse_cfg(text):
    d = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        k = k.strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        d[k] = v
    return d


def enc_name(s):
    return s.replace(' ', '%20').replace('\t', '%09')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--zip', required=True, help='RetroArch autoconfig.zip')
    ap.add_argument('--out', required=True, help='输出 controller_db.txt')
    ap.add_argument('--stats', action='store_true')
    a = ap.parse_args()

    if not os.path.exists(a.zip):
        print('!! 缺输入 zip: %s' % a.zip, file=sys.stderr)
        return 11

    z = zipfile.ZipFile(a.zip)
    cfgs = [n for n in z.namelist() if n.startswith('udev/') and n.endswith('.cfg')]
    cfgs.sort()

    lines = []
    n_vidpid = n_nameonly = n_skip = 0
    for n in cfgs:
        d = parse_cfg(z.read(n).decode('utf-8', 'replace'))
        name = d.get('input_device', '').strip()
        vid = d.get('input_vendor_id', '').strip()
        pid = d.get('input_product_id', '').strip()
        try:
            vidh = '%04x' % int(vid, 10) if vid else '----'
            pidh = '%04x' % int(pid, 10) if pid else '----'
        except ValueError:
            vidh = pidh = '----'
        if not name and vidh == '----':
            n_skip += 1
            continue
        toks = ['%s %s %s' % (vidh, pidh, enc_name(name) or '-')]
        for up, short in KEYMAP.items():
            if up in d and d[up] != '':
                toks.append('%s=%s' % (short, d[up]))
        if len(toks) == 1:            # 只有名字、没有任何映射：无意义
            n_skip += 1
            continue
        if vidh != '----' and pidh != '----':
            n_vidpid += 1
        else:
            n_nameonly += 1
        lines.append(' '.join(toks))

    hdr = [
        '# controller_db.txt —— RetroArch 官方 udev autoconfig 全量合并表（自动生成，勿手改）',
        '# 来源: libretro/retroarch-joypad-autoconfig  →  buildbot.libretro.com/assets/frontend/autoconfig.zip',
        '# 生成: tools/build_controller_db.py',
        '# 记录数: %d （有 vid/pid: %d ；仅名字: %d ；跳过: %d）' % (len(lines), n_vidpid, n_nameonly, n_skip),
        '# 格式: <vid:4hex|----> <pid:4hex|----> <name(%20 编码)> key=value ...',
    ]
    out = '\n'.join(hdr + lines) + '\n'
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    tmp = a.out + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(out)
    os.replace(tmp, a.out)

    if a.stats:
        print('udev cfg 总数 = %d' % len(cfgs))
        print('写入记录     = %d' % len(lines))
        print('  有 vid/pid = %d' % n_vidpid)
        print('  仅名字     = %d' % n_nameonly)
        print('  跳过       = %d' % n_skip)
        print('输出 %s  (%d B)' % (a.out, len(out.encode())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
