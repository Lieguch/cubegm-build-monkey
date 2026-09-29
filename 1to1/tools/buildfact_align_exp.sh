#!/bin/sh
# =============================================================================
# 构建事实对齐实验（2026-09-28，v2：修正头集合顺序）
#
# 已由单变量实测钉死的三条工厂事实（见 BUILD-FACT-ALIGNMENT.md）：
#   1. 真 glibc 2.24 头（`putc`→`_IO_putc`、`getc`→`_IO_getc`）
#   2. 优化档 ≥-O1 且非 -Os（`strdup`→`__strdup`）
#   3. GCC 不做 `strcmp(x,"lit")==0` → `bcmp` 的变换，clang 会做 ⇒ 需 `-fno-builtin-strcmp`
#
# 头集合顺序（两次失败换来的，不可随意调整）：
#   组件自己的头 → GCC include → GCC include-fixed → sysroot/usr/include
#   理由见 build/_attic/_patch_hdr_order.py 的模块注释。
#
# 臂：
#   A = 真头 + 现优化档（专有 -Os / 上游 -O1 / libiconv -O0）
#   B = 真头 + -O2（专有与上游）+ -fno-builtin-strcmp（libiconv 保持 -O0）
#
# 用法: sh tools/buildfact_align_exp.sh [A|B|AB]
# =============================================================================
set -u
cd /d/output/rkgame-1to1 || exit 9
WHICH="${1:-AB}"
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
CC="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe cc"
ROOT="$PWD"
# ★ 缓存目录**按臂隔离**：实测 8 路并行编译共享同一全局缓存会报
#   `error: CacheCheckFailed`（zig 缓存竞态）⇒ 对象未产出 ⇒ 下游链接迷惑。
export ZIG_GLOBAL_CACHE_DIR="$ROOT/build/_zigcache_bfa2_${CACHE_TAG:-A}"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR" report build/ab

TB="$ROOT/cache_tc/bootlin63"
TC="$TB/arm-buildroot-linux-gnueabihf/sysroot"
GI="$TB/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include"
GIF="$TB/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include-fixed"
GD="$TC/usr/include"
for d in "$GD/stdio.h" "$GI/stddef.h" "$GIF/limits.h"; do
    [ -f "$d" ] || { echo "!! 缺真工具链头：$d" >&2; exit 3; }
done
# ★ 额外头集合：GCC 原生顺序（GCC include → include-fixed → sysroot/usr/include），
#   且**尾置**在组件自己的 `-I` 之后（见脚本头注释）。
HDR="-nostdinc -I$GI -I$GIF -I$GD"

ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"
FID="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"

# 专有对象（并行 8 路）  $1=优化档 $2=额外 flags $3=输出目录
build_prop() {
    opt="$1"; extra="$2"; out="$3"
    mkdir -p "$out"; : > "report/_bfa2_err_$(basename "$out").txt"
    CFLAGS="-c $opt -w -Wno-error=implicit-function-declaration -I$ROOT/src/compat $HDR $extra $ARCH $FID"
    export CCZ="$CC" CFLAGS
    find "$ROOT/src/proprietary" -name '*.c' -print0 \
      | xargs -0 -P 8 -I{} sh -c 'b=$(basename "$1" .c); $CCZ $CFLAGS "$1" -o "'"$out"'/$b.o" 2>>report/_bfa2_err_'"$(basename "$out")"'.txt' _ {}
    n=$(ls -1 "$out"/*.o 2>/dev/null | wc -l)
    echo "   专有对象 $n/213  ($opt $extra)"
    [ "$n" -ge 200 ] || { echo "  ★★ 编译失败过多"; head -6 "report/_bfa2_err_$(basename "$out").txt"; return 5; }
}

# XUnzip  $1=优化档 $2=额外 flags $3=输出
build_xu() {
    $CC -x c++ -c "$1" -w -Wno-error=implicit-function-declaration -I"$ROOT/src/upstream/xunzip/posix" \
        -I$ROOT/src/compat $HDR "$2" $ARCH $FID -std=gnu++98 -fno-exceptions \
        "$ROOT/src/upstream/xunzip/unzip.cpp" -o "$3" 2>>report/_bfa2_xu.txt
    echo "   XUnzip $(stat -c%s "$3" 2>/dev/null || echo 0) B ($1 $2)"
}

# 链接 + 尺子  $1=专有目录 $2=上游目录 $3=XUnzip $4=输出
link_and_judge() {
    DIAG_OBJD="$1" UPOBJD="$2" DIAG_XUNZIP="$3" \
        CC="$CC" SYSROOT="" PY="$PY" sh tools/link_full.sh "$4" > "report/_bfa2_link_$(basename "$4").txt" 2>&1
    rc=$?
    echo "   link rc=$rc size=$(stat -c%s "$4" 2>/dev/null || echo 0)"
    [ "$rc" = "0" ] && [ -s "$4" ] || { echo "   ★★ 链接失败"; tail -10 report/link_full_err.txt; return 5; }
    "$PY" tools/probe_link_binding.py "$4" 2>&1 | head -3
    "$PY" tools/diff_exec.py --batch --steps 3000 --ours "$4" \
        --out "report/_bfa2_diff_$(basename "$4" .elf).txt" > /dev/null 2>&1
    grep -a "汇总：PASS\|自洽校验" "report/_bfa2_diff_$(basename "$4" .elf).txt" | head -2
}

if [ "$WHICH" = "AB" ] || [ "$WHICH" = "A" ]; then
echo "############ 臂 A：真头 + 现优化档 ############"
build_prop -Os "" "$ROOT/build/bfa2_obj_A" || exit 5
build_xu -Os "" "$ROOT/build/bfa2_xu_A.o"
EXTRA_INC_TRAIL="$HDR" UPOPT=-O1 LIBOPT=-O0 \
    CC="$CC" PY="$PY" SYSROOT="" sh tools/build_upstream.sh "$ROOT/build/bfa2_up_A" > report/_bfa2_up_A.txt 2>&1
echo "   上游对象 $(ls -1 build/bfa2_up_A/*.o 2>/dev/null | wc -l)/25  $(grep -a FAIL report/_bfa2_up_A.txt | head -2)"
link_and_judge "$ROOT/build/bfa2_obj_A" "$ROOT/build/bfa2_up_A" "$ROOT/build/bfa2_xu_A.o" "$ROOT/build/ab/bfa2_A.elf"
fi

if [ "$WHICH" = "AB" ] || [ "$WHICH" = "B" ]; then
echo
echo "############ 臂 B：真头 + -O2 + -fno-builtin-strcmp ############"
build_prop -O2 "-fno-builtin-strcmp" "$ROOT/build/bfa2_obj_B" || exit 5
build_xu -O2 "-fno-builtin-strcmp" "$ROOT/build/bfa2_xu_B.o"
EXTRA_INC_TRAIL="$HDR" UPOPT=-O2 LIBOPT=-O0 \
    CC="$CC" PY="$PY" SYSROOT="" sh tools/build_upstream.sh "$ROOT/build/bfa2_up_B" > report/_bfa2_up_B.txt 2>&1
echo "   上游对象 $(ls -1 build/bfa2_up_B/*.o 2>/dev/null | wc -l)/25  $(grep -a FAIL report/_bfa2_up_B.txt | head -2)"
link_and_judge "$ROOT/build/bfa2_obj_B" "$ROOT/build/bfa2_up_B" "$ROOT/build/bfa2_xu_B.o" "$ROOT/build/ab/bfa2_B.elf" 2>&1 | grep -v "单侧未建模\|已登记\|★★ 出现\|要么补进\|★★ 单侧未建模"
fi

if [ "$WHICH" = "C" ]; then
echo
echo "############ 臂 C：**per-TU 优化档**（证据推导）+ 真头 + -fno-builtin-strcmp ############"
echo "   依据（BUILD-FACT-ALIGNMENT.md §七）：工厂同时导入 putchar(需要 extern-inline 关)"
echo "   与 __strdup(需要 extern-inline 开) ⇒ **应用 -Os / 上游 -O2**，不是单一档。"
build_prop -Os "-fno-builtin-strcmp" "$ROOT/build/bfa3_obj_C" || exit 5
build_xu -O2 "-fno-builtin-strcmp" "$ROOT/build/bfa3_xu_C.o"
EXTRA_INC_TRAIL="$HDR" UPOPT=-O2 LIBOPT=-O0 \
    CC="$CC" PY="$PY" SYSROOT="" sh tools/build_upstream.sh "$ROOT/build/bfa3_up_C" > report/_bfa3_up_C.txt 2>&1
echo "   上游对象 $(ls -1 build/bfa3_up_C/*.o 2>/dev/null | wc -l)/25  $(grep -a FAIL report/_bfa3_up_C.txt | head -2)"
link_and_judge "$ROOT/build/bfa3_obj_C" "$ROOT/build/bfa3_up_C" "$ROOT/build/bfa3_xu_C.o" "$ROOT/build/ab/bfa3_C.elf" 2>&1 | grep -v "已登记\|★★ 出现\|要么补进\|★★ 单侧未建模"
fi

echo
echo "############ 判决 ############"
for tag in A B; do
    f="report/_bfa2_diff_bfa2_$tag.txt"
    [ -f "$f" ] && printf '   %s: %s\n' "$tag" "$(grep -a '汇总：PASS' "$f" | head -1)"
done
echo "   基线（纪律 50：不硬编码，用 python3 tools/ruler_baseline.py 取；以下为取值示例）"
echo "   ★ 基线请以 tools/ruler_baseline.py 的输出为准（随产物 sha 自失效）"
echo DONE
