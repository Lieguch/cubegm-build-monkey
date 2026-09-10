#!/bin/sh
# ============================================================
# recon_build.sh — 重建函数集编译门禁
#
# 对 src/proprietary/ 下每个函数逐个编译，报告通过/失败与首错。
# 这是重建进度的**真实度量**（不是"写了多少文件"，而是"能编译多少函数"）。
#
# 用法（CI 内）:
#   CC=arm-linux-gnueabihf-gcc sh tools/recon_build.sh [报告路径]
# ============================================================
set -u
CC="${CC:-arm-linux-gnueabihf-gcc}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REP="${1:-$ROOT/report/recon_build.txt}"
SRCDIR="$ROOT/src/proprietary"
CFLAGS="-c -O1 -w -I$ROOT/src/compat -march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic"

mkdir -p "$(dirname "$REP")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ok=0; bad=0; total=0
: > "$TMP/bad.txt"
: > "$TMP/ok.txt"

for f in "$SRCDIR"/*/*.c; do
    [ -f "$f" ] || continue
    total=$((total + 1))
    rel="${f#$ROOT/}"
    if "$CC" $CFLAGS "$f" -o "$TMP/o.o" 2> "$TMP/err.txt"; then
        ok=$((ok + 1))
        echo "$rel" >> "$TMP/ok.txt"
    else
        bad=$((bad + 1))
        # 提取首条 error 行
        firsterr=$(grep -a -m1 -E 'error:' "$TMP/err.txt" | head -c 200)
        [ -n "$firsterr" ] || firsterr=$(head -c 200 "$TMP/err.txt" | tr '\n' ' ')
        echo "$rel|$firsterr" >> "$TMP/bad.txt"
    fi
done

{
  echo "============================================================"
  echo "重建编译门禁  CC=$CC"
  echo "============================================================"
  echo "总计 $total 个函数文件，编译通过 $ok，失败 $bad"
  if [ "$total" -gt 0 ]; then
    # 用 awk 输出百分比
    awk -v o="$ok" -v t="$total" 'BEGIN{printf "通过率 %.1f%%\n", 100.0*o/t}'
  fi
  echo ""
  echo "--- 失败样本（前 25，含首错）---"
  head -25 "$TMP/bad.txt" | while IFS='|' read -r f e; do
    printf '  %-56s %s\n' "$f" "$e"
  done
  echo ""
  echo "--- 失败原因聚类（关键词）---"
  sed 's/.*error: //' "$TMP/bad.txt" | sed 's/[0-9]\+/N/g' | sort | uniq -c | sort -rn | head -20
} | tee "$REP"

# 硬门禁：全失败 = 作业未生效
if [ "$ok" -eq 0 ] && [ "$total" -gt 0 ]; then
  echo "::error::recon_build: 0 个函数编译通过，门禁未生效"
  exit 1
fi
exit 0
