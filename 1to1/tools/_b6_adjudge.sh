#!/bin/sh
# B6 候选 A/B 最小裁决：单侧跑原厂 factory + zig三桩 + zig shim，抓 dumb buffer 实体序列
# 关键洞察：driver.so（闭源）是同一个，dumb buffer 建立序列由它决定，与主程序无关
#          ⇒ 只需 factory 单侧，无需重建 ELF。
set -u
cd /workspace/1to1 || exit 9

L=/tmp/b6_adjudge.log
{ echo "=== B6 裁决 $(date -u) ==="; } > $L

# ---- 1) 环境铺设（参照 cnb_devqemu.sh / cnb_ladder.sh）----
echo '--- 建 /arm-root-device ---' >> $L
rm -rf /arm-root-device; mkdir -p /arm-root-device
cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>$L
rm -f /arm-root-device/MANIFEST.sha256
[ -e /arm-root-device/lib/ld-linux-armhf.so.3 ] || ln -sf ld-2.29.so /arm-root-device/lib/ld-linux-armhf.so.3
ls -l /arm-root-device/lib/ld-linux-armhf.so.3 >> $L 2>&1

echo '--- 建 /sdcard/cubegm ---' >> $L
mkdir -p /sdcard/cubegm; cp -a golden/sdcard_min/. /sdcard/cubegm/ 2>>$L || true

echo '--- 设备节点 ---' >> $L
[ -e /dev/mem ] || { : > /dev/mem 2>/dev/null && chmod 666 /dev/mem 2>/dev/null; } || true
mkdir -p /dev/dri 2>/dev/null || true
for i in 0 1; do [ -e /dev/dri/card$i ] || : > /dev/dri/card$i 2>/dev/null || true; done
ls -l /dev/mem /dev/dri/card0 >> $L 2>&1 || true

# ---- 2) zig 构建三桩 + shim（钉 2.29，宿主 GCC 会引入 GLIBC_2.38 不可用）----
ZIG=$(python3 -c 'import os,ziglang;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)

echo '--- zig 建桩 ---' >> $L
CC_ARM="$ZIG cc" sh tools/build_libkms_stub.sh   report/stublib      >>$L 2>&1 || echo '  kms fail' >> $L
CC_ARM="$ZIG cc" sh tools/build_libdrm_stub.sh   report/drmstublib   >>$L 2>&1 || echo '  drm fail' >> $L
CC_ARM="$ZIG cc" sh tools/build_libasound_stub.sh report/alsastublib >>$L 2>&1 || echo '  alsa fail' >> $L
CC="$ZIG cc" sh tools/build_guest_shim.sh report/guest_shim.so       >>$L 2>&1 || echo '  shim fail' >> $L
ls -la report/stublib report/drmstublib report/alsastublib report/guest_shim.so >> $L 2>&1

echo '--- 桩自证 ---' >> $L
echo "  drm 未定义=$(arm-linux-gnueabihf-nm -D report/drmstublib/libdrm.so.2 2>/dev/null | grep -c ' U ' || echo 0)" >> $L
echo "  drm dumb#=$(grep -a -c -F 'dumb#' report/drmstublib/libdrm.so.2 2>/dev/null)" >> $L
echo "  shim 最高GLIBC=$(arm-linux-gnueabihf-objdump -T report/guest_shim.so 2>/dev/null | grep -oE 'GLIBC_[0-9.]+' | sort -t_ -k2 -V | tail -1)" >> $L

# ---- 3) 核心裁决：带三桩+shim 跑 factory，抓 dumb 实体序列 ----
# LD_LIBRARY_PATH 顺序：alsa 最前，drm 次之，再设备真库（libkms 用真库即可，driver.so 无 kms_* 符号）
LIBPATH="/workspace/1to1/report/alsastublib:/workspace/1to1/report/drmstublib:/arm-root-device/usr/lib:/arm-root-device/lib"
Q=/usr/bin/qemu-arm-static

echo '--- 铺 factory 到工作目录 ---' >> $L
cp -f golden/factory.rkgame.bin /sdcard/cubegm/rkgame
chmod +x /sdcard/cubegm/rkgame
cp -f report/guest_shim.so /sdcard/cubegm/guest_shim.so

echo '--- 跑裁决（30s 超时）---' >> $L
( cd /sdcard/cubegm && timeout 40 $Q -L /arm-root-device -cpu cortex-a7 -strace \
    -E LD_PRELOAD=/sdcard/cubegm/guest_shim.so \
    -E LD_LIBRARY_PATH="$LIBPATH" \
    -E CGM_SHIM_VERBOSE=0 \
    -E HOME=/tmp -E TMPDIR=/tmp -E LC_ALL=C -E LANG=C \
    /sdcard/cubegm/rkgame > /tmp/b6_stdout.txt 2> /tmp/b6_stderr.txt )
echo "  qemu exit=$?" >> $L

echo '--- [drmstub] dumb# 实体序列（候选 A/B 裁决核心）---' >> $L
grep -a 'dumb#' /tmp/b6_stderr.txt >> $L 2>&1 || echo '  (无 dumb# 行)' >> $L

echo '--- [drmstub] MAP_DUMB handle→offset 对照 ---' >> $L
grep -a 'MAP_DUMB' /tmp/b6_stderr.txt >> $L 2>&1 || echo '  (无 MAP_DUMB 行)' >> $L

echo '--- [drmstub] AddFB2 / fb2_buf / frame# / SUMMARY ---' >> $L
grep -aE 'AddFB2|fb2_buf=|frame#|SUMMARY' /tmp/b6_stderr.txt >> $L 2>&1 || echo '  (无 fb 行)' >> $L

echo '--- [drmstub] R189 呈现点全入参（plane/pageflip 几何 = 画面来源线索）---' >> $L
grep -aE 'SetPlane_geom|PageFlip_geom' /tmp/b6_stderr.txt >> $L 2>&1 || echo '  (无 geom 行)' >> $L

echo '--- [shim] fb_lookup HIT（分支1 是否拦到 dumb 映射）---' >> $L
grep -a 'fb_lookup HIT' /tmp/b6_stderr.txt >> $L 2>&1 || echo '  (无 HIT 行)' >> $L

echo '--- [shim] ANON_WR（R189：driver 画布匿名 mmap 是否走本 shim）---' >> $L
grep -a 'ANON_WR' /tmp/b6_stderr.txt >> $L 2>&1 || echo '  (无 ANON_WR 行 ⇒ driver 画布不经本 shim)' >> $L

echo '--- [shim] 画布登记候选（canvas_count/latest 若桩有查询）---' >> $L
grep -aE 'canvas|CANVAS' /tmp/b6_stderr.txt >> $L 2>&1 || echo '  (无 canvas 行)' >> $L

echo '--- [shim] mmap2_FAIL / 真崩溃 ---' >> $L
grep -aE 'mmap2_FAIL|真崩溃|SIGSEGV' /tmp/b6_stderr.txt | head -20 >> $L 2>&1 || true

echo '--- stderr 前 25 行（执行流判断）---' >> $L
head -25 /tmp/b6_stderr.txt >> $L 2>&1

echo '--- stderr 行数 ---' >> $L
wc -l /tmp/b6_stderr.txt >> $L 2>&1

echo 'REMOTE-DONE' >> $L
cat $L