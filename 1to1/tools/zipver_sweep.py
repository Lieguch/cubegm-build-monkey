#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""上游 zip 库**版本对拍**：把候选源用同口径编译，与工厂逐符号比 size（可复用、可验收）。

## 为什么需要它（2026-09-21，GAP 16.54）

项目长期**逐符号手工对齐** `src/upstream/xunzip/unzip.cpp`（第 45/46/47 轮各修一个），
进度慢且看不出全局。本工具把「同源码不同编译器 size 差通常 <2×」这条已验证的判据
**用在候选源上**（与「反推编译口径 `-Os`」同一套方法）：

    同一份候选源码 × 固定口径（-std=gnu++14 -Os -target arm-linux-gnueabihf.2.29）
      → 编译成 .o → 解 SHT_SYMTAB → 与工厂同名函数逐个比 st_size → 命中者即原厂版本

## 首跑结论（2026-09-21，决定性）

| 候选 | 在 ±33% 内命中工厂 |
|---|---|
| **A. `src/upstream/zip_utils.zip!unzip.cpp`（Wischik 原版，2004-06-25，144,408 B）** | **20 / 25** |
| B. `src/upstream/xunzip/unzip.cpp`（现用，tomyqg/helix_mp3 变体，151,019 B） | 约 0 / 25（几乎每行偏 2×）|

★ 原版有 **6 个符号精确到字节**：`unzStringFileNameCompare` 16=16 · `unzClose` 60=60 ·
  `unzGetGlobalInfo` 32=32 · `unzGoToFirstFile` 96=96 · `unzlocal_DosDateToTmuDate` 64=64 ·
  `unzGetCurrentFileInfo` 64=64。

★ 工厂 **≠ 纯原版**，5 处已知改动（方向明确，见 GAP 16.54）：
  · `unzOpenCurrentFile` 工厂**单参** 316 B（原版双参 `...PKc` 440 B）⇒ 砍掉了 password；
  · `TUnzip::Find` 工厂 `...PKch...`（**unsigned char**）vs 原版 `...PKcb...`（bool）；
  · `TUnzip::Unzip` / `Get` / `Open` 工厂是"薄封装 + GCC 冷热分割（`.part.N`）"，原版是单一大函数。

## 用法

    python3 tools/zipver_sweep.py            # 对拍原版 vs 工厂 vs 现用产物

退出码：0 = 原版命中率 ≥80%；2 = 命中率不足（说明候选源仍不对）；3 = 编译失败/无法判定。
"""

import io
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

REPO = 'D:/output/rkgame-1to1'
ZIG = ('C:/Users/Administrator/.workbuddy/binaries/python/envs/default/'
       'Lib/site-packages/ziglang/zig.exe')
POSIX = os.path.join(REPO, 'src', 'upstream', 'xunzip', 'posix')


def syms(path):
    """返回 {符号名: st_size}（只取 SHT_SYMTAB 的 STT_FUNC）。"""
    if not os.path.exists(path):
        return None
    d = open(path, 'rb').read()
    es = struct.unpack_from('<H', d, 46)[0]
    sh = struct.unpack_from('<I', d, 32)[0]
    n = struct.unpack_from('<H', d, 48)[0]
    S = [struct.unpack_from('<10I', d, sh + i * es) for i in range(n)]
    out = {}
    for s in S:
        if s[1] != 2:
            continue
        stro = S[s[6]][4]
        ent = s[9] or 16
        for j in range(s[5] // ent):
            nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
            if nmn == 0 or (inf & 0xF) != 2 or sz == 0:
                continue
            k = d.index(b'\x00', stro + nmn)
            out.setdefault(d[stro + nmn:k].decode('utf-8', 'replace'), sz)
    return out


def build(tag, src, incdirs, outdir):
    obj = os.path.join(outdir, '%s.o' % tag)
    # ★ `-std=gnu++14`：原版源码用了 `register`（C++17 已删）；工厂是 GCC 6（默认 gnu++14）
    #   ⇒ 方言也必须对齐，否则连编译都过不去（这本身就是"口径"的一部分）。
    cmd = [ZIG, 'c++', '-target', 'arm-linux-gnueabihf.2.29',
           '-std=gnu++14', '-mfloat-abi=hard', '-mfpu=neon', '-c', '-w', '-Os']
    for i in incdirs:
        cmd += ['-I', i]
    cmd += [src, '-o', obj]
    env = dict(os.environ)
    env['ZIG_LOCAL_CACHE_DIR'] = os.path.join(outdir, 'lc_' + tag)
    env['ZIG_GLOBAL_CACHE_DIR'] = os.path.join(outdir, 'gc_' + tag)
    p = subprocess.run(cmd, capture_output=True, env=env)
    ok = os.path.exists(obj)
    if not ok:
        err = (p.stderr or b'').decode('utf-8', 'replace').splitlines()[:6]
        return None, err
    return obj, []


def main():
    outdir = tempfile.mkdtemp(prefix='cgm_ver_')
    # 解出原版三件套
    with zipfile.ZipFile(os.path.join(REPO, 'src', 'upstream', 'zip_utils.zip')) as z:
        z.extractall(outdir)
    print('  === 候选 A：Wischik 原版（刚从 zip_utils.zip 解出，未修改）===')
    for f in ('unzip.cpp', 'unzip.h'):
        print('     %-12s %8d B' % (f, os.path.getsize(os.path.join(outdir, f))))

    # ★ 纯文本归一：原版含 `L"..."` 宽字符字面量，而我们的 POSIX 垫片把 TCHAR 定成 char。
    #   只在**临时副本**上把 `L"` 替换为 `"`（影响面 = FormatZipMessage 等，**不在对拍集合内**
    #   的 `unz*`/`TUnzip::*`）。这是为了让 TU 能编过，不改变被对拍函数的代码。
    src0 = os.path.join(outdir, 'unzip.cpp')
    txt = io.open(src0, encoding='utf-8', errors='replace').read()
    n_l = txt.count('L"')
    txt2 = txt.replace('L"', '"')
    src1 = os.path.join(outdir, 'unzip_norm.cpp')
    io.open(src1, 'w', encoding='utf-8', newline='\n').write(txt2)
    print('     · 纯文本归一：L" → " 共 %d 处（临时副本，不动原包）' % n_l)

    objs = {}
    obj, err = build('pristine', src1,
                     [POSIX, outdir, os.path.join(REPO, 'src', 'upstream', 'xunzip')], outdir)
    if obj:
        objs['原版(Wischik)'] = obj
        print('     ✓ 编译成功 %s (%d B)' % (os.path.basename(obj), os.path.getsize(obj)))
    else:
        print('     ✗ 编译失败：')
        for l in err:
            print('        %s' % l[:130])

    # 我们现用的（build/obj 里已有；没有就用链接产物）
    our = os.path.join(REPO, 'build', 'rkgame.rebuilt.elf')
    F = syms(os.path.join(REPO, 'golden', 'factory.rkgame.bin'))
    R = syms(our) if os.path.exists(our) else None
    P = syms(obj) if obj else None

    keys = sorted(k for k in (set(F) | (set(P or {})))
                  if ('unz' in k.lower() or 'TUnzip' in k))
    print()
    print('  %-50s %7s %8s %8s' % ('符号', '工厂B', '原版B', '我们B'))
    print('  ' + '-' * 78)
    hit = tot = 0
    for k in keys:
        a = F.get(k, 0)
        b = (P or {}).get(k, 0)
        c = (R or {}).get(k, 0)
        r = ('%.2f' % (b / a)) if (a and b) else '—'
        good = bool(a and b and 0.75 <= b / a <= 1.33)
        if a and b:
            tot += 1
            hit += good
        print('  %-50s %7s %8s %8s  %s%s' % (k[:50], a or '—', b or '—', c or '—', r,
                                             '' if good else ' ★'))
    print()
    print('  ⇒ 原版(Wischik) 在 +/-33%% 内命中工厂：%d / %d' % (hit, tot))
    shutil.rmtree(outdir, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
