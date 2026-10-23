#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_b6a_pixel_diff.py —— B6A 帧缓冲逐像素归因（R224）

用法（云上，抓完两侧 dump 之后）：
    python3 tools/_b6a_pixel_diff.py /tmp/frame_factory.raw /tmp/frame_rebuild.raw

前置：用 CGM_ABI_DUMP=<path> 跑 factory / rebuild 两侧，各得一份 1280x720 RGB565
      （pitch=2560，1,843,200 B）首帧原文。

输出（全部机器可读，结论必须由这些数字支撑，禁止口头断言）：
  1. 差异像素数 / 占比 / bbox
  2. 16 条带分区哈希（对齐 abi_probe 的 bands 输出，可交叉核对）
  3. 差异块的粗定位（ASCII 缩略图）
  4. 平移匹配（排除"整体偏移"）
  5. 同形状判定（93%+ 相同 = 局部块差异，而非全图不同）
  6. 颜色映射集中度（排除"固定转换表错误"）

判据口径：
  · 主体相同率 >= 90% 且差异成块  ⇒ 局部 UI 元素渲染差异（不是全图毁坏）
  · 平移匹配显著优于 0 偏移        ⇒ 布局/坐标偏移
  · 颜色映射集中度 >= 80%          ⇒ 转换表/调色板错误
"""
import sys
import collections

W, H, PITCH = 1280, 720, 2560


def px(buf, x, y):
    o = y * PITCH + x * 2
    return buf[o] | (buf[o + 1] << 8)


def lum(v):
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    return r * 8 + g * 4 + b * 8


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    F = open(sys.argv[1], "rb").read()
    R = open(sys.argv[2], "rb").read()
    expect = H * PITCH
    print("sizes: factory=%d rebuild=%d expect=%d %s"
          % (len(F), len(R), expect, "OK" if len(F) == len(R) == expect else "MISMATCH"))
    if len(F) != expect or len(R) != expect:
        print("尺寸不符：不是 1280x720 RGB565 pitch=2560 的帧")
        return 3

    # 1) 差异像素 + bbox
    nd = 0
    xmin, xmax, ymin, ymax = W, -1, H, -1
    for y in range(H):
        base = y * PITCH
        for x in range(W):
            o = base + x * 2
            if F[o] != R[o] or F[o + 1] != R[o + 1]:
                nd += 1
                if x < xmin: xmin = x
                if x > xmax: xmax = x
                if y < ymin: ymin = y
                if y > ymax: ymax = y
    print("\n[1] 差异像素 %d / %d = %.4f%%" % (nd, W * H, nd * 100.0 / (W * H)))
    print("    bbox x=[%d,%d] y=[%d,%d]" % (xmin, xmax, ymin, ymax))

    # 2) 16 条带哈希（与 abi_probe bands 同算法同分带）
    print("\n[2] 16 条带 FNV-1a（对照 abi_probe bands#1 输出）")
    per = (H * PITCH) // 16
    for i in range(16):
        hf = 2166136261
        hr = 2166136261
        seg_f = F[i * per:(i + 1) * per]
        seg_r = R[i * per:(i + 1) * per]
        for v in seg_f:
            hf = ((hf ^ v) * 16777619) & 0xFFFFFFFF
        for v in seg_r:
            hr = ((hr ^ v) * 16777619) & 0xFFFFFFFF
        print("    b%-2d F=%08x R=%08x %s" % (i, hf, hr, "SAME" if hf == hr else "DIFF"))

    # 3) ASCII 差异缩略
    print("\n[3] 差异缩略图（# = 该格 >=30% 像素不同, + = 有差异, . = 无）")
    if xmax >= 0:
        sx = max(1.0, (xmax - xmin + 1) / 76.0)
        sy = max(1.0, (ymax - ymin + 1) / 32.0)
        for gy in range(32):
            y0 = ymin + int(gy * sy)
            y1 = min(ymin + int((gy + 1) * sy), ymax + 1)
            line = ""
            for gx in range(76):
                x0 = xmin + int(gx * sx)
                x1 = min(xmin + int((gx + 1) * sx), xmax + 1)
                d = 0
                t = 0
                for y in range(y0, y1):
                    base = y * PITCH
                    for x in range(x0, x1):
                        o = base + x * 2
                        t += 1
                        if F[o] != R[o] or F[o + 1] != R[o + 1]:
                            d += 1
                line += "#" if t and d * 100 >= t * 30 else ("+" if d else ".")
            print("    " + line)

    # 4) 平移匹配（排除整体偏移）
    print("\n[4] 平移匹配（中心区域 x=150..600 y=200..520，步长 6）")
    best = (0.0, 0, 0)
    for dy in range(-16, 17, 2):
        for dx in range(-16, 17, 2):
            same = 0
            tot = 0
            for y in range(200, 520, 6):
                for x in range(150, 600, 6):
                    yy, xx = y + dy, x + dx
                    if yy < 0 or yy >= H:
                        continue
                    tot += 1
                    if px(F, x, y) == px(R, xx, yy):
                        same += 1
            if tot and same * 100.0 / tot > best[0]:
                best = (same * 100.0 / tot, dx, dy)
    print("    最佳 %.2f%% @ dx=%d dy=%d（dx=dy=0 即无整体偏移）" % best)

    # 5) 主体相同率
    same0 = 0
    tot0 = 0
    for y in range(200, 520, 2):
        for x in range(150, 600, 2):
            tot0 += 1
            if px(F, x, y) == px(R, x, y):
                same0 += 1
    print("\n[5] 中心区逐像素相同率 %.2f%%（>=90%% ⇒ 局部块差异，非全图毁坏）"
          % (same0 * 100.0 / tot0))

    # 6) 颜色映射集中度（排除固定转换表错误）
    print("\n[6] 颜色映射集中度（同一 factory 值是否固定映射到同一 rebuild 值）")
    m = collections.defaultdict(collections.Counter)
    for y in range(140, 600, 2):
        for x in range(105, 680, 2):
            a = px(F, x, y)
            b = px(R, x, y)
            if a != b:
                m[a][b] += 1
    conc = 0
    tot = 0
    for a, c in m.items():
        t = sum(c.values())
        if t >= 20:
            tot += 1
            if c.most_common(1)[0][1] * 100.0 / t >= 80:
                conc += 1
    print("    不同 factory 值 %d 个；高频(>=20)中映射>=80%%集中: %d/%d"
          % (len(m), conc, tot))
    print("    （集中度高 ⇒ 转换表/调色板错误；低 ⇒ 位置/内容不同）")
    print("\n    最高频 8 组映射：")
    top = sorted(m.items(), key=lambda kv: -sum(kv[1].values()))[:8]
    for a, c in top:
        items = ", ".join("0x%04x(%d)" % (v, k) for v, k in c.most_common(3))
        print("      0x%04x (n=%5d) -> %s" % (a, sum(c.values()), items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
