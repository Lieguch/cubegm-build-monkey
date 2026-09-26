#!/bin/sh
# ============================================================================
# toolchain_ab.sh —— 工具链 A/B 判决（**用行为尺判，不用代理指标判**）
#
# 为什么重做这个实验（第 66 轮）：
#   旧 `fidelity_matrix.sh` 用**体积比 / 助记符直方图**判"谁更像工厂"——那是**代理指标**
#   （GAP 16.43 已明确它不是功能进度尺）。而本项目手里本来就有一把**行为尺**：
#   `tools/diff_exec.py --batch`（qemu 差分执行，逐函数比 观测量/访存/调用/终止）。
#   ⇒ 判决改为：「同一份源码，换工具链重编，谁的 **DIVERGE 更少**」。
#
# 单变量保证：
#   · 两侧**同一份源码**、同一份 `linker/factory.ld`、同一组 flags
#     （flags 逐字取自工厂 DWARF：-O2 -march=armv7-a -mfloat-abi=hard -mfpu=neon
#      -mtune=cortex-a8 -std=gnu11 -fgnu89-inline -fmerge-all-constants
#      -fno-stack-protector -fomit-frame-pointer -ftls-model=initial-exec -frounding-math）；
#   · 唯一变量 = 编译器（zig/clang 21  vs  Buildroot-GCC 6.3.0 + glibc 2.24 + binutils 2.27）。
#
# 为什么 bootlin63 是对照腿：
#   工厂真值（DWARF + 产物自带 summary.csv 双向核对）= GCC 6.2.0 / **glibc 2.24** /
#   **binutils 2.27** / gold 1.12；bootlin63 = GCC **6.3.0** / glibc **2.24** /
#   binutils **2.27**（唯一差异 = GCC 次版本）。
#   ★ 关键：我们**现在**的构建是 `-target arm-linux-gnueabihf.2.7` ⇒ 编译头是 **glibc 2.7**，
#     与工厂的 2.24 不同 —— 这正是 ctype 宏展开 / `__strdup` vs `strdup` / `_chk` 变体
#     那一整类差异的来源（GAP 17.16、17.18）。
#
# 用法：  PY=<python> sh tools/toolchain_ab.sh
# 输出：  report/toolchain_ab.txt
# exit: 0 = 两条腿都量到 / 11 = 无可用工具链
# ============================================================================
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 11
PY="${PY:-python3}"
ZIG="${ZIG:-}"
if [ -z "$ZIG" ]; then
    ZIG=$("$PY" -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)
fi
mkdir -p report build/ab

TC=cache_tc/bootlin63
BB="https://toolchains.bootlin.com/downloads/releases/toolchains/armv7-eabihf/tarballs"
TC_URL="$BB/armv7-eabihf--glibc--bleeding-edge-2017.05-toolchains-1-1.tar.bz2"

# flags：逐字取自工厂 DWARF（见 tools/dwarf_recon.py）。`-mtune` 两种拼写：
#   GCC 用 cortex-a8；zig/LLVM 的 ARM CPU 表用下划线 cortex_a8（实测写 cortex-a8 会报
#   `unknown CPU: 'cortex'`）。
FID_BASE="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"

# ---- ★★ 默认值区（`set -u` 下**所有**外部可覆盖变量必须在此统一给默认）----
#   为什么：本脚本曾在"预检块"里引用 `$AB_ONLY`，而它的默认值写在**后面**的腿 A 段
#   ⇒ `AB_ONLY: parameter not set` ⇒ exit 2 ⇒ 一次 CI 白跑（只暴露一个比特）。
#   同型缺陷上一轮已在 `ZIGBIN` 上出现过一次 ⇒ 现在改为**集中声明 + 机械 lint**双保险。
AB_ONLY="${AB_ONLY:-both}"
GLIBC_VER="${GLIBC_VER:-2.7}"
SYSROOT="${SYSROOT:-}"
FID_JOBS="${FID_JOBS:-}"

RES=report/_ab_results.txt
: > "$RES"
OUT=report/toolchain_ab.txt
: > "$OUT"

say() { echo "$@" | tee -a "$OUT"; }

# ---- 取对照工具链 -----------------------------------------------------------
ensure_tc() {
    # ★ `.ok` 由 `touch` 创建（0644）⇒ 判定必须用 `-f`，`-x` 永远不命中（会重复下载）。
    [ -f "$TC/.ok" ] && return 0
    if [ ! -s "$TC.tar.bz2" ]; then
        echo "  下载 bootlin63（约 64 MB）..."
        curl -fsSL --retry 3 --retry-delay 2 --max-time 900 -o "$TC.tar.bz2" "$TC_URL" || return 1
    fi
    rm -rf "$TC"; mkdir -p "$TC"
    tar -xjf "$TC.tar.bz2" -C "$TC" --strip-components=1 || return 1
    touch "$TC/.ok"
}

# ---- 量一条腿 ---------------------------------------------------------------
# $1=标签 $2=产物路径
measure() {
    lab=$1; elf=$2
    if [ ! -s "$elf" ]; then
        say "  $lab : ★ 构建失败（无产物）"
        echo "$lab BUILD_FAILED" >> "$RES"
        return 1
    fi
    sha=$("$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$elf")
    sz=$(stat -c%s "$elf")
    # ① ABI 门禁（GLIBC 运行时下限必须 ≤ 工厂）
    "$PY" tools/abi_check.py "$elf" > "report/_ab_abi_$lab.txt" 2>&1
    abi=$?
    # ② 行为尺（**判决用**）
    "$PY" tools/diff_exec.py --batch --steps 3000 --ours "$elf" \
        --out "report/_ab_diff_$lab.txt" > "report/_ab_diff_${lab}_stdout.txt" 2>&1
    line=$(grep -a '汇总：PASS' "report/_ab_diff_$lab.txt" 2>/dev/null | head -1 | sed 's/^ *//')
    say "  $lab : size=$sz abi_rc=$abi  $line"
    echo "$lab sha256=$sha size=$sz abi_rc=$abi | $line" >> "$RES"
    return 0
}

say "======================= 工具链 A/B（判决尺 = diff_exec 行为差分）======================="
say "  源文件数 = $(ls -1 src/proprietary/*/*.c 2>/dev/null | wc -l)"
say "  工厂真值：GCC 6.2.0 / glibc 2.24 / binutils 2.27 / gold 1.12（DWARF 恢复）"
say ""

# ---- 预检（fail-closed，**必须在花钱之前**）--------------------------------
# 为什么放这里：切到真实 glibc 2.24 时，凡"我们声明了、glibc 也声明了"的名字都可能撞车
# （`__timezone_ptr_t` 就是这么撞的：我们缺 `__restrict` ⇒ conflicting type qualifiers）。
# 一次 CI 只暴露一个 ⇒ 先在本步把**全部同名声明**对拍完，再决定要不要编译。
say "======================= 预检（编译之前 fail-closed）======================="
if [ "$AB_ONLY" = "both" ] || [ "$AB_ONLY" = "gcc63" ]; then
    if ensure_tc; then
        SR_TC=$(ls -d "$TC"/*/sysroot 2>/dev/null | head -1)
        say "  ① 声明文本双向自证（含两个缺陷态反例）"
        # ★ 不写死 `CC=cc`：本机 Windows 无 cc/gcc/clang（探针自带 pick_cc 会兜到 $ZIG）。
        SYSROOT="$SR_TC" ZIG="$ZIG" sh tools/glibc_compat_probe.sh --selftest \
            > build/_ab_pre1.txt 2>&1
        rc1=$?
        sed 's/^/    /' build/_ab_pre1.txt | tee -a "$OUT"
        if [ "$rc1" != "0" ]; then
            # ★ 必须分辨原因：1=声明不一致（我们的问题）/ 2=不可判（仪器或环境的问题）。
            #   混成一句话会让下一轮查错方向（本轮就写错过一次）。
            case "$rc1" in
              1) say "  ★★ 预检失败【声明不一致】：compat 的声明与 glibc 原文不同 ⇒ 停在此处";;
              2) say "  ★★ 预检【不可判】：宿主编译器不可用（见上）⇒ fail-closed，停在此处";;
              *) say "  ★★ 预检失败【rc=$rc1，原因未登记】⇒ fail-closed，停在此处";;
            esac
            exit 1
        fi
        say "  ② 全量同名声明对拍（我方 vs 真实 sysroot）"
        "$PY" tools/compat_vs_glibc.py --out report/compat_vs_glibc.txt \
            | sed 's/^/    /' | tee -a "$OUT"
        if [ "$("$PY" tools/compat_vs_glibc.py >/dev/null 2>&1; echo $?)" = "1" ]; then
            say "  ★★ 预检失败：存在 MISMATCH（见 report/compat_vs_glibc.txt）⇒ 停在此处"
            exit 1
        fi
        say "  预检通过：无同名冲突风险 ⇒ 继续编译"
    else
        say "  ★ 预检跳过：工具链不可用（**不可判，不得当作通过**）"
    fi
fi
say ""

# ---- 腿 A：zig（现状，glibc 头 = 2.7）--------------------------------------
# ★ `AB_ONLY` 只跑指定腿 —— 本机（Windows）跑不了 Linux 版 GCC 工具链，
#   但 zig 腿完全可跑 ⇒ 仪器必须支持"只跑能跑的那条"，否则本机就等于不可用。
if [ "$AB_ONLY" = "both" ] || [ "$AB_ONLY" = "zig" ]; then
say "---- 腿 A：zig cc（GLIBC_VER=${GLIBC_VER:-2.7}，现状）----"
GLIBC_VER="$GLIBC_VER" CC="$ZIG cc" PY="$PY" \
    FIDELITY="$FID_BASE -mtune=cortex_a8" \
    sh tools/link_full.sh build/ab/zig.elf 2>&1 | tail -3 | tee -a "$OUT"
fi

# ---- 腿 B：bootlin63（GCC 6.3.0 + glibc 2.24 + binutils 2.27）----------------
if [ "$AB_ONLY" = "both" ] || [ "$AB_ONLY" = "gcc63" ]; then
say ""
say "---- 腿 B：bootlin63（GCC 6.3.0 / glibc 2.24 / binutils 2.27）----"
if ensure_tc; then
    # ★ 用 `.br_real`（真编译器）而不是 `-gcc`（Buildroot 的 toolchain-wrapper 会按
    #   buildroot.config 注入 `-mcpu=cortex-a9 -mfpu=vfpv3-d16`，与工厂的
    #   `-march=armv7-a -mfpu=neon` 冲突且不可见 ⇒ 必须绕开 wrapper 才能保证单变量）。
    CCB=$(ls "$TC"/bin/*-gcc.br_real 2>/dev/null | head -1)
    SYSROOT_TC=$(ls -d "$TC"/*/sysroot 2>/dev/null | head -1)
    if [ -n "$CCB" ] && [ -n "$SYSROOT_TC" ]; then
        say "  CC      = $CCB"
        say "  SYSROOT = $SYSROOT_TC"
        CC="$CCB" SYSROOT="$SYSROOT_TC" PY="$PY" \
            FIDELITY="$FID_BASE -mtune=cortex-a8" \
            sh tools/link_full.sh build/ab/gcc63.elf 2>&1 | tail -4 | tee -a "$OUT"
    else
        say "  ★ UNAVAILABLE（工具链内没有 *-gcc.br_real 或 sysroot）"
    fi
else
    say "  ★ UNAVAILABLE（下载/解压失败）"
fi
fi   # AB_ONLY

say ""
say "======================= 度量 ======================="
measure zig build/ab/zig.elf
measure gcc63 build/ab/gcc63.elf

say ""
say "======================= 判决表（**只看行为尺**）======================="
say "  读法：DIVERGE 越少越接近工厂。"
say "  · gcc63 的 DIVERGE **显著少于** zig ⇒ 工具链对齐是有效的整类优化 ⇒ 主构建切 CC。"
say "  · 两者接近 ⇒ 差异不来自 libc 头/编译器族，须回 GAP 17.19（上游库版本错配）另找。"
say "  · ABI 门禁 rc≠0 的腿**一律不得采用**（会在设备上 GLIBC_* not found 起不来）。"
say ""
say "  ---- 原始记录 ----"
cat "$RES" | tee -a "$OUT"

say ""
say "→ 已写入 $OUT"
[ -s build/ab/zig.elf ] || exit 11
exit 0
