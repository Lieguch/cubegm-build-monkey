#!/bin/sh
# ============================================================================
# toolchain_ab.sh —— 工具链 A/B 判决（**用行为尺判**：diff_exec 的 DIVERGE 数）
#
# 为什么重做（第 66 轮）：
#   旧 `fidelity_matrix.sh` 用**体积比 / 助记符直方图**判"谁更像工厂"——那是**代理指标**
#   （GAP 16.43 已认定它不是功能进度尺）。本项目手里本来就有行为尺（qemu 差分执行），
#   判决应写成：**同一份源码、同一组 flags，只换编译器/优化级别，谁的 DIVERGE 更少。**
#
# ★★ 单变量前提（第 66 轮订正）：**必须整条编译链一起换**
#   本仓的链接步骤（`link_full.sh`）是**纯链接**：它只把 `build/obj/*.o`（213 个专有函数）
#   + `build/upstream/*.o`（stb/mxml/mp3/libiconv）+ 工厂数据镜像链起来。
#   产出 `build/obj/*.o` 的**唯一**脚本是 `tools/link_audit.sh`，上游对象由
#   `tools/build_upstream.sh` 产出。
#   ⇒ 只换 `link_full.sh` 的 CC 是**假单变量**（首次 CI 实测即 `undefined symbol: main`）。
#
# 腿（`AB_LEGS` 可覆盖）：
#   zig-Os     现状：zig/clang 21 + glibc **2.7** 头 + `-Os`
#   gcc63-Os   Bootlin GCC 6.3.0 + glibc **2.24** + binutils 2.27 + `-Os`
#   gcc63-O2   同上，但 `-O2` —— **工厂 DWARF 的 `DW_AT_producer` 写的是 `-O2`**，
#              而 `-Os` 是当年按**体积比**（代理指标）选定的 ⇒ 用行为尺复核。
#
# 工厂真值（DWARF + 产物自带 summary.csv 双向核对）：
#   GCC 6.2.0 / glibc 2.24 / binutils 2.27 / gold 1.12 / -O2 / -march=armv7-a
#   -mfloat-abi=hard -mfpu=neon -mtune=cortex-a8 -std=gnu11 -fgnu89-inline
#   -fmerge-all-constants -fno-stack-protector -fomit-frame-pointer
#   -ftls-model=initial-exec -frounding-math
#
# 用法：  PY=<python> sh tools/toolchain_ab.sh
#         AB_LEGS=zig-Os sh tools/toolchain_ab.sh        # 只跑一条腿（本机可跑）
# 输出：  report/toolchain_ab.txt
# exit: 0 = 全部腿都量到 / 3 = 缺腿（**不可判，不得当作通过**） / 11 = 仪器不可用
# ============================================================================
set -u

# ---- ★★ 默认值区（`set -u` 下**所有**可外部覆盖变量必须在此统一给默认）------
#   血泪：本脚本曾在"预检块"里引用 `$AB_LEGS`（前身叫 AB_ONLY），而它的默认值写在
#   后面的腿段 ⇒ `parameter not set` ⇒ exit 2 ⇒ 一次 CI 白跑。同型缺陷上一轮已在
#   `ZIGBIN` 上出现过 ⇒ 现在集中声明，并配 `tools/lint_setu_order.py` 机械兜底。
PY="${PY:-python3}"
ZIG="${ZIG:-}"
AB_LEGS="${AB_LEGS:-zig-Os,gcc63-Os,gcc63-O2}"
GLIBC_VER="${GLIBC_VER:-2.7}"
SYSROOT="${SYSROOT:-}"
FID_JOBS="${FID_JOBS:-}"

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 11
# ★ 必须**先建 `cache_tc`**：CI 首跑即因缺此目录而 `curl -o cache_tc/xxx.tar.bz2` 失败
#   （本机恰好已存在该目录 ⇒ 只有 CI 暴露）。
mkdir -p report build/ab cache_tc
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$ROOT/build/_zigcache_ab}"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR"

if [ -z "$ZIG" ]; then
    ZIG=$("$PY" -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)
fi

TC=cache_tc/bootlin63
BB="https://toolchains.bootlin.com/downloads/releases/toolchains/armv7-eabihf/tarballs"
TC_URL="$BB/armv7-eabihf--glibc--bleeding-edge-2017.05-toolchains-1-1.tar.bz2"
DWGCC="$TC/bin/arm-buildroot-linux-gnueabihf-gcc.br_real"
TCSYS=$(ls -d "$TC"/*/sysroot 2>/dev/null | head -1)

# flags：逐字取自工厂 DWARF。`-mtune` 两种拼写：GCC 用 cortex-a8；zig/LLVM 的 ARM
# CPU 表用下划线 cortex_a8（实测写 cortex-a8 会报 `unknown CPU: 'cortex'`）。
FID_BASE="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"

RES=report/_ab_results.txt
: > "$RES"
OUT=report/toolchain_ab.txt
: > "$OUT"

say() { echo "$@" | tee -a "$OUT"; }

# ---- 取对照工具链 -----------------------------------------------------------
ensure_tc() {
    # ★ `.ok` 由 `touch` 创建（0644）⇒ 判定必须用 `-f`，`-x` 永远不命中（会重复下载）。
    [ -f "$TC/.ok" ] && return 0
    mkdir -p cache_tc
    if [ ! -s "$TC.tar.bz2" ]; then
        echo "  下载 bootlin63（约 64 MB）...  url=$TC_URL"
        curl -fsSL --retry 3 --retry-delay 2 --max-time 900 -o "$TC.tar.bz2" "$TC_URL" \
            2>report/_ab_tc.txt
        rc=$?
        if [ "$rc" != "0" ]; then
            echo "   ★★ 下载失败 curl rc=$rc"; sed 's/^/     /' report/_ab_tc.txt | head -6
            echo "     --- 环境事实（URL / 网络 / 磁盘）---"; df -h . 2>/dev/null | head -3
            return 1
        fi
    fi
    echo "  tarball = $(stat -c%s "$TC.tar.bz2" 2>/dev/null) B；解压中 ..."
    rm -rf "$TC"; mkdir -p "$TC"
    tar -xjf "$TC.tar.bz2" -C "$TC" --strip-components=1 2>report/_ab_tc.txt
    rc=$?
    if [ "$rc" != "0" ]; then
        echo "   ★★ 解压失败 tar rc=$rc"; sed 's/^/     /' report/_ab_tc.txt | head -6
        df -h . 2>/dev/null | head -3
        return 1
    fi
    touch "$TC/.ok"
    TCSYS=$(ls -d "$TC"/*/sysroot 2>/dev/null | head -1)
    echo "  工具链就绪：$DWGCC"
}

# ---- 量一条腿 ---------------------------------------------------------------
measure() {
    lab=$1; elf=$2
    if [ ! -s "$elf" ]; then
        say "  $lab : ★ 构建失败（无产物）"
        echo "$lab BUILD_FAILED" >> "$RES"
        return 1
    fi
    sha=$("$PY" -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$elf")
    sz=$(stat -c%s "$elf")
    "$PY" tools/abi_check.py "$elf" > "report/_ab_abi_$lab.txt" 2>&1
    abi=$?
    "$PY" tools/diff_exec.py --batch --steps 3000 --ours "$elf" \
        --out "report/_ab_diff_$lab.txt" > "report/_ab_diff_${lab}_stdout.txt" 2>&1
    line=$(grep -a '汇总：PASS' "report/_ab_diff_$lab.txt" 2>/dev/null | head -1 | sed 's/^ *//')
    say "  $lab : size=$sz abi_rc=$abi  $line"
    echo "$lab sha256=$sha size=$sz abi_rc=$abi | $line" >> "$RES"
    return 0
}

# ---- 构建一条腿（**整条编译链**：link_audit → build_upstream → link_full）----
build_leg() {
    lab=$1; cc=$2; opt=$3; sr=$4
    say ""
    say "---- 腿 $lab：CC=$cc  OPT=$opt  SYSROOT=${sr:-（无）} ----"
    # 每条腿**必须从干净的对象目录开始**，否则腿间互相污染（就不再是单变量）
    rm -rf build/obj build/upstream build/cxx_ops.o build/crt_init.o build/factory_local.o
    mkdir -p build/obj build/upstream

    # ① 专有 213 个函数 → build/obj/*.o（本仓唯一产出该目录的脚本）
    OPT="$opt" CC="$cc" SYSROOT="$sr" sh tools/link_audit.sh "report/_ab_la_$lab.txt" \
        > "report/_ab_compile_$lab.txt" 2>&1
    rc1=$?
    n_obj=$(ls -1 build/obj/*.o 2>/dev/null | wc -l)
    say "  ① link_audit    rc=$rc1  产出对象 $n_obj（期望 213）"
    if [ "$n_obj" -lt 213 ]; then
        say "     ★ 有文件编译失败："
        head -6 report/_link_bad.txt 2>/dev/null | sed 's/^/       /' | tee -a "$OUT"
    fi
    # ② 上游库对象
    CC="$cc" SYSROOT="$sr" PY="$PY" sh tools/build_upstream.sh build/upstream \
        >> "report/_ab_compile_$lab.txt" 2>&1
    rc2=$?
    n_up=$(ls -1 build/upstream/*.o 2>/dev/null | wc -l)
    say "  ② build_upstream rc=$rc2  产出对象 $n_up"
    # ③ 链接
    # ★ 非 zig 腿补 `-lm`：工厂 DT_NEEDED 含 libm.so.6；clang 驱动会自动加，GCC 不会。
    case "$cc" in
      *zig*) ld_extra="" ;;
      *)     ld_extra="-lm" ;;
    esac
    CC="$cc" SYSROOT="$sr" PY="$PY" EXTRA_LDFLAGS="$ld_extra" \
        sh tools/link_full.sh "build/ab/$lab.elf" > "report/_ab_build_$lab.txt" 2>&1
    rc3=$?
    tail -3 "report/_ab_build_$lab.txt" | sed 's/^/     /' | tee -a "$OUT"
    if [ "$rc3" != "0" ] || [ ! -s "build/ab/$lab.elf" ]; then
        say "  ★★ 腿 $lab 构建失败 rc=$rc3 —— 可检索错误行（完整输出见 report/_ab_build_$lab.txt）："
        # ★ 用 `error:`（带冒号）而不是裸 `error`：后者会撞上 `dlerror` 这类**函数名**
        #   ⇒ 报出"看起来像错误"的行，把人引向错方向（本轮实测）。
        grep -aE 'error:|Error|undefined reference|not found|cannot|FATAL' \
            "report/_ab_build_$lab.txt" | head -12 | sed 's/^/     /' | tee -a "$OUT"
        say "     --- 编译失败清单（report/_link_bad.txt：文件 + 首条 error:）---"
        head -12 report/_link_bad.txt 2>/dev/null | sed 's/^/     /' | tee -a "$OUT"
        grep -aE 'error:|undefined reference' "report/_link_err_all.txt" 2>/dev/null \
            | head -8 | sed 's/^/     /' | tee -a "$OUT"
    fi
}

# ---- 预检（fail-closed，**在花钱之前**）-------------------------------------
say "======================= 工具链 A/B（判决尺 = diff_exec 行为差分）======================="
say "  源文件数 = $(ls -1 src/proprietary/*/*.c 2>/dev/null | wc -l)"
say "  工厂真值：GCC 6.2.0 / glibc 2.24 / binutils 2.27 / gold 1.12 / -O2（DWARF 恢复）"
say "  腿       = $AB_LEGS"
say ""
say "======================= 预检（编译之前 fail-closed）======================="
NEED_GCC=0
case ",$AB_LEGS," in *,gcc63-*) NEED_GCC=1 ;; esac
if [ "$NEED_GCC" = "1" ]; then
    if ensure_tc; then
        say "  ① 声明文本双向自证（含两个缺陷态反例）"
        SYSROOT="$TCSYS" ZIG="$ZIG" sh tools/glibc_compat_probe.sh --selftest \
            > build/_ab_pre1.txt 2>&1
        rc1=$?
        sed 's/^/    /' build/_ab_pre1.txt | tee -a "$OUT"
        if [ "$rc1" != "0" ]; then
            # ★ 必须分辨原因：1=声明不一致（我们的问题）/ 2=不可判（仪器或环境的问题）。
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

# ---- 逐腿构建 + 度量 --------------------------------------------------------
OLDIFS=$IFS; IFS=','
for leg in $AB_LEGS; do
    case "$leg" in
      zig-Os)    build_leg "$leg" "$ZIG cc" "-Os" "" ;;
      zig-O2)    build_leg "$leg" "$ZIG cc" "-O2" "" ;;
      gcc63-Os)  build_leg "$leg" "$DWGCC"  "-Os" "$TCSYS" ;;
      gcc63-O2)  build_leg "$leg" "$DWGCC"  "-O2" "$TCSYS" ;;
      *)         say "  ★ 未登记的腿：$leg（跳过）" ;;
    esac
done
IFS=$OLDIFS

say ""
say "======================= 度量 ======================="
IFS=','
for leg in $AB_LEGS; do
    measure "$leg" "build/ab/$leg.elf"
done
IFS=$OLDIFS

say ""
say "======================= 判决表（**只看行为尺**）======================="
say "  读法：DIVERGE 越少越接近工厂；abi_rc≠0 的腿**一律不得采用**（设备上会 GLIBC_* not found）。"
say "  · gcc63-* 的 DIVERGE 显著少于 zig-* ⇒ 工具链对齐是有效的整类优化 ⇒ 主构建切 CC。"
say "  · gcc63-O2 < gcc63-Os ⇒ \`-Os\`（当年按**体积比**选的）应改为 DWARF 的 \`-O2\`。"
say "  · 各腿接近 ⇒ 差异不来自编译器族/libc 头/优化级别，须回 GAP 17.19（上游库版本错配）另找。"
say ""
say "  ---- 原始记录 ----"
cat "$RES" | tee -a "$OUT"
say ""
say "→ 已写入 $OUT"

# ---- 退出码必须表达"判决是否真的做出来了" -----------------------------------
n_ok=0; n_tot=0
IFS=','
for leg in $AB_LEGS; do
    n_tot=$((n_tot + 1))
    grep -q "^$leg sha256=" "$RES" 2>/dev/null && n_ok=$((n_ok + 1))
done
IFS=$OLDIFS
say "  度量成功腿数 = $n_ok / $n_tot"
if [ "$n_ok" -ge "$n_tot" ] && [ "$n_tot" -gt 0 ]; then exit 0; fi
say "  ★★ 判决不成立（$n_ok/$n_tot 条腿量到）⇒ 退出码 3（不可判，不得当作通过）"
exit 3
