#!/bin/sh
# 一次性远程取证：GCC 14.2.0 下诊断字符串是否真消失（内联立即数 vs 真消除）
set -u
cd /workspace/1to1 || exit 9

echo "===== [1] -O0 完整编译报错 ====="
arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -O0 -w \
  -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -Wl,-soname,libdrm.so.2 tools/guest_shim/drm_stub.c -o /tmp/drm_O0.so 2>&1 | head -40
echo "rc=$? (rc 非0 即报错)"

echo "===== [2] 各优化级别构建到 /tmp ====="
for O in O1 Os O2 O3; do
  arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -$O -w \
    -fno-unwind-tables -fno-asynchronous-unwind-tables \
    -Wl,-soname,libdrm.so.2 tools/guest_shim/drm_stub.c -o /tmp/drm_$O.so 2>&1 | head -5
  echo "-- $O rc=$? size=$(wc -c < /tmp/drm_$O.so 2>/dev/null)"
done

echo "===== [3] strings 搜关键标签（GCC -O2）====="
for tag in 'dumb#' '[drmstub]' 'frame#' 'SUMMARY' 'fb2_buf=' 'MAP_DUMB' 'AddFB2_h' 'mmap2_FAIL'; do
  n=$(strings /tmp/drm_O2.so 2>/dev/null | grep -F "$tag" | wc -l)
  echo "  tag='$tag'  strings命中=$n"
done

echo "===== [4] 反汇编 dumb_entity_note（看字符串是否立即数内联）====="
arm-linux-gnueabihf-objdump -d /tmp/drm_O2.so 2>/dev/null \
  | awk '/<dumb_entity_note>:/{f=1} f{print} f&&/^$/{c++; if(c>1)exit}' | head -80

echo "===== [5] .rodata 原始 dump（前 400 字节）====="
arm-linux-gnueabihf-objdump -s -j .rodata /tmp/drm_O2.so 2>/dev/null | head -40

echo "===== [6] 未定义符号数（O2 自洽性）====="
arm-linux-gnueabihf-nm -D /tmp/drm_O2.so 2>/dev/null | grep ' U ' | wc -l

echo "===== [7] 云上被测产物是否就位 ====="
ls -la build/rkgame.rebuilt.elf golden/factory.rkgame.bin 2>&1 | head -10
ls -la golden/ 2>/dev/null | head -20

echo "===== [8] 桩导出符号覆盖（O2 产物 vs NEED）====="
python3 tools/driver_stub_coverage.py --print-need drm 2>/dev/null > /tmp/need.txt
echo "  NEED 清单行数=$(wc -l < /tmp/need.txt 2>/dev/null)"
for s in $(cat /tmp/need.txt 2>/dev/null); do
  arm-linux-gnueabihf-nm -D --defined-only /tmp/drm_O2.so 2>/dev/null | awk '{print $NF}' | grep -qx "$s" || echo "  缺: $s"
done
echo "  导出覆盖检查完"
echo "DIAG-DONE"