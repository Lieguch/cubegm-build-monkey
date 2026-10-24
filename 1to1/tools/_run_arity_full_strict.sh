#!/bin/sh
# 临时：切 proto.h.strict 全量跑门禁（去截断版），跑完自动原子恢复 proto.h
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PH="$ROOT/src/compat/proto.h"
ST="$ROOT/src/compat/proto.h.strict"
BK="$PH._live_backup"
if [ -e "$BK" ]; then
  echo "ABORT: stale backup $BK exists — clean it first" >&2
  exit 2
fi
cp "$PH" "$BK"
cp "$ST" "$PH"
echo "=== switched to strict, running gate ==="
sh "$ROOT/tools/check_arity_compile.sh"
echo "=== restoring proto.h ==="
mv -f "$BK" "$PH"
echo "restored K&R count: $(grep -cE 'extern [^(;]+\(\);' "$PH")"
echo "=== error lines total in report: $(grep -cE 'error:' "$ROOT/report/arity_compile.txt")"