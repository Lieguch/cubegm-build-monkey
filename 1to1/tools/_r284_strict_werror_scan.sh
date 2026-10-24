#!/bin/sh
# _r284_strict_werror_scan.sh —— 本地复刻 CI s20 严格类型轨（R284 诊断用）
# 临时切换 proto.h -> proto.h.strict，全量编译 214 个专有文件，
# 收集 -Werror=int-conversion/incompatible-pointer-types/implicit-int 错误。
# 跑完原子恢复 proto.h（与 _run_arity_full_strict.sh 同模式）。
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PH="$ROOT/src/compat/proto.h"
ST="$ROOT/src/compat/proto.h.strict"
BK="$PH._live_backup284"
OUT="$ROOT/report/_r284_strict_werror.txt"
ZIG="${ZIG:-C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe}"

if [ -e "$BK" ]; then echo "ABORT: stale backup $BK" >&2; exit 2; fi
cp "$PH" "$BK"
cp "$ST" "$PH"
: > "$OUT"
fail=0; n=0
for f in $(find "$ROOT/src/proprietary" -name '*.c' | sort); do
  n=$((n+1))
  err=$("$ZIG" cc -c -Os -Wall \
        -Werror=int-conversion -Werror=incompatible-pointer-types -Werror=implicit-int \
        -Wno-error=implicit-function-declaration -Wno-error=unused-parameter -Wno-error=unused-variable \
        -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon \
        -fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 \
        -I "$ROOT/src/compat" -I "$ROOT/src" \
        -o "$ROOT/build/_arity_chk.o" "$f" 2>&1)
  if [ -n "$err" ]; then
    fail=$((fail+1))
    echo "===== ${f#$ROOT/}" >> "$OUT"
    echo "$err" | grep -E "error:" >> "$OUT"
  fi
done
mv -f "$BK" "$PH"
echo "严格类型轨：编译 $n 个文件，失败 $fail 个"
echo "明细: $OUT"
