#!/bin/sh
# ============================================================================
# fidelity_matrix.sh —— 判决实验（重做版，第 65 轮）：**工具链对齐到底能不能让机器码更像工厂？**
#
# ## 为什么要重做（上一个版本错在两处，且从未跑过）
#   1. 它用的是 Ubuntu 自带的 `arm-linux-gnueabihf-gcc`（ubuntu-22.04 上是 GCC 11/12），
#      **不是工厂的编译器** ⇒ 实验从一开始就没在问正确的问题；
#   2. 它的 `OPT=-Os`，而工厂的优化级别**已从目标程序自带的 DWARF 读出**：`-O2`。
#   ⇒ 结论：那个实验即便跑了也答不了"换到原厂同款工具链会不会更接近"。
#
# ## 本版依据（全部来自 `golden/factory.rkgame.bin` 自身，见 `report/dwarf_recon.txt`）
#   · `DW_AT_producer`：`GNU C11 6.2.0 -mabi=aapcs-linux -march=armv7-a -mfloat-abi=hard
#     -mfpu=neon -mtune=cortex-a8 -mtls-dialect=gnu -g -O2 -std=gnu11 -fgnu89-inline
#     -fmerge-all-constants -fno-stack-protector -frounding-math -fomit-frame-pointer
#     -ftls-model=initial-exec`
#   · `DW_AT_comp_dir` = `/home/vmuser/Lakka/build.Lakka-a10.arm-8.0-devel/`
#     工具链目录 = `.../toolchain/lib/gcc/armv7a-libreelec-linux-gnueabi/6.2.0/include`
#   · `.comment` 有**两个**编译器标签：`GCC: (GNU) 6.2.0` 与 `Linaro GCC 4.9-2016.02) 4.9.4`
#     ⇒ 至少有**两组对象**来自**两个**工具链。哪一组编了 rkgame 自己的代码，**必须实验判定**，
#       不能猜。本脚本把**候选工具链全部下来并排跑**，让数据说话。
#   · `.note.gnu.gold-version` = GNU gold 1.12（对应 binutils 2.27，即 GCC 6.2 那一组）
#   · `.ARM.attributes`：CPU_arch=v7 / CPU_arch_profile=A / FP_arch=VFPv3 /
#     Advanced_SIMD_arch=Neon / ABI_VFP_args=硬浮点 ⇒ 应用对象确实按
#     `-march=armv7-a -mfloat-abi=hard -mfpu=neon` 编译。
#
# ## 设计（单变量）
#   同一份源码、**完全相同的一组 flags**（取自 DWARF），**唯一变量 = 编译器**：
#       clang(现状) / Linaro GCC 4.9.4-2016.02 / Linaro GCC 6.2.1-2016.11
#   只编译不链接（绕开跨工具链链接的 glibc 符号冲突），再用同一反汇编器与同一份工厂数据对拍。
#   判据（沿用既有、且已声明"不是功能进度尺"的相对刻度）：
#       M1 ±15% 体积命中数  ·  M2 助记符直方图 L1 中位
#
# ## 环境
#   需要联网下载工具链（CI 上没问题）。任一候选下载失败 ⇒ **不是静默跳过**，
#   而是把该候选标为 UNAVAILABLE 并**列入结论表**（"没跑"与"跑了但输了"必须可区分）。
#
# 输出：report/fidelity_matrix.txt
# exit: 0 = 至少两个候选完成对拍 / 11 = 仪器不可用（全部候选都不可用）
# ============================================================================
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 11
mkdir -p report build/fid cache_tc

# ---- 取自已实测的 DWARF：这组 flags 是**读出来的**，不是猜的 -----------------
OPT="${OPT:--O2}"
ARCHF="-march=armv7-a -mfloat-abi=hard -mfpu=neon -mtune=cortex-a8"
EXTRA="-std=gnu11 -fgnu89-inline -fmerge-all-constants -fno-stack-protector -fomit-frame-pointer -ftls-model=initial-exec -frounding-math -mtls-dialect=gnu"
COMMON="-c $OPT -w -I$ROOT/src/compat $ARCHF $EXTRA"

LINARO_49_URL="https://releases.linaro.org/components/toolchain/binaries/4.9-2016.02/arm-linux-gnueabihf/gcc-linaro-4.9-2016.02-x86_64_arm-linux-gnueabihf.tar.xz"
LINARO_62_URL="https://releases.linaro.org/components/toolchain/binaries/6.2-2016.11/arm-linux-gnueabihf/gcc-linaro-6.2.1-2016.11-x86_64_arm-linux-gnueabihf.tar.xz"

echo "======================= 仪器（口径自证）======================="
echo "  工厂 .comment   : $(python3 -c "
import re,sys
d=open('golden/factory.rkgame.bin','rb').read()
print(' | '.join(sorted(set(m.group(0).decode('latin1') for m in re.finditer(rb'GCC: \([^)]{0,40}\)[^\x00]{0,22}', d)))))
" 2>/dev/null || echo '(读取失败)')"
echo "  工厂 comp_dir   : $(python3 -c "
import re
d=open('golden/factory.rkgame.bin','rb').read()
m=re.search(rb'/home/\w+/[A-Za-z]+/build\.[A-Za-z0-9.\-]+', d)
print(m.group(0).decode() if m else '(未找到)')
" 2>/dev/null || echo '(读取失败)')"
echo "  flags（取自 DWARF）: OPT=$OPT $ARCHF"
echo "                       $EXTRA"
echo

# ---- 取工具链 --------------------------------------------------------------
fetch_tc() {
    # $1 = 目录名  $2 = url
    d="cache_tc/$1"
    if [ -x "$d/bin/chk" ]; then :; fi
    if [ -d "$d" ] && [ -n "$(ls -A "$d" 2>/dev/null)" ]; then
        echo "$d"
        return 0
    fi
    echo "  下载 $1 ..." >&2
    if ! curl -fsSL --retry 2 -o "cache_tc/$1.tar.xz" "$2"; then
        echo "   ★ $1 下载失败" >&2
        return 1
    fi
    mkdir -p "$d"
    if ! tar -xJf "cache_tc/$1.tar.xz" -C "$d" --strip-components=1; then
        echo "   ★ $1 解压失败" >&2
        return 1
    fi
    echo "$d"
}

prepare_candidate() {
    # $1=名字  $2=url  → 设置全局 CC_BIN 或返回 1
    dir=$(fetch_tc "$1" "$2") || return 1
    if [ -x "$dir/bin/arm-linux-gnueabihf-gcc" ]; then
        CC_BIN="$dir/bin/arm-linux-gnueabihf-gcc"
    else
        echo "   ★ $1 里找不到 arm-linux-gnueabihf-gcc" >&2
        return 1
    fi
    return 0
}

# ---- clang（现状基线）------------------------------------------------------
ZIGBIN=""
if command -v python3 >/dev/null 2>&1; then
    ZIGBIN=$(python3 -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)
fi
[ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ] || ZIGBIN="${ZIGBIN_ENV:-}"
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-/tmp/zigcache_fid}"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR"

RESULTS="report/_fid_matrix_results.txt"
: > "$RESULTS"

compile_all() {
    # $1 = 出目录  $2 = 编译命令前缀（余下由本函数拼 flags）
    out="$1"; shift
    rm -rf "$out"; mkdir -p "$out"
    ok=0; bad=0
    : > "report/_fid_err_$(basename "$out").txt"
    for f in "$ROOT"/src/proprietary/*/*.c; do
        [ -f "$f" ] || continue
        stem=$(basename "$f" .c)
        # shellcheck disable=SC2086
        if $@ $COMMON "$f" -o "$out/$stem.o" 2>>"report/_fid_err_$(basename "$out").txt"; then
            ok=$((ok+1))
        else
            bad=$((bad+1)); rm -f "$out/$stem.o"
        fi
    done
    echo "$ok $bad"
}

echo "======================= 编译（唯一变量 = 编译器）======================="
echo "  源文件数 = $(ls -1 "$ROOT"/src/proprietary/*/*.c | wc -l)"

# 1) clang 基线
if [ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ]; then
    r=$(compile_all build/fid/clang "$ZIGBIN cc -target arm-linux-gnueabihf")
    echo "  clang($("$ZIGBIN" cc --version 2>&1 | head -1 | tr -d '\n')) : ok=${r% *} bad=${r#* }"
    echo "clang ok=${r% *} bad=${r#* }" >> "$RESULTS"
else
    echo "  clang : UNAVAILABLE（找不到 zig）"
    echo "clang UNAVAILABLE" >> "$RESULTS"
fi

# 2) Linaro 4.9.4
if prepare_candidate linaro-4.9-2016.02 "$LINARO_49_URL"; then
    echo "  gcc49 : $($CC_BIN --version | head -1)"
    r=$(compile_all build/fid/gcc49 "$CC_BIN")
    echo "         ok=${r% *} bad=${r#* }"
    echo "gcc49 ok=${r% *} bad=${r#* }" >> "$RESULTS"
else
    echo "  gcc49 : UNAVAILABLE（下载/解压失败）"
    echo "gcc49 UNAVAILABLE" >> "$RESULTS"
fi

# 3) Linaro 6.2.1
if prepare_candidate linaro-6.2-2016.11 "$LINARO_62_URL"; then
    echo "  gcc62 : $($CC_BIN --version | head -1)"
    r=$(compile_all build/fid/gcc62 "$CC_BIN")
    echo "         ok=${r% *} bad=${r#* }"
    echo "gcc62 ok=${r% *} bad=${r#* }" >> "$RESULTS"
else
    echo "  gcc62 : UNAVAILABLE（下载/解压失败）"
    echo "gcc62 UNAVAILABLE" >> "$RESULTS"
fi

# ---- 收敛到两侧都编出的同子集（防幸存者偏差）-------------------------------
for cand in clang gcc49 gcc62; do
    [ -d "build/fid/$cand" ] || continue
    for o in build/fid/$cand/*.o; do
        [ -f "$o" ] || continue
        b=$(basename "$o")
        for other in clang gcc49 gcc62; do
            [ "$other" = "$cand" ] && continue
            [ -d "build/fid/$other" ] || continue
            [ -f "build/fid/$other/$b" ] || { rm -f "$o"; break; }
        done
    done
done
echo
echo "  各方可用对象数： clang=$(ls -1 build/fid/clang/*.o 2>/dev/null | wc -l)" \
     " gcc49=$(ls -1 build/fid/gcc49/*.o 2>/dev/null | wc -l)" \
     " gcc62=$(ls -1 build/fid/gcc62/*.o 2>/dev/null | wc -l)"

# ---- 对拍 ------------------------------------------------------------------
SETS=""
for cand in clang gcc49 gcc62; do
    [ -d "build/fid/$cand" ] && [ -n "$(ls -A build/fid/$cand 2>/dev/null)" ] && SETS="$SETS --set $cand=build/fid/$cand"
done
if [ -z "$SETS" ]; then
    echo "★★ 没有任何候选产出对象 —— 仪器不可用，硬失败" >&2
    exit 11
fi

echo
echo "======================= 对拍 ======================="
# shellcheck disable=SC2086
python3 tools/fidelity_compare.py $SETS | tee report/fidelity_matrix.txt
rc=$?

{
  echo
  echo "======================= 结论口径 ======================="
  echo "  · 本实验的**唯一变量是编译器**；flags 全部取自目标程序自带的 DWARF（$OPT $ARCHF）。"
  echo "  · 若 gcc62/gcc49 的「±15% 命中」与「直方图 L1 中位」同时优于 clang"
  echo "    ⇒ **工具链对齐是有效的整类优化**，下一步把主构建的 CC 切到同款工具链。"
  echo "  · 体积比/直方图**不是功能进度尺**（GAP 16.43）：这里只用于「同输入下谁更像工厂」的相对判断。"
  echo "  · 任一候选 UNAVAILABLE 都必须保留在表里（「没跑」不等于「跑了但输了」）。"
} >> report/fidelity_matrix.txt

# 把工具链身份写进产物（可复核：下次谁改了这一行就是口径漂移）
{
  echo
  echo "======================= 候选身份 ======================="
  cat "$RESULTS"
  if [ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ]; then
    echo "--- clang ---"; "$ZIGBIN" cc --version 2>&1 | head -2
  fi
  for d in cache_tc/linaro-4.9-2016.02 cache_tc/linaro-6.2-2016.11; do
    if [ -x "$d/bin/arm-linux-gnueabihf-gcc" ]; then
      echo "--- $d ---"; "$d/bin/arm-linux-gnueabihf-gcc" --version | head -2
    fi
  done
} >> report/fidelity_matrix.txt

echo
echo "→ 已写入 report/fidelity_matrix.txt"
exit $rc
