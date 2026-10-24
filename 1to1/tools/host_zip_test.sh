#!/bin/sh
# host_zip_test.sh —— L1（本机）zip 逻辑端到端自测：把**同一份** unzip.cpp 编到 PC 上跑真数据
#
# 为什么需要（R262）：XOR 开关那一类缺陷（只该对 WQW 容器解密）在真机上是"名字解不开"，
#   在 PC 上 10 分钟就能证死；我上一轮却先上了真机。此脚本把这件事变成一条命令。
#
# 判据（三条都必须满足，否则 exit 1）：
#   ① 原厂 PK 容器（ui_cn.zip，明文名）+ 厂商 key2 → 6/6 命中
#   ② 原厂 WQW 容器（003.dat，密文名）+ 厂商 key2 → 命中；**不给密钥 → 必须 NOTFOUND**（证明解密真在工作）
#   ③ 原厂 joystick.zip → 3/3 命中
# 用法：sh tools/host_zip_test.sh
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIG="${ZIG:-$(ls /*/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe 2>/dev/null | head -1)}"
[ -n "${ZIG:-}" ] || ZIG="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe"
EXE="$ROOT/build/host_zip_test.exe"
mkdir -p "$ROOT/build/hostshim" "$ROOT/build"
# 主机 shim 补丁（只影响本机测试，不动生产 shim）
if [ ! -f "$ROOT/build/hostshim/windows.h" ]; then
  cp "$ROOT/src/upstream/xunzip/posix/windows.h" "$ROOT/build/hostshim/windows.h"
  cp "$ROOT/src/upstream/xunzip/posix/tchar.h"   "$ROOT/build/hostshim/tchar.h"
  sed -i 's/^typedef int            __time32_t;/#ifndef _WIN32\ntypedef int            __time32_t;\n#endif/' "$ROOT/build/hostshim/windows.h" 2>/dev/null || true
fi
"$ZIG" cc -std=gnu++14 -O1 -w -DXUNZIP_KEEP_PLAIN_WRAPPERS \
    -I "$ROOT/build/hostshim" -I "$ROOT/src/upstream/xunzip" \
    -o "$EXE" "$ROOT/tools/host_zip_test.cpp" "$ROOT/src/upstream/xunzip/unzip.cpp" || { echo "!! 编译失败" >&2; exit 2; }
fail=0
chk() { # desc, expect_rc, args...
  d="$1"; want="$2"; shift 2
  out=$("$EXE" "$@" 2>&1); rc=$?
  if [ "$rc" -eq "$want" ]; then echo "  ✓ $d"; else echo "  ✗ $d（rc=$rc，期望 $want）"; echo "$out" | tail -3; fail=1; fi
}
echo "== L1 zip 逻辑自测 =="
chk "PK 容器 ui.cfg      （应命中）" 0 "$ROOT/golden/sdcard_min/ui_cn.zip"        vendor ui.cfg
chk "PK 容器 menu.raw    （应命中）" 0 "$ROOT/golden/sdcard_min/ui_cn.zip"        vendor menu.raw
chk "PK 容器 setting.raw （应命中）" 0 "$ROOT/golden/sdcard_min/ui_cn.zip"        vendor setting.raw
chk "PK 容器 joystick   （应命中）" 0 "$ROOT/golden/sdcard_min/joystick.zip"      vendor joystick.raw
chk "WQW 容器 003.dat   （应命中）" 0 "$ROOT/golden/sdcard_min/003.dat"           vendor "Action 52 in 1_000.raw"
chk "WQW 容器 无密钥    （应 NOTFOUND）" 1 "$ROOT/golden/sdcard_min/003.dat"      zero   "Action 52 in 1_000.raw"
[ "$fail" -eq 0 ] && { echo "== L1 PASS =="; exit 0; } || { echo "== L1 FAIL =="; exit 1; }
