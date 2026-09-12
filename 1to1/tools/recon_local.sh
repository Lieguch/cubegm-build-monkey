#!/bin/sh
# ============================================================
# recon_local.sh — 本地逐函数编译回路（zig cc，ARM32 hard-float）
#
# 目的：把 CI 的分钟级往返降为本地秒级迭代。
# 校准铁律：本地结果只用于**迭代**；最终判定仍以 CI（GCC 11.4 +
# Ubuntu 22.04 头）为准。两者分歧时，以 CI 日志为准并记录差异。
#
# ★ 已实测校准：zig 产物 e_flags=0x05000400 与原厂逐位一致
#   （EABIv5 + hard-float + interworking），ABI 门禁风险 = 0。
# ★ 铁律：zig.exe 是 Windows 原生程序 —— 传给它的所有路径必须是
#   Windows 原生形式（C:/...）；Git Bash 的 /tmp 挂在 R: 虚拟盘，
#   会触发 CacheCheckFailed。
#
# 用法:
#   sh tools/recon_local.sh [输出报告]
# ============================================================
set -u
ZIG="${ZIG:-C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRCDIR="$ROOT/src/proprietary"
REP="${1:-$ROOT/report/local_recon_build.txt}"

# 传给 zig.exe 的路径全部转 Windows 原生形式
NROOT="$(cygpath -w "$ROOT" 2>/dev/null || echo "$ROOT")"
# ★ CI 对齐铁律：CI 用 GCC(-w)——implicit-function-declaration / int-conversion 只是警告。
#   Clang 默认把这两类升为 error，导致本地比 CI 更严（伪差）。必须显式降级为警告，
#   使「本地失败集合」≈「CI 失败集合」。ABI 与错误判定以 CI 为准。
CFLAGS="-c -O1 -w -Wno-error=implicit-function-declaration -Wno-error=int-conversion -Wno-error=incompatible-pointer-types -Wno-error=implicit-int -Wno-error=uninitialized -Wno-error=return-type -Wno-error=unused-variable -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon -I$NROOT/src/compat"
# ★ 严格口径：把 int-conversion / incompatible-pointer / implicit-int 升为 error。
#   用于「消除假绿」——只有它通过，才代表类型真正正确（否则 FILE*/int 混用等会真崩）。
#   只对宽松通过的文件重测，成本不翻倍。
CFLAGS_STRICT="-c -O1 -Wall -Werror=int-conversion -Werror=incompatible-pointer-types -Werror=implicit-int -Wno-error=implicit-function-declaration -Wno-error=unused-parameter -Wno-error=unused-variable -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon -I$NROOT/src/compat"

# zig 缓存 + 中间产物全放 C: 盘原生临时目录
NTMP="C:/Users/Administrator/AppData/Local/Temp/zigcache1to1"
mkdir -p "$NTMP/zigcache"
export ZIG_GLOBAL_CACHE_DIR="$NTMP/zigcache"
TMP="$NTMP/recon_local_$$"
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

ok=0; bad=0; total=0
: > "$TMP/bad.txt"
: > "$TMP/ok.txt"

for f in "$SRCDIR"/*/*.c; do
    [ -f "$f" ] || continue
    total=$((total + 1))
    nf="$(cygpath -w "$f" 2>/dev/null || echo "$f")"
    rel="${f#$ROOT/}"
    if "$ZIG" cc $CFLAGS "$nf" -o "$TMP/o.o" 2> "$TMP/err.txt"; then
        ok=$((ok + 1))
        echo "$rel" >> "$TMP/ok.txt"
    else
        bad=$((bad + 1))
        # 提取前 3 条 error 行（比 CI 的首错更有诊断力）
        firsterr=$(grep -a -m3 -E 'error:' "$TMP/err.txt" | head -c 400)
        [ -n "$firsterr" ] || firsterr=$(head -c 300 "$TMP/err.txt" | tr '\n' ' ')
        echo "$rel|$firsterr" >> "$TMP/bad.txt"
    fi
done

# ============================================================
# 严格口径双轨复测（消除假绿）：把「宽松通过」文件用严格 CFLAGS 再测。
# 严格通过 = 类型真正正确；严格失败 = 假绿（类型错被 warning 掩盖）。
# 只重测宽松通过文件，成本不翻倍。
# ============================================================
strict_ok=0
: > "$TMP/strict_bad.txt"
while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    nf="$(cygpath -w "$ROOT/$rel" 2>/dev/null || echo "$ROOT/$rel")"
    if "$ZIG" cc $CFLAGS_STRICT "$nf" -o "$TMP/s.o" 2> "$TMP/serr.txt"; then
        strict_ok=$((strict_ok + 1))
    else
        serr=$(grep -a -m3 -E 'error:' "$TMP/serr.txt" | head -c 300)
        [ -n "$serr" ] || serr=$(head -c 200 "$TMP/serr.txt" | tr '\n' ' ')
        echo "$rel|$serr" >> "$TMP/strict_bad.txt"
    fi
done < "$TMP/ok.txt"
strict_bad=$(( ok - strict_ok ))

mkdir -p "$(dirname "$REP")"
{
  echo "============================================================"
  echo "本地重建编译回路  CC=zig cc (clang 21) target=arm hard-float"
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
  echo "★ 假绿清单：宽松通过但严格失败（类型错误被 warning 掩盖，链接/运行期会崩）："
  if [ -s "$TMP/strict_bad.txt" ]; then
    cat "$TMP/strict_bad.txt"
  else
    echo "（无 —— 全部宽松通过文件也严格通过）"
  fi
  echo ""
  echo "--- 宽松口径失败明细（全量，每文件前 3 错）---"
  cat "$TMP/bad.txt"
} | tee "$REP"

# 硬门禁：全失败 = 编译回路未生效（与 CI 版一致）
if [ "$ok" -eq 0 ] && [ "$total" -gt 0 ]; then
  echo "::error::recon_local: 0 个函数本地编译通过，回路未生效"
  exit 1
fi
exit 0
