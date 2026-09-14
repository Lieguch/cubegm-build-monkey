#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fetch_armhf_sysroot.py — 从 ports.ubuntu.com 直接取 armhf 运行库并解包成 sysroot。

★ 为什么不走 apt
----------------
`dpkg --add-architecture armhf` 之后，任何一次全局 `apt-get update` 都会让 apt 去
**所有** 已配置源（含 `security.ubuntu.com`）拉 `binary-armhf/Packages` —— 而 Ubuntu 的
security 源**根本没有 armhf**，于是 404、`apt-get update` 返回 100、`set -e` 直接中断。
CI 实测就是这么挂的：
    E: Failed to fetch https://security.ubuntu.com/ubuntu/dists/jammy/main/binary-armhf/Packages  404

⇒ 本脚本**不碰任何 apt 状态**：只读 ports.ubuntu.com 的 Packages 索引，解析出 .deb 的
   Filename，再逐个下载 + `dpkg-deb -x` 解包。可重复、可审计、与 runner 的 apt 配置无关。

用法:
  python3 tools/fetch_armhf_sysroot.py <sysroot> [suite] [pkg1,pkg2,...]
默认包集 = 覆盖 重建产物 + 工厂 rkgame 的全部 NEEDED（见下方 DEFAULT_PKGS 注释）。
"""
import gzip
import io
import os
import subprocess
import sys
import time
import urllib.request

BASE = 'http://ports.ubuntu.com/ubuntu-ports'
SUITE = 'jammy'
COMPONENTS = ('main', 'universe')

# 依赖来源（实测）：
#   重建产物 NEEDED : libc.so.6 libm.so.6
#   工厂 rkgame NEEDED: libz.so.1 libdl.so.2 libm libstdc++ libpthread libgcc_s libc
#   → libc6 提供 libc/libm/libdl/libpthread/ld-linux；其余逐个列名
DEFAULT_PKGS = ['libc6', 'libstdc++6', 'libgcc-s1', 'zlib1g',
                'libdrm2', 'libasound2', 'libudev1', 'libcrypt1', 'libselinux1', 'libpcre2-8-0']


def fetch(url, timeout=120, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'cgm-sysroot/1.0'})
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as e:
            last = e
            if i + 1 < retries:
                print('   [retry %d/%d] %s' % (i + 1, retries - 1, e))
                time.sleep(2 + 3 * i)
    raise last


def index_packages(suite=SUITE):
    """→ {pkg_name: (filename, version)} ；后出现的覆盖先出现的（universe 里的更新）。"""
    out = {}
    for comp in COMPONENTS:
        url = '%s/dists/%s/%s/binary-armhf/Packages.gz' % (BASE, suite, comp)
        try:
            raw = fetch(url)
        except Exception as e:
            print('   [warn] 索引取不到 %s: %s' % (url, e))
            continue
        txt = gzip.decompress(raw).decode('utf-8', 'replace')
        n = 0
        for stanza in txt.split('\n\n'):
            name = fn = ver = None
            for line in stanza.splitlines():
                if line.startswith('Package: '):
                    name = line[9:].strip()
                elif line.startswith('Filename: '):
                    fn = line[10:].strip()
                elif line.startswith('Version: '):
                    ver = line[9:].strip()
            if name and fn:
                out[name] = (fn, ver)
                n += 1
        print('   [ok]   %s/binary-armhf: %d 个包' % (comp, n))
    return out


def extract_deb(deb, dest):
    """解包 .deb → dest。优先 dpkg-deb；不可用时用纯 Python（ar + tar）兜底，
       这样在 Windows 开发机（无 dpkg）上也能完整预演 CI 步骤。"""
    try:
        r = subprocess.run(['dpkg-deb', '-x', deb, dest],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        if r.returncode == 0:
            return True, 'dpkg-deb'
    except FileNotFoundError:
        pass

    try:
        import tarfile
        import lzma
        import zlib
        data = open(deb, 'rb').read()
        if data[:8] != b'!<arch>\n':
            return False, 'not an ar archive'
        off, body, name = 8, None, None
        while off + 60 <= len(data):
            hdr = data[off:off + 60]
            mname = hdr[0:16].decode('ascii', 'replace').strip()
            msize = int(hdr[48:58].decode('ascii', 'replace').strip() or 0)
            chunk = data[off + 60:off + 60 + msize]
            if mname.startswith('data.tar'):
                name, body = mname, chunk
                break
            off += 60 + msize + (msize % 2)
        if body is None:
            return False, 'no data.tar member'
        if name.endswith('.xz'):
            raw = lzma.decompress(body)
        elif name.endswith('.gz'):
            raw = zlib.decompress(body, 16 + 15)
        elif name.endswith('.zst'):
            try:
                import zstandard
                # ★ 不能用 decompress()：Ubuntu 的 data.tar.zst 帧头**不含内容长度**，
                #   decompress() 会报 "could not determine content size in frame header"。
                #   必须走流式 reader。
                dctx = zstandard.ZstdDecompressor()
                raw = dctx.stream_reader(io.BytesIO(body)).read()
            except ImportError:
                # 无模块时退回 zstd CLI（Windows 开发机常见）
                p = subprocess.run(['zstd', '-d', '-c'], input=body,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if p.returncode != 0:
                    raise RuntimeError('zstd CLI 失败: %s' % p.stderr.decode()[:80])
                raw = p.stdout
        else:
            raw = body
        tar = tarfile.open(fileobj=io.BytesIO(raw))
        try:
            tar.extractall(dest, filter='tar')
        except TypeError:                      # 老 Python 无 filter 参数
            tar.extractall(dest)
        return True, 'python-ar'
    except Exception as e:
        return False, 'python-ar failed: %s' % e


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    index_only = '--index-only' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sysroot = args[0]
    suite = args[1] if len(args) > 1 else SUITE
    pkgs = args[2].split(',') if len(args) > 2 else DEFAULT_PKGS

    os.makedirs(sysroot, exist_ok=True)
    if os.path.exists(os.path.join(sysroot, 'usr/lib/arm-linux-gnueabihf/libc.so.6')) or \
       os.path.exists(os.path.join(sysroot, 'lib/arm-linux-gnueabihf/libc.so.6')):
        print('sysroot 已存在 libc6，跳过下载')
        return 0

    print('== 读取 ports.ubuntu.com 索引（%s）==' % suite)
    idx = index_packages(suite)
    if not idx:
        print('FATAL 索引为空')
        return 2

    if index_only:
        print()
        print('--- 索引自检（期望的包是否都能解析到 .deb）---')
        bad = 0
        for p in pkgs:
            hit = idx.get(p)
            if hit:
                print('   [ok]   %-16s %-22s %s' % (p, hit[1], hit[0]))
            else:
                print('   [miss] %s' % p)
                bad += 1
        print('索引条数 %d ；未解析 %d' % (len(idx), bad))
        return 0 if bad == 0 else 3

    tmp = os.path.join(sysroot, '.debs')
    os.makedirs(tmp, exist_ok=True)
    ok = 0
    for p in pkgs:
        hit = idx.get(p)
        if not hit:
            print('   [miss] %s 不在索引中' % p)
            continue
        fn, ver = hit
        url = '%s/%s' % (BASE, fn)
        deb = os.path.join(tmp, os.path.basename(fn))
        try:
            data = fetch(url, timeout=300)
        except Exception as e:
            print('   [fail] %s: %s' % (p, e))
            continue
        open(deb, 'wb').write(data)
        good, how = extract_deb(deb, sysroot)
        if good:
            ok += 1
            print('   [ok]   %-16s %-24s %8d B  (%s)' % (p, ver, len(data), how))
        else:
            print('   [fail] %s 解包失败: %s' % (p, how))
    print('解包成功 %d / %d' % (ok, len(pkgs)))
    print('sysroot = %s' % sysroot)
    return 0 if ok else 3


if __name__ == '__main__':
    sys.exit(main())
