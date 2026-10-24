#!/bin/sh
# 用精确原型编译**全部**专有源文件，收集"实参个数不符"等编译错误（一次过清单）
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
. "$ROOT/tools/cgm_upgrade_flags.sh" 2>/dev/null || true
ZIG="${ZIG:-C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe}"
OUT="$ROOT/report/arity_compile.txt"
: > "$OUT"
fail=0
n=0
for f in $(find "$ROOT/src/proprietary" -name '*.c' | sort); do
  n=$((n+1))
  err=$("$ZIG" cc -c -Os -w -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon \
        -fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 \
        -DCGM_DIAG_TRACE_ZIP -DCGM_DIAG_TRACE_INPUT ${CGM_DEFS:-} ${CGM_HDR:-} \
        -I "$ROOT/src/compat" -I "$ROOT/src" \
        -o "$ROOT/build/_arity_chk.o" "$f" 2>&1)
  if [ -n "$err" ]; then
    fail=$((fail+1))
    echo "===== ${f#$ROOT/}" >> "$OUT"
    echo "$err" | grep -E "error:|note: passing argument" >> "$OUT"
  fi
done
echo "编译 $n 个文件，失败 $fail 个" >> "$OUT"
echo "编译 $n 个文件，失败 $fail 个"
grep -c "^=====" "$OUT" 2>/dev/null || true
