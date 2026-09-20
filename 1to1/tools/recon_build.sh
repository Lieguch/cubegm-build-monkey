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
# ★ 与工厂二进制对齐的行为相关标志（工厂 .comment 里印着完整命令行：
#   `... -fno-stack-protector ...`，且二进制中 stack_chk/FORTIFY/__memcpy_chk 出现次数均为 0）。
#   Ubuntu 的 GCC 默认插 canary 并开 FORTIFY ⇒ 重建产物会 abort（*** stack smashing detected ***），
#   那是工具链差异，不是代码差异 ⇒ 必须显式关掉，否则行为差分永远有一处假分歧。
FIDELITY="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
# ★ CC 自适应：**zig 的 gnueabihf 目标不支持 `-fno-pic`**（会报 unsupported），
#   而 GCC 需要它。此前这里把 `-march=… -fno-pic` 写死，导致 CI 一旦改用 zig cc
#   就会在编译步骤直接失败（本地用 recon_local.sh 因此没暴露）。
case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic" ;;
esac
# ★★ 2026-09-20（GAP 16.33）：**优化级别默认 -Os**（此前 -O1）。
#   依据：单变量抽样实测（zig cc -target arm-linux-gnueabihf.2.29，逐个编译同一份 src）
#     SPI_RR         工厂  92 B ⇒ -O1 384 B (4.17x)  vs  **-Os  92 B (1.00x，精确到字节)**
#     gameType       工厂  60 B ⇒ -O1 276 B (4.60x)  vs  **-Os  52 B (0.87x)**
#     Convert_Stereo 工厂  56 B ⇒ -O1 412 B (7.36x)  vs  **-Os  76 B (1.36x)**
#     outputblankxy  工厂 220 B ⇒ -O1 644 B (2.93x)  vs  **-Os 272 B (1.24x)**
#     DrawSelectBar  工厂 168 B ⇒ -O1 488 B (2.90x)  vs  **-Os 196 B (1.17x)**
#     SPI_WW         工厂 104 B ⇒ -O1 296 B (2.85x)  vs  **-Os  96 B (0.92x)**
#     DrawFrame      工厂 552 B ⇒ -O1 644 B (1.17x)  vs  **-Os 508 B (0.92x)**
#   ⇒ **工厂 rkgame 是用 -Os 编译的**；-O1 会把"常量次数的小循环"完全展开
#     （源码里的 `do{...}while(cVar2 != 0)`，次数为编译期常量），制造 4~7x 的
#     **纯编译差异**，被 tools/prop_equiv.py 的 size 比值判据误报成 FAIL。
#   ★ 单变量纪律：想回到旧口径做对照，用 `OPT=-O1 sh tools/recon_build.sh`。
OPT="${OPT:--Os}"
CFLAGS="-c $OPT -w -I$ROOT/src/compat $ARCH $FIDELITY"
CFLAGS_STRICT="-c $OPT -Wall -Werror=int-conversion -Werror=incompatible-pointer-types -Werror=implicit-int -Wno-error=implicit-function-declaration -Wno-error=unused-parameter -Wno-error=unused-variable -I$ROOT/src/compat $ARCH $FIDELITY"

mkdir -p "$(dirname "$REP")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

ok=0; bad=0; infra=0; total=0
: > "$TMP/bad.txt"
: > "$TMP/ok.txt"
: > "$TMP/infra.txt"

# ---------------------------------------------------------------------------
# ★★ 三态判定（与 tools/recon_local.sh 完全同语义；血泪见该脚本长注释）
#   ① rc=0                            → 通过
#   ② rc≠0 且 stderr 含 `error:`       → 真源码错误（宽松失败 / 严格假绿）
#   ③ rc≠0 且 stderr 不含 `error:`     → INFRA 未判定：重试一次；仍如此则单独计数，
#                                        既不算通过也不算类型错，并在末尾显式失败。
#   判据用「有没有 `error:`」而非「stderr 是否为空」：编译器可能只吐 warning 后因
#   环境原因失败，那时 stderr 非空但依然不是源码错误。
# ---------------------------------------------------------------------------
compile_loose() {
    c_rc=0
    $CC $CFLAGS "$1" -o "$TMP/o.o" 2> "$TMP/err.txt" || c_rc=$?
    if [ "$c_rc" != "0" ] && ! grep -qa "error:" "$TMP/err.txt"; then
        sleep 2
        c_rc=0
        $CC $CFLAGS "$1" -o "$TMP/o.o" 2> "$TMP/err.txt" || c_rc=$?
    fi
    return "$c_rc"
}

for f in "$SRCDIR"/*/*.c; do
    [ -f "$f" ] || continue
    total=$((total + 1))
    rel="${f#$ROOT/}"
    # shellcheck disable=SC2086
    # ★ 不能写成 "$CC"：CC 可能是多词命令（如 `<zig> cc`），加引号会被当成单个文件名
    #   → `No such file or directory`（技能库第 28 条）。
    if compile_loose "$f"; then
        ok=$((ok + 1))
        echo "$rel" >> "$TMP/ok.txt"
    elif grep -qa "error:" "$TMP/err.txt"; then
        bad=$((bad + 1))
        firsterr=$(grep -a -m3 -E 'error:' "$TMP/err.txt" | head -c 400)
        echo "$rel|$firsterr" >> "$TMP/bad.txt"
    else
        infra=$((infra + 1))
        echo "$rel|$(grep -a -m2 -E 'warning:|note:' "$TMP/err.txt" | head -c 200 | tr '\n' ' ')" \
             >> "$TMP/infra.txt"
    fi
done

# ---- 严格口径双轨复测（只重测宽松通过文件，成本不翻倍）----
strict_ok=0
: > "$TMP/strict_bad.txt"
: > "$TMP/infra_strict.txt"
while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    # shellcheck disable=SC2086
    s_rc=0
    $CC $CFLAGS_STRICT "$ROOT/$rel" -o "$TMP/s.o" 2> "$TMP/serr.txt" || s_rc=$?
    # ★ 同「宽松口径」三态语义：rc≠0 且无 `error:` ⇒ 瞬时故障，重试一次
    if [ "$s_rc" != "0" ] && ! grep -qa "error:" "$TMP/serr.txt"; then
        sleep 2
        s_rc=0
        $CC $CFLAGS_STRICT "$ROOT/$rel" -o "$TMP/s.o" 2> "$TMP/serr.txt" || s_rc=$?
    fi
    if [ "$s_rc" = "0" ]; then
        strict_ok=$((strict_ok + 1))
    elif grep -qa "error:" "$TMP/serr.txt"; then
        serr=$(grep -a -m3 -E 'error:' "$TMP/serr.txt" | head -c 300)
        echo "$rel|$serr" >> "$TMP/strict_bad.txt"
    else
        echo "$rel|$(grep -a -m2 -E 'warning:|note:' "$TMP/serr.txt" | head -c 200 | tr '\n' ' ')" \
             >> "$TMP/infra_strict.txt"
    fi
done < "$TMP/ok.txt"
strict_infra=$(wc -l < "$TMP/infra_strict.txt" 2>/dev/null | tr -d ' '); strict_infra=${strict_infra:-0}
strict_bad=$(( ok - strict_ok - strict_infra ))

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
  echo "--- ★ INFRA 未判定（rc≠0 但 stderr 无 'error:'；已重试一次仍如此）---"
  echo "    语义：既不算通过、也不算类型错。必须先消除环境因素再复跑，本报告才可信。"
  echo "    宽松口径 $infra 项 / 严格口径 $strict_infra 项"
  if [ -s "$TMP/infra.txt" ]; then cat "$TMP/infra.txt"; fi
  if [ -s "$TMP/infra_strict.txt" ]; then cat "$TMP/infra_strict.txt"; fi
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
# 硬门禁 3：INFRA 未判定 ⇒ 本轮门禁结论无效（既非通过也非失败），必须显式失败
if [ "$infra" -gt 0 ] || [ "$strict_infra" -gt 0 ]; then
  echo "::error::recon_build: 出现 INFRA 未判定（宽松 $infra / 严格 $strict_infra）⇒ 本轮结论无效，请复跑"
  exit 3
fi
exit 0
