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
# ★ `set -u` 下必须有默认值：尾部静态门禁要调用 python（此前依赖外部 export，缺了就中断）
PY="${PY:-python}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRCDIR="$ROOT/src/proprietary"
REP="${1:-$ROOT/report/local_recon_build.txt}"

# 传给 zig.exe 的路径全部转 Windows 原生形式
NROOT="$(cygpath -w "$ROOT" 2>/dev/null || echo "$ROOT")"
# ★ CI 对齐铁律：CI 用 GCC(-w)——implicit-function-declaration / int-conversion 只是警告。
#   Clang 默认把这两类升为 error，导致本地比 CI 更严（伪差）。必须显式降级为警告，
#   使「本地失败集合」≈「CI 失败集合」。ABI 与错误判定以 CI 为准。
# ★ 与工厂对齐（见 recon_build.sh 顶部说明）
FIDELITY="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
CFLAGS="-c -O1 -w -Wno-error=implicit-function-declaration -Wno-error=int-conversion -Wno-error=incompatible-pointer-types -Wno-error=implicit-int -Wno-error=uninitialized -Wno-error=return-type -Wno-error=unused-variable -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon -I$NROOT/src/compat $FIDELITY"
# ★ 严格口径：把 int-conversion / incompatible-pointer / implicit-int 升为 error。
#   用于「消除假绿」——只有它通过，才代表类型真正正确（否则 FILE*/int 混用等会真崩）。
#   只对宽松通过的文件重测，成本不翻倍。
CFLAGS_STRICT="-c -O1 -Wall -Werror=int-conversion -Werror=incompatible-pointer-types -Werror=implicit-int -Wno-error=implicit-function-declaration -Wno-error=unused-parameter -Wno-error=unused-variable -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon -I$NROOT/src/compat $FIDELITY"

# zig 缓存 + 中间产物全放 C: 盘原生临时目录
NTMP="C:/Users/Administrator/AppData/Local/Temp/zigcache1to1"
mkdir -p "$NTMP/zigcache"
export ZIG_GLOBAL_CACHE_DIR="$NTMP/zigcache"
TMP="$NTMP/recon_local_$$"
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

ok=0; bad=0; infra=0; total=0
: > "$TMP/bad.txt"
: > "$TMP/ok.txt"
: > "$TMP/infra.txt"

# ---------------------------------------------------------------------------
# ★★ 三态判定（血泪：把「基础设施瞬时故障」误判成「类型错误」）
#
# 事实依据（2026-09-16 实测）：`recon_local.sh` 曾连续 5 轮报「严格 213/213、假绿 0」，
#   随后一轮报「严格 212/213、假绿 1」，点名 FUN_000226a8_filelist_run_game.c，
#   但该行 stderr **为空**。手工以**完全相同的严格命令行**编译该文件 ⇒ rc=0、stderr 里
#   `error:` 出现次数 **0**（只有 7 条 warning + 2 条 note），连跑 3 次全 0。
#   ⇒ 那次 rc≠0 是**工具链/环境瞬时故障**（zig 在内存压力下可能非 0 退出且 stderr 为空），
#     却被计成「假绿」，污染了门禁结论。
#
# 新语义（三态，缺一不可）：
#   ① rc=0                              → 通过
#   ② rc≠0 且 stderr 含 `error:`         → **真源码错误**（宽松失败 / 严格假绿）
#   ③ rc≠0 且 stderr **不含** `error:`   → **INFRA 未判定**：先重试一次；
#                                           仍如此则单独计数，**既不算通过也不算类型错**，
#                                           并在末尾以非 0 退出码显式暴露。
#   判据用「有没有 `error:`」而不是「stderr 是否为空」—— 因为编译器也可能只吐 warning
#   然后因环境原因失败，那时 stderr 非空但依然不是源码错误。
# ---------------------------------------------------------------------------
compile_loose() {
    # $1 = 已转 Windows 形式的源文件路径
    rc=0
    "$ZIG" cc $CFLAGS "$1" -o "$TMP/o.o" 2> "$TMP/err.txt" || rc=$?
    if [ "$rc" != "0" ] && ! grep -qa "error:" "$TMP/err.txt"; then
        sleep 2                      # 让 OOM/锁竞争过去
        rc=0
        "$ZIG" cc $CFLAGS "$1" -o "$TMP/o.o" 2> "$TMP/err.txt" || rc=$?
    fi
    return "$rc"
}

for f in "$SRCDIR"/*/*.c; do
    [ -f "$f" ] || continue
    total=$((total + 1))
    nf="$(cygpath -w "$f" 2>/dev/null || echo "$f")"
    rel="${f#$ROOT/}"
    if compile_loose "$nf"; then
        ok=$((ok + 1))
        echo "$rel" >> "$TMP/ok.txt"
    elif grep -qa "error:" "$TMP/err.txt"; then
        bad=$((bad + 1))
        # 提取前 3 条 error 行（比 CI 的首错更有诊断力）
        firsterr=$(grep -a -m3 -E 'error:' "$TMP/err.txt" | head -c 400)
        echo "$rel|$firsterr" >> "$TMP/bad.txt"
    else
        infra=$((infra + 1))
        echo "$rel|$(grep -a -m2 -E 'warning:|note:' "$TMP/err.txt" | head -c 200 | tr '\n' ' ')" \
             >> "$TMP/infra.txt"
    fi
done

# ============================================================
# 严格口径双轨复测（消除假绿）：把「宽松通过」文件用严格 CFLAGS 再测。
# 严格通过 = 类型真正正确；严格失败 = 假绿（类型错被 warning 掩盖）。
# 只重测宽松通过文件，成本不翻倍。
# ============================================================
strict_ok=0
: > "$TMP/strict_bad.txt"
: > "$TMP/infra_strict.txt"
while IFS= read -r rel; do
    [ -n "$rel" ] || continue
    nf="$(cygpath -w "$ROOT/$rel" 2>/dev/null || echo "$ROOT/$rel")"
    s_rc=0
    "$ZIG" cc $CFLAGS_STRICT "$nf" -o "$TMP/s.o" 2> "$TMP/serr.txt" || s_rc=$?
    # ★ 同「宽松口径」的三态语义：rc≠0 且无 `error:` ⇒ 瞬时故障，重试一次
    if [ "$s_rc" != "0" ] && ! grep -qa "error:" "$TMP/serr.txt"; then
        sleep 2
        s_rc=0
        "$ZIG" cc $CFLAGS_STRICT "$nf" -o "$TMP/s.o" 2> "$TMP/serr.txt" || s_rc=$?
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
  echo "--- ★ INFRA 未判定（rc≠0 但 stderr 无 'error:'；已重试一次仍如此）---"
  echo "    语义：既不算通过、也不算类型错。必须先消除环境因素再复跑，本报告才可信。"
  echo "    宽松口径 $infra 项 / 严格口径 $strict_infra 项"
  if [ -s "$TMP/infra.txt" ]; then cat "$TMP/infra.txt"; fi
  if [ -s "$TMP/infra_strict.txt" ]; then cat "$TMP/infra_strict.txt"; fi
  echo ""
  echo "--- 宽松口径失败明细（全量，每文件前 3 错）---"
  cat "$TMP/bad.txt"
} | tee "$REP"

# 硬门禁：全失败 = 编译回路未生效（与 CI 版一致）
if [ "$ok" -eq 0 ] && [ "$total" -gt 0 ]; then
  echo "::error::recon_local: 0 个函数本地编译通过，回路未生效"
  exit 1
fi

# 硬门禁：INFRA 未判定 ⇒ 本轮结论不可信（既非通过也非失败），必须显式失败
if [ "$infra" -gt 0 ] || [ "$strict_infra" -gt 0 ]; then
  echo "::error::recon_local: 出现 INFRA 未判定（宽松 $infra / 严格 $strict_infra）⇒ 本轮门禁结论无效，请复跑"
  exit 3
fi

# 硬门禁：数组名转型（Ghidra 把 `arr[0]` 误渲染成 `(窄类型)arr` ⇒ 静默语义错）
#   该类错误**编译/链接/ABI/布局全绿**，只有行为差分或这个静态扫描能发现。
echo ""
echo "== 数组名转型静态门禁（tools/scan_array_casts.py）=="
if ! "$PY" "$NROOT/tools/scan_array_casts.py" "$NROOT/src"; then
  echo "::error::recon_local: 数组名被转型成窄整数（见上）"
  exit 2
fi

# 硬门禁：变参函数保真度（Ghidra 把 `f(const char*,...)` 渲染成单参数 ⇒ 静默语义错）
#   实测代价：RARCH_LOG 丢 `...` ⇒ RARCH_LOG_V 的 va_list 是调用者 r1 残留 ⇒ 崩在 libc strlen。
echo ""
echo "== 变参函数保真度门禁（tools/scan_varargs_fns.py）=="
if ! "$PY" "$NROOT/tools/scan_varargs_fns.py"; then
  echo "::error::recon_local: 有函数丢了变参语义（Ghidra 丢 \"...\"）"
  exit 4
fi

# 硬门禁：上游符号指纹（技能铁律 90 —— "库名对 ≠ 版本对"）
#   实测代价：XUnzip 版本不符 ⇒ TUnzip::Unzip 28 B vs 1608 B ⇒ P5 卡三轮。
#   ★ 依赖 build/rkgame.rebuilt.elf（由 link_full.sh 产出）；未链接时脚本会明确报错。
echo ""
echo "== 上游符号指纹门禁（tools/scan_upstream_fingerprint.py）=="
if ! "$PY" "$NROOT/tools/scan_upstream_fingerprint.py"; then
  echo "::error::recon_local: 上游库疑似版本/实现不符（见上表）"
  exit 5
fi
exit 0
