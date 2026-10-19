#!/bin/sh
# GCC 链 divmod 未定义符号根因取证：谁引用 + 最小复现 + march 影响
set -u
cd /workspace/1to1 || exit 9

echo "===== [1] 谁引用 __aeabi_uidivmod / __aeabi_idivmod（objdump -r 重定位 + 反汇编 bl 目标）====="
arm-linux-gnueabihf-objdump -d report/drmstublib/libdrm.so.2 2>/dev/null \
  | grep -nE 'bl.*(uidivmod|idivmod|<.*divmod)' | head -30

echo "----- 动态重定位表里这两个符号的引用地址 -----"
arm-linux-gnueabihf-objdump -R report/drmstublib/libdrm.so.2 2>/dev/null \
  | grep -iE 'divmod' | head -20

echo "===== [2] 最小复现：v%10;v/10 在 GCC arm 默认 vs -march=armv7-a ====="
cat > /tmp/t.c <<'EOF'
typedef unsigned int u32;
u32 f(u32 v){ char nb[12]; int m=0; if(!v) nb[m++]='0';
  while(v){ nb[m]=(char)('0'+(v%10u)); v/=10u; m++; } return m; }
EOF
echo "--- 默认（无 -march）---"
arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -Oz -w -fno-unwind-tables -fno-asynchronous-unwind-tables /tmp/t.c -o /tmp/t_def.so 2>&1 | head -5
echo "  未定义:"; arm-linux-gnueabihf-nm -D /tmp/t_def.so 2>/dev/null | grep ' U ' || echo "  (0 个)"
echo "--- -march=armv7-a -mfloat-abi=hard -mfpu=neon ---"
arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -Oz -w -march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-unwind-tables -fno-asynchronous-unwind-tables /tmp/t.c -o /tmp/t_v7.so 2>&1 | head -5
echo "  未定义:"; arm-linux-gnueabihf-nm -D /tmp/t_v7.so 2>/dev/null | grep ' U ' || echo "  (0 个)"

echo "===== [3] 完整 drm_stub.c 加 -march=armv7-a 后的未定义符号 ====="
arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -Oz -w -march=armv7-a -mfloat-abi=hard -mfpu=neon \
  -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -Wl,-soname,libdrm.so.2 tools/guest_shim/drm_stub.c -o /tmp/drm_v7.so 2>&1 | head -5
echo "  未定义:"; arm-linux-gnueabihf-nm -D /tmp/drm_v7.so 2>/dev/null | grep ' U ' || echo "  (0 个)"
echo "  size=$(wc -c < /tmp/drm_v7.so 2>/dev/null)  dumb#=$(grep -a -c -F 'dumb#' /tmp/drm_v7.so 2>/dev/null)"
echo "  导出数=$(arm-linux-gnueabihf-nm -D --defined-only /tmp/drm_v7.so 2>/dev/null | wc -l)"

echo "===== [4] alsa 桩 / shim 未定义符号审计 ====="
echo "  libasound.so.2 未定义:"; arm-linux-gnueabihf-nm -D report/alsastublib/libasound.so.2 2>/dev/null | grep ' U ' || echo "  (0)"
echo "  libkms.so.1 未定义:"; arm-linux-gnueabihf-nm -D report/stublib/libkms.so.1 2>/dev/null | grep ' U ' || echo "  (0)"
echo "  guest_shim.so 未定义:"; arm-linux-gnueabihf-nm -D report/guest_shim.so 2>/dev/null | grep ' U ' | head -10 || echo "  (0)"

echo "===== [5] 设备 rootfs 是否有 libgcc_s 可兜底解析 divmod ====="
find /workspace/1to1/golden/device_rootfs_min -name 'libgcc_s*' 2>/dev/null | head -5
find /workspace/1to1/golden/device_rootfs_min -name 'ld-*.so*' -o -name 'ld-linux*' 2>/dev/null | head -5
echo "DIAG-DONE"