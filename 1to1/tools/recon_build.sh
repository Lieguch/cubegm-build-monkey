#!/bin/sh
# ============================================================
# recon_build.sh — 重建函数集编译门禁（CI 版，双轨）
#
# 对 src/proprietary/ 下每个函数逐个编译，报告通过/失败与首错。
# 这是重建进度的**真实度量**（不是"写了多少文件"，而是"能编译多少函数"）。
#
# ★ 双轨口径（消除假绿）：
#   宽松 = 语法通过（-w，只拦真语法/结构错）
#   严格 = 类型正确（-Werror=int-conversion / incompatible-pointer-types /
#                    implicit-int）——只有严格通过才代表类型真正确
#   硬门禁：严格失败 > 0 即 exit 1（不允许用 warning 掩盖类型错）
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
CFLAGS_STRICT="-c -O1 -Wall -Werror=int-conversion -Werror=incompatible-pointer-types -Werror=implicit-int -Wno-error=implicit-function-declaration -Wno-error=unused-parameter -Wno-error=unused-variable -I$ROOT/src/compat -march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic"

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
        firsterr=$(grep -a -m3 -E 'error:' "$TMP/err.txt" | head -c 400)
        [ -n "$firsterr" ] || firsterr=$(head -c 300 "$TMP/err.txt" | tr '\n' ' ')
        echo "$rel|$firsterr" >> "$TMP/bad.txt"
    fi
done

# ---- 严格口径双轨复测（只重测宽松通过文件，成本不翻倍）----
strict_ok=0
: > "$TMP/strict_bad.txt"
while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    if "$CC" $CFLAGS_STRICT "$ROOT/$rel" -o "$TMP/s.o" 2> "$TMP/serr.txt"; then
        strict_ok=$((strict_ok + 1))
    else
        serr=$(grep -a -m3 -E 'error:' "$TMP/serr.txt" | head -c 300)
        [ -n "$serr" ] || serr=$(head -c 200 "$TMP/serr.txt" | tr '\n' ' ')
        echo "$rel|$serr" >> "$TMP/strict_bad.txt"
    fi
done < "$TMP/ok.txt"
strict_bad=$(( ok - strict_ok ))

{
  echo "============================================================"
  echo "重建编译门禁（双轨）  CC=$CC"
  echo "============================================================"
  echo "【宽松口径 / 语法通过】 总计 $total，通过 $ok，失败 $bad"
  if [ "$total" -gt 0 ]; then
    awk -v o="$ok" -v t="$total" 'BEGIN{printf "        语法通过率 %.1f%%\n", 100.0*o/t}'
  fi
  echo "【严格口径 / 类型正确】 在宽松通过的 $ok 中：严格通过 $strict_ok，假绿(类型错) $strict_bad"
  if [ "$ok" -gt 0 ]; then
    awk -v s="$strict_ok" -v o="$ok" 'BEGIN{printf "        类型正确率(占宽松通过) %.1f%%\n", 100.0*s/o}'
  fi
  echo ""
  echo "★ 假绿清单：宽松通过但严格失败（类型错误被 warning 掩盖）："
  if [ -s "$TMP/strict_bad.txt" ]; then cat "$TMP/strict_bad.txt"; else echo "（无）"; fi
  echo ""
  echo "--- 宽松口径失败明细（每文件前 3 错）---"
  head -40 "$TMP/bad.txt"
  echo ""
  echo "--- 失败原因聚类（关键词）---"
  sed 's/.*error: //' "$TMP/bad.txt" | sed 's/[0-9]\+/N/g' | sort | uniq -c | sort -rn | head -20
} | tee "$REP"

# 硬门禁 1：全失败 = 作业未生效
if [ "$ok" -eq 0 ] && [ "$total" -gt 0 ]; then
  echo "::error::recon_build: 0 个函数编译通过，门禁未生效"
  exit 1
fi
# 硬门禁 2：假绿必须为 0（不允许类型错被 warning 掩盖）
if [ "$strict_bad" -gt 0 ]; then
  echo "::error::recon_build: 存在 $strict_bad 个假绿（宽松通过但严格类型失败），禁止用 warning 掩盖类型错"
  exit 1
fi
exit 0
