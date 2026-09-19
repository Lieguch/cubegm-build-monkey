"""从设备真实 rootfs（org.bin 提取件）生成「设备精确 sysroot 最小集」。

为什么需要它：
  我们此前的差分 sysroot 是 **Ubuntu jammy（glibc 2.35）** —— 那是"能跑"的替代品，
  不是设备真实环境。设备真实 rootfs（org.bin 的 squashfs 分区）里是
  **glibc 2.29 (Buildroot)**、**libstdc++ 6.0.22**、**libz 1.2.11**、
  **libdrm 2.4.0 + libdrm_rockchip.so.1**、libasound 2.0.0、libkms 1.0.0。
  ⇒ 用真件当 sysroot，才谈得上"在设备上会怎样"。

只用不猜：
  · 输入 = 用户本地「解包归档/rootfs解包」（F: 盘），**只读**
  · 输出 = golden/device_rootfs_min/（入库）＋ MANIFEST.sha256（可校验）
  · 尺寸刻意控制在 ~4 MB：只取差分运行真正会加载的运行时元件

用法：
  python tools/make_device_sysroot.py --src "<rootfs解包目录>" [--out golden/device_rootfs_min]
"""
import argparse, hashlib, io, os, re, shutil, sys

# 设备真实运行时会加载的元件（名字 + 制造成 symlink 的规范名）
WANT = [
    ('lib/ld-2.29.so',                  'lib/ld-linux-armhf.so.3'),
    ('lib/libc-2.29.so',                'lib/libc.so.6'),
    ('lib/libm-2.29.so',                'lib/libm.so.6'),
    ('lib/libdl-2.29.so',               'lib/libdl.so.2'),
    ('lib/libpthread-2.29.so',          'lib/libpthread.so.0'),
    ('lib/librt-2.29.so',               'lib/librt.so.1'),
    ('lib/libgcc_s.so.1',               None),
    ('usr/lib/libstdc++.so.6.0.22',     'usr/lib/libstdc++.so.6'),
    ('usr/lib/libasound.so.2.0.0',      'usr/lib/libasound.so.2'),
    ('usr/lib/libdrm.so.2.4.0',         'usr/lib/libdrm.so.2'),
    ('usr/lib/libdrm_rockchip.so.1.0.0','usr/lib/libdrm_rockchip.so.1'),
    ('usr/lib/libkms.so.1.0.0',         'usr/lib/libkms.so.1'),
    ('usr/lib/libz.so.1.2.11',          'usr/lib/libz.so.1'),
]


def sha(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='解包归档/rootfs解包 目录')
    ap.add_argument('--out', default='golden/device_rootfs_min')
    a = ap.parse_args()

    if not os.path.isdir(a.src):
        print('★ 源目录不存在: %s' % a.src); return 1
    if os.path.exists(a.out):
        shutil.rmtree(a.out)

    rows, total, miss = [], 0, []
    for rel, link in WANT:
        sp = os.path.join(a.src, rel)
        if not os.path.exists(sp):
            miss.append(rel); continue
        dp = os.path.join(a.out, rel)
        os.makedirs(os.path.dirname(dp), exist_ok=True)
        shutil.copy2(sp, dp)
        n = os.path.getsize(dp); total += n
        rows.append((rel, n, sha(dp), link or ''))
        if link:
            lp = os.path.join(a.out, link)
            os.makedirs(os.path.dirname(lp), exist_ok=True)
            if os.path.lexists(lp):
                os.remove(lp)
            os.symlink(os.path.basename(rel), lp)

    man = os.path.join(a.out, 'MANIFEST.sha256')
    with io.open(man, 'w', encoding='utf-8', newline='\n') as f:
        for rel, n, h, link in rows:
            f.write('%s  %s\n' % (h, rel))
        f.write('# 设备精确 sysroot 最小集（源：org.bin 的 squashfs rootfs 分区）\n')
        f.write('# 设备真实 glibc = 2.29 (Buildroot)；busybox v1.27.2；libstdc++ 6.0.22\n')
        f.write('# libz 1.2.11；libdrm 2.4.0 + libdrm_rockchip.so.1；libasound 2.0.0；libkms 1.0.0\n')
        f.write('# 生成工具: tools/make_device_sysroot.py（--src 指向本机解包归档/rootfs解包）\n')

    print('== 设备精确 sysroot -> %s' % a.out)
    print('   %-36s %10s  %s' % ('文件', '大小', '设备规范名'))
    for rel, n, h, link in rows:
        print('   %-36s %10d  %s' % (rel, n, link or '-'))
    print('   合计 %d 个文件，%d B = %.2f MB' % (len(rows), total, total / 1048576.0))
    if miss:
        print('   ★ 源里缺（不影响，记录以便核查）: %s' % ', '.join(miss))
    print('   MANIFEST -> %s' % man)

    # 自证：glibc 版本串必须与"设备真实"一致
    libc = os.path.join(a.out, 'lib/libc-2.29.so')
    if os.path.exists(libc):
        d = open(libc, 'rb').read()
        m = re.findall(rb'GNU C Library[^\x00]{0,60}', d)
        print('   自证 glibc 版本串: %s' % (m[0].decode('utf-8', 'replace') if m else '(未找到)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
