#!/bin/sh
# ============================================================================
# upstream_cc_probe.sh —— 「上游库 · 纯编译器」判决实验
#
# ## 问的问题（只有这一句）
#   「把**上游单头库**（没有被我们重建过的那部分）换编译器，机器码会不会更接近工厂？」
#
# ## 为什么要单独做（补第 99 轮 fid 矩阵的盲区）
#   第 99 轮的 `fidelity_matrix.sh` 样本 = **213 个「我们重建的 TU」**，
#   里面同时含 (a) 编译器差异、(b) 重建 C 与工厂原 C 的差异。
#   ⇒ 「换编译器没用」这个结论**无法排除**「重建误差把信号淹了」。
#
#   **上游库是干净样本**：`src/upstream/stb/stb_truetype.h` 是原版上游源码，
#   我们**没有重建它**；版本也已单独排除（v1.20~v1.23 四版编译产物几乎完全相同，
#   而工厂的 `stbtt_Rasterize`=1244 比四版的 6084 小 4.9 倍）⇒ 唯一变量 = 编译器。
#
# ## 预登记判据（先写下再跑；判负也是交付物）
#   M1 = 体积完全相同（st_size 相等）的共有函数个数  —— 越大越像
#   M2 = 体积比中位（候选/工厂）                     —— 越接近 1.000 越像
#   M3 = 工厂独有函数个数（我方把它们内联掉了）      —— 越小越像
#   M4 = 候选独有函数个数                            —— 越小越像
#   ⇒ 某真 GCC 候选 M1 显著高于 clang 且 M2 更接近 1.000 且 M3/M4 不劣
#      ⇒ **上游库应改用该编译器**（可隔离杠杆成立）
#   ⇒ 全部与 clang 相当 ⇒ 上游库差异另有原因（不是编译器）
#
# ## 运行位置
#   **Linux 专属**（GCC 臂是 x86-64 Linux ELF；本机 Windows 无法执行）。
#   用户口径：不在本机搭环境 ⇒ 一律在 CI / CNB 云开发跑。
#   ★ 本脚本**只编译不链接**（绕开跨工具链 libc 符号冲突），很快（一个 .o）。
#
# 用法：PY=<venv>/python sh tools/upstream_cc_probe.sh [--with-bootlin]
# 输出：report/upstream_cc_probe.txt
# exit: 0 = 至少 2 个候选产出对象且比对完成 / 4 = 非 Linux / 11 = 仪器不可用
# ============================================================================
set -u

if [ "$(uname -s 2>/dev/null)" != "Linux" ]; then
    echo "★★ upstream_cc_probe.sh 是 **Linux 专属**：GCC 臂是 x86-64 Linux ELF，Windows 上" >&2
    echo "   "Exec format error"，只会得到残缺判决。用户口径：不在本机搭环境。" >&2
    echo "   ⇒ 请在 CI / CNB 云开发（Linux）上运行。" >&2
    exit 4
fi

PY="${PY:-python3}"
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT" || exit 11
mkdir -p report build/_upcc

SRC=src/upstream/stb/stb_truetype_impl.c
if [ ! -f "$SRC" ]; then echo "★ 缺 $SRC" >&2; exit 11; fi

# flags 逐字取自工厂 DWARF（见 report/dwarf_recon.txt）
OPT="-O2"
ARMF="-march=armv7-a -mfloat-abi=hard -mfpu=neon"
EXTRA="-std=gnu11 -fgnu89-inline -fmerge-all-constants -fno-stack-protector -fomit-frame-pointer -frounding-math"

ZIGBIN="${ZIGBIN:-}"
if [ -z "$ZIGBIN" ]; then
    ZIGBIN=$("$PY" -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)
fi
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$ROOT/build/_zigcache_fid}"

OUT=report/upstream_cc_probe.txt
LOG=build/_upcc/_probe.log
: > "$LOG"

SPECS=""
n_cand=0

echo "======================= 编译（只编译不链接）======================="

# ---- 1) clang（zig cc）—— 现状基线 ----
if [ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ]; then
    # zig 的 ARM CPU 表用下划线（实测 cortex-a8 会报 unknown CPU）
    if "$ZIGBIN" cc -c "$OPT" -w -target arm-linux-gnueabihf $ARMF -mtune=cortex_a8 $EXTRA \
            "$SRC" -o build/_upcc/clang.o 2>build/_upcc/_e_clang.txt; then
        echo "  clang      : OK    $("$ZIGBIN" cc --version 2>&1 | head -1)"
        SPECS="$SPECS clang=build/_upcc/clang.o"; n_cand=$((n_cand+1))
    else
        echo "  clang      : FAIL"; head -3 build/_upcc/_e_clang.txt
    fi
else
    echo "  clang      : 无 zig（跳过）"
fi

# ---- 2) 发行版 ARM GCC（真 GCC 家族；版本与工厂不同，报告里注明）----
SYSGCC=""
for c in arm-linux-gnueabihf-gcc arm-linux-gnueabihf-gcc-12 arm-linux-gnueabihf-gcc-13 \
         arm-linux-gnueabihf-gcc-11; do
    if command -v "$c" >/dev/null 2>&1; then SYSGCC=$c; break; fi
done
if [ -n "$SYSGCC" ]; then
    if "$SYSGCC" -c "$OPT" -w $ARMF -mtune=cortex-a8 $EXTRA "$SRC" \
            -o build/_upcc/sysgcc.o 2>build/_upcc/_e_sysgcc.txt; then
        echo "  sysgcc     : OK    $("$SYSGCC" --version 2>&1 | head -1)"
        SPECS="$SPECS sysgcc=build/_upcc/sysgcc.o"; n_cand=$((n_cand+1))
    else
        echo "  sysgcc     : FAIL"; head -3 build/_upcc/_e_sysgcc.txt
    fi
else
    echo "  sysgcc     : 未安装（CI 需 apt-get install gcc-arm-linux-gnueabihf）"
fi

# ---- 3) bootlin63（GCC 6.3 / glibc 2.24 / binutils 2.27，与工厂最同族）----
#    ★ 复用 fidelity_matrix.sh 下好的缓存，不重复下载。
TC=cache_tc/bootlin63
if [ -d "$TC" ]; then
    B63=""
    for g in "$TC"/bin/*-gcc.br_real "$TC"/bin/*-gcc; do
        [ -f "$g" ] || continue
        case "$g" in *-gcc-[0-9]*) continue ;; esac
        B63=$g; break
    done
    SR="$TC/arm-buildroot-linux-gnueabihf/sysroot"
    if [ -n "$B63" ]; then
        if "$B63" -c "$OPT" -w --sysroot="$SR" $ARMF -mtune=cortex-a8 $EXTRA "$SRC" \
                -o build/_upcc/bootlin63.o 2>build/_upcc/_e_b63.txt; then
            echo "  bootlin63  : OK    $("$B63" --version 2>&1 | head -1)"
            SPECS="$SPECS bootlin63=build/_upcc/bootlin63.o"; n_cand=$((n_cand+1))
        else
            echo "  bootlin63  : FAIL"; head -3 build/_upcc/_e_b63.txt
        fi
    else
        echo "  bootlin63  : 缓存目录在但找不到 *-gcc"
    fi
else
    echo "  bootlin63  : 无缓存（先跑 tools/fidelity_matrix.sh 会下好）"
fi

if [ "$n_cand" -lt 2 ]; then
    echo "★★ 只有 $n_cand 个候选产出对象 ⇒ 判据不成立（无法比较），拒绝给结论" >&2
    exit 11
fi

echo
echo "======================= 比对（与工厂 stbtt* 函数）======================="
# shellcheck disable=SC2086
"$PY" tools/upstream_cc_compare.py --prefix stbtt --factory golden/factory.rkgame.bin $SPECS \
    > "$OUT" 2>&1
rc=$?
cat "$OUT"

{
    echo
    echo "======================= 候选身份（口径可复核）======================="
    echo "  flags: $OPT $ARMF -mtune=cortex-a8 $EXTRA   （取自工厂 DWARF；clang 组去掉 -mtls-dialect=gnu）"
    echo "  样本 : $SRC（上游 v1.26 源码，**未被重建**）"
    echo "  版本 : 已单独排除 —— v1.20/v1.21/v1.22/v1.23 四版编译产物几乎完全相同"
    echo "         （stbtt_FindGlyphIndex=632、stbtt_Rasterize=6084 四版一致；工厂是 848 / 1244）"
    echo "  ★ 本表只回答「谁更像工厂」，不构成功能进度尺（GAP 16.43）。"
} >> "$OUT"

echo
echo "→ 已写入 $OUT"
exit $rc
