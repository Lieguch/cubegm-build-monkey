#!/bin/sh
# 取证三件事：① GCC -O1 的 divmod 未定义（判断问题历史）② 设备 libc 是否导出 aeabi divmod ③ hidden divmod 兜底的最小可行性实验
set -u
cd /workspace/1to1 || exit 9

echo "===== [1] GCC -O1 的未定义符号（判断 divmod 问题是否自古有之）====="
arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -O1 -w \
  -fno-unwind-tables -fno-asynchronous-unwind-tables \
  -Wl,-soname,libdrm.so.2 tools/guest_shim/drm_stub.c -o /tmp/drm_o1c.so 2>&1 | head -3
echo "  O1 未定义:"; arm-linux-gnueabihf-nm -D /tmp/drm_o1c.so 2>/dev/null | grep ' U ' || echo "  (0)"

echo "===== [2] 设备 libc 是否导出 __aeabi_uidivmod / idivmod（判断旧产物能否现场加载）====="
arm-linux-gnueabihf-nm -D golden/device_rootfs_min/lib/libc.so.6 2>/dev/null | grep -iE '__aeabi_(ui)?div(mod)?' | head -20
echo "  ---- libgcc_s ----"
arm-linux-gnueabihf-nm -D golden/device_rootfs_min/lib/libgcc_s.so.1 2>/dev/null | grep -iE '__aeabi_(ui)?div(mod)?' | head -20
echo "  ---- ld-2.29 ----"
arm-linux-gnueabihf-nm -D golden/device_rootfs_min/lib/ld-2.29.so 2>/dev/null | grep -iE '__aeabi_(ui)?div(mod)?' | head -20

echo "===== [3] hidden divmod 兜底最小实验（GCC -Os -nostdlib）====="
cat > /tmp/divm.c <<'CEOF'
typedef unsigned int u32;
/* EABI 运行时 helper：GCC -Os 会把 v%10 + v/10 合并成 __aeabi_uidivmod 调用 */
struct uqr { u32 q; u32 r; };
__attribute__((visibility("hidden")))
struct uqr __aeabi_uidivmod(u32 n, u32 d)
{
    u32 q = 0, r = 0;
    int i;
    if (d == 0) { struct uqr z = {0,0}; return z; }
    for (i = 31; i >= 0; i--) {
        r = (r << 1) | ((n >> i) & 1u);
        if (r >= d) { r -= d; q |= (1u << i); }
    }
    { struct uqr z = {q, r}; return z; }
}
/* 触发点：十进制转换（商+余都要） */
u32 f(u32 v){ char b[12]; int m=0; if(!v) b[m++]='0';
  while(v){ b[m]=(char)('0'+(v%10u)); v/=10u; m++; } return m; }
CEOF
echo "--- 不带 helper 对照 ---"
sed '/__aeabi_uidivmod/,/^}/d' /tmp/divm.c > /tmp/divm_noh.c
cat > /tmp/divm_noh2.c <<'CEOF'
typedef unsigned int u32;
u32 f(u32 v){ char b[12]; int m=0; if(!v) b[m++]='0';
  while(v){ b[m]=(char)('0'+(v%10u)); v/=10u; m++; } return m; }
CEOF
arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -Os -w -fno-unwind-tables -fno-asynchronous-unwind-tables /tmp/divm_noh2.c -o /tmp/divm_noh.so 2>&1 | head -3
echo "  无 helper 未定义:"; arm-linux-gnueabihf-nm -D /tmp/divm_noh.so 2>/dev/null | grep ' U ' || echo "  (0)"
echo "--- 带 hidden helper ---"
arm-linux-gnueabihf-gcc -shared -fPIC -nostdlib -Os -w -fno-unwind-tables -fno-asynchronous-unwind-tables /tmp/divm.c -o /tmp/divm_h.so 2>&1 | head -3
echo "  带 helper 未定义:"; arm-linux-gnueabihf-nm -D /tmp/divm_h.so 2>/dev/null | grep ' U ' || echo "  (0)"
echo "  helper 是否导出(应为空=hidden):"; arm-linux-gnueabihf-nm -D --defined-only /tmp/divm_h.so 2>/dev/null | grep -i divmod || echo "  (hidden,未导出 ✓)"
echo "  helper 是否 local 定义:"; arm-linux-gnueabihf-nm /tmp/divm_h.so 2>/dev/null | grep -iE 'divmod' | head -5

echo "===== [4] 验证 hidden helper 的正确性（qemu-arm 跑测试）====="
cat > /tmp/divtest.c <<'CEOF'
#include <stdio.h>
typedef unsigned int u32;
struct uqr { u32 q; u32 r; };
__attribute__((visibility("hidden")))
struct uqr __aeabi_uidivmod(u32 n, u32 d){ u32 q=0,r=0; int i; if(d==0){struct uqr z={0,0};return z;}
  for(i=31;i>=0;i--){ r=(r<<1)|((n>>i)&1u); if(r>=d){r-=d;q|=(1u<<i);} } struct uqr z={q,r}; return z; }
u32 f(u32 v){ char b[12]; int m=0; if(!v) b[m++]='0'; while(v){ b[m]=(char)('0'+(v%10u)); v/=10u; m++; } return m; }
int main(void){
  u32 tv[7] = {0,1,9,10,99,12345,2000};
  int bad=0, i;
  for(i=0;i<7;i++){ u32 r=f(tv[i]); int e=0; u32 t=tv[i];
    if(!t)e=1; else while(t){ t/=10; e++; }
    if(r!=(u32)e){ bad=1; printf("MISMATCH v=%u got=%u exp=%d\n", tv[i], r, e); } }
  printf("divmod helper test %s\n", bad?"FAIL":"OK");
  return bad;
}
CEOF
if command -v qemu-arm-static >/dev/null 2>&1; then
  arm-linux-gnueabihf-gcc -O2 -w /tmp/divtest.c -o /tmp/divtest_arm 2>&1 | head -3
  qemu-arm-static /tmp/divtest_arm 2>&1 | head -5
else
  echo "  (无 qemu-arm-static，跳过运行时正确性验证)"
fi
echo "DIAG-DONE"