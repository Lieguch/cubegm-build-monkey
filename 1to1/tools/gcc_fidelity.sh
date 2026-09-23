#!/bin/sh
# ============================================================================
# gcc_fidelity.sh —— 判决实验：**同一份源码，换编译器，谁更接近工厂？**
#
# 背景（ROUTE-DECISION.md §五④）：工厂指纹 = GCC 6.2.0 + GNU gold；
#   我们 = zig(zig cc → clang) + lld。差异是**跨编译器家族**的，不是版本号。
#   本项目自带装 gcc-arm-linux-gnueabihf 的能力（cnb_env.sh [1/7]），但**从未用过**。
#
# 设计（单变量）：
#   · 两组**完全相同**的 CFLAGS，**唯一差别是编译器**
#   · 只编译不链接 ⇒ 绕开"GCC 对象 + zig 链接"的 glibc 符号冲突（cnb_env.sh 已记录该坑）
#   · 用同一个反汇编器、同一份工厂数据对拍（tools/fidelity_compare.py）
#
# 输出：report/gcc_fidelity.txt
# exit: 0 = 两组都编出来且比较完成 / 1 = 比较器报错 / 11 = 仪器不可用（编译器缺失等）
# ============================================================================
set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 11
mkdir -p report build/gcc_obj build/clang_obj

OPT="${OPT:--Os}"
FIDELITY="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
COMMON="-c $OPT -w -Wno-error=implicit-function-declaration -I$ROOT/src/compat $FIDELITY"

GCC_BIN="${GCC_BIN:-arm-linux-gnueabihf-gcc}"
if ! command -v "$GCC_BIN" >/dev/null 2>&1; then
    echo "★★ 找不到 $GCC_BIN —— 仪器不可用，硬失败（不允许『没有 GCC 就直接跳过』）" >&2
    exit 11
fi

# zig（clang 侧）：优先 python -m ziglang，其次环境变量 ZIGBIN
ZIGBIN="${ZIGBIN:-}"
if [ -z "$ZIGBIN" ] && command -v python3 >/dev/null 2>&1; then
    ZIGBIN=$(python3 -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)
fi
if [ -z "$ZIGBIN" ] || [ ! -x "$ZIGBIN" ]; then
    echo "★★ 找不到 zig —— 仪器不可用，硬失败（clang 侧无法同口径对比）" >&2
    exit 11
fi
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-/tmp/zigcache_fid}"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR"

echo "======================= 仪器 ======================="
echo "  GCC   : $($GCC_BIN --version | head -1)"
echo "  clang : $($ZIGBIN cc --version 2>&1 | head -1)   （zig $($ZIGBIN version)）"
echo "  OPT   : $OPT"
echo "  工厂  : .comment 期望值 = \"GCC: (GNU) 6.2.0\" + gold 1.12（见 ROUTE-DECISION 3.1）"
echo

rm -f build/gcc_obj/*.o build/clang_obj/*.o
gok=0; gbad=0; cok=0; cbad=0
: > report/_gcc_first_err.txt
: > report/_clang_first_err.txt

for f in "$ROOT"/src/proprietary/*/*.c; do
    [ -f "$f" ] || continue
    b=$(basename "$f"); stem=${b%.c}

    if $GCC_BIN   $COMMON -march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic \
                  "$f" -o "build/gcc_obj/$stem.o" 2>>report/_gcc_first_err.txt; then
        gok=$((gok + 1))
    else
        gbad=$((gbad + 1)); rm -f "build/gcc_obj/$stem.o"
    fi

    if $ZIGBIN cc $COMMON -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon \
                  "$f" -o "build/clang_obj/$stem.o" 2>>report/_clang_first_err.txt; then
        cok=$((cok + 1))
    else
        cbad=$((cbad + 1)); rm -f "build/clang_obj/$stem.o"
    fi
done

echo "======================= 编译 ======================="
echo "  GCC   : 成功 $gok / 失败 $gbad"
echo "  clang : 成功 $cok / 失败 $cbad"
if [ "$gbad" -gt 0 ] || [ "$cbad" -gt 0 ]; then
    echo "  --- 失败前 8 条（GCC 侧）---"; grep -aE 'error' report/_gcc_first_err.txt | head -8
    echo "  --- 失败前 8 条（clang 侧）---"; grep -aE 'error' report/_clang_first_err.txt | head -8
fi
if [ "$gok" -eq 0 ] || [ "$cok" -eq 0 ]; then
    echo "★★ 有一侧一个对象都没产出 —— 仪器不可用，硬失败" >&2
    exit 11
fi
echo

# 收敛到**同一子集**（两侧都编成功的文件），避免"幸存者偏差"。
# ★ 必须 POSIX（CI 的 /bin/sh 是 dash，不支持 <(...) 进程替换）。
BOTH=0
for o in build/gcc_obj/*.o; do
    [ -f "$o" ] || continue
    b=$(basename "$o")
    if [ -f "build/clang_obj/$b" ]; then
        BOTH=$((BOTH + 1))
    else
        rm -f "$o"
    fi
done
for o in build/clang_obj/*.o; do
    [ -f "$o" ] || continue
    b=$(basename "$o")
    [ -f "build/gcc_obj/$b" ] || rm -f "$o"
done
echo "  两组都编出的文件数（同子集）= $BOTH"
if [ "$BOTH" -eq 0 ]; then
    echo "★★ 同子集为空 —— 仪器不可用，硬失败" >&2
    exit 11
fi
echo

echo "======================= 对拍（同一个反汇编器 / 同一份工厂数据）======================="
PY="${PY:-python3}"
$PY tools/fidelity_compare.py --set clang=build/clang_obj --set gcc=build/gcc_obj
rc=$?
echo
echo "======================= 判读 ======================="
echo "  · 若 gcc 的「±15% 命中」与「直方图 L1 中位」同时优于 clang ⇒ 换工具链是有价值的整类优化："
echo "    下一步把 CC 切到同族 GCC 并重跑全部门禁（link_audit/link_full/elf_load/relro/mmio_*/…）"
echo "  · 若不优 ⇒ **排除一个变量**：主线仍走 ROUTE-DECISION §五①②（volatile 整块 + 访问原语 + 沙箱复现）"
echo "  · 声明：体积比**不是功能进度尺**（GAP 16.43）。这里只用于「同输入下两个编译器谁更像工厂」的**相对**判断。"
exit $rc
