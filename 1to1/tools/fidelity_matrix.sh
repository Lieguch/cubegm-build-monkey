#!/bin/sh
# ============================================================================
# fidelity_matrix.sh —— 判决实验（第 65 轮，**候选已换成"可达 + 版本对齐"的**）
#
# ## 问的问题（只有这一句）
#   「把编译器换成**与工厂同族、同 glibc、同 binutils** 的那一个，机器码会不会更接近工厂？」
#
# ## 依据（全部来自目标程序自身，见 `report/dwarf_recon.txt`；不许凭印象写）
#   · 构建目录  `/home/vmuser/Lakka/build.Lakka-a10.arm-8.0-devel/`
#   · 编译器    `GNU C11 6.2.0`（`.comment` 另有 `Linaro GCC 4.9-2016.02) 4.9.4`）
#   · CFLAGS    `-march=armv7-a -mfloat-abi=hard -mfpu=neon -mtune=cortex-a8 -O2
#                -std=gnu11 -fgnu89-inline -fmerge-all-constants -fno-stack-protector
#                -fomit-frame-pointer -ftls-model=initial-exec -mtls-dialect=gnu`
#   · binutils  `GNU AS 2.27` + `.note.gnu.gold-version` = gold 1.12
#   · glibc     `2.24`
#
# ## 候选（**每个 tarball 都已 curl 实测过 HTTP 码**，不是"我印象里能下"）
#   clang      ：zig cc（现状基线）
#   bootlin63  ：`armv7-eabihf--glibc--bleeding-edge-2017.05-toolchains-1-1`
#                ⇒ **GCC 6.3.0 / glibc 2.24 / binutils 2.27**  ← 与工厂同族、同 libc、同 binutils
#   bootlin54  ：`armv7-eabihf--glibc--stable-2017.05-toolchains-1-1`
#                ⇒ GCC 5.4.0 / glibc 2.24 / binutils 2.27
#                ← **对照组**：libc/binutils 与上面**完全相同**，只差 GCC 大版本。
#                  有它才能把"libc/binutils 对齐的贡献"与"GCC 版本的贡献"**分开**——
#                  否则"换了工具链变好了"这句话说不清是哪个变量的功劳。
#   linaro49   ：`gcc-linaro-4.9-2016.02-…-arm-linux-gnueabihf`（`.comment` 里的第二个标签）
#                ⚠ 实测本机/CI 对该域名 **不可达**（curl exit 35）；保留候选并预期 UNAVAILABLE，
#                  **不许**因为它挂了就把整轮结论当成"没得比"。
#
#   ★ 为什么这一轮不硬等 GCC **6.2.0** 本体：官方 repo（`releases.linaro.org`）不可达，
#     `developer.arm.com` 的直链要在页面里取。而 **6.3.0 与 6.2.0 同属 GCC 6.x、代码生成族相同**
#     ⇒ 用它做判决**有效**；拿到 6.2.0 只是把最后一个变量也钉死（补齐路径见 `GAP.md` §17.22）。
#
# ## 设计（单变量）+ 预登记判据（先写下再跑，防事后找解释）
#   同一份源码、**逐字相同**的一组 flags（取自 DWARF），唯一变量 = 编译器；只编译不链接
#   （绕开跨工具链链接的 libc 符号冲突），同一反汇编器 + 同一份工厂数据对拍。
#     M1 = 「体积比落在工厂 ±15% 内」的函数数（越大越像）
#     M2 = 助记符直方图 L1 距离中位数（越小越像）
#   ⇒ bootlin63 的 M1 明显高于 clang 且 M2 明显低于 clang
#      ⇒ **工具链对齐是有效的整类优化**，下一步把主构建 `CC` 切过去并重跑全部门禁；
#   ⇒ bootlin63 ≈ clang ⇒ 才允许讨论"判据口径"，且必须附本次原始数字。
#   ★ 体积比/直方图**不是功能进度尺**（GAP 16.43），仅用于"同输入下谁更像工厂"的相对判断。
#
# 输出：report/fidelity_matrix.txt
# exit: 0 = 至少两个候选完成对拍 / 11 = 仪器不可用
# ============================================================================
set -u

# ★ 解释器可覆盖：本机 `python3` 是**基座**解释器（无 pyelftools/capstone），venv 才有。
#   硬编 python3 会把本机路径封死 ⇒ 只能上 CI 跑 ⇒ 绕圈。
#   用法：PY=<venv>/python sh tools/fidelity_matrix.sh
PY="${PY:-python3}"

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 11
mkdir -p report build/fid cache_tc

# ---- 解析 zig（**必须放最前**：探针与编译都要用；旧版放编译段 ⇒ set -u 下探针先崩）----
ZIGBIN="${ZIGBIN:-}"
if [ -z "$ZIGBIN" ]; then
    ZIGBIN=$("$PY" -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)
fi
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-$ROOT/build/_zigcache_fid}"

# ---- flags：逐字取自 DWARF --------------------------------------------------
OPT="${OPT:--O2}"
ARCHF="-march=armv7-a -mfloat-abi=hard -mfpu=neon -mtune=cortex-a8"
EXTRA="-std=gnu11 -fgnu89-inline -fmerge-all-constants -fno-stack-protector -fomit-frame-pointer -ftls-model=initial-exec -frounding-math -mtls-dialect=gnu"
COMMON="-c $OPT -w -I$ROOT/src/compat $ARCHF $EXTRA"
# ★ clang 不接受 GCC 专属开关（实测 `unknown CPU` 一族）⇒ 给 clang 一个**兼容子集**。
#   这构成一处**必须在报告里披露的口径差异**：GCC 组之间是严格单变量（flags 逐字相同），
#   而 clang↔GCC 之间除编译器外还差这 4 个开关。所以：
#     · **判决结论以 GCC 两组之间的比较为准**（bootlin63 vs bootlin54，flags 完全相同，
#       唯一差别 = GCC 大版本 ⇒ 干净地给出"GCC 版本的贡献"）；
#     · clang 只作**基线参照**，且它的 flags 差异在此显式登记。
#   ★ 实测 zig 对 `-mtune=cortex-a8` 报 `error: unknown CPU: 'cortex'`（它的 ARM CPU 表
#     不含该值，且报错只吐了 dash 前那段）⇒ clang 基线**去掉 -mtune**，其余保持一致。
# ★★ 第 66 轮实测（逐个 flag 用 zig 打靶）：
#     zig 接受工厂的全部 flags **除了** `-mtls-dialect=gnu`（`unsupported option ... for armv7`）。
#     而 `-mtune=cortex-a8` 必须写成 `-mtune=cortex_a8`（zig 的 ARM CPU 表用下划线；
#     写 cortex-a8 会报 `unknown CPU: 'cortex'`——它把 "-a8" 当成了另一个开关）。
#     ⇒ clang 组现在与 GCC 组**逐字相同**，只差 `-mtls-dialect=gnu` 一个（ARM EABI 默认值）。
COMMON_CLANG="-c $OPT -w -I$ROOT/src/compat -march=armv7-a -mfloat-abi=hard -mfpu=neon \
 -mtune=cortex_a8 -std=gnu11 -fgnu89-inline -fmerge-all-constants -fno-stack-protector \
 -fomit-frame-pointer -ftls-model=initial-exec -frounding-math"

BB="https://toolchains.bootlin.com/downloads/releases/toolchains/armv7-eabihf/tarballs"
BOOTLIN63_URL="$BB/armv7-eabihf--glibc--bleeding-edge-2017.05-toolchains-1-1.tar.bz2"
BOOTLIN54_URL="$BB/armv7-eabihf--glibc--stable-2017.05-toolchains-1-1.tar.bz2"
LINARO49_URL="https://releases.linaro.org/components/toolchain/binaries/4.9-2016.02/arm-linux-gnueabihf/gcc-linaro-4.9-2016.02-x86_64_arm-linux-gnueabihf.tar.xz"

echo "======================= 口径自证（须与工厂指纹一致）======================="
"$PY" tools/dwarf_recon.py --out report/dwarf_recon.txt >/dev/null 2>&1 || true
grep -aE 'comp_dir|GNU C11|GNU AS|glibc-' report/dwarf_recon.txt 2>/dev/null | head -4
echo "  flags（取自 DWARF）: $OPT $ARCHF"
echo "                       $EXTRA"
echo

# ---- 取工具链 --------------------------------------------------------------
# ★ 必须**按扩展名选解压器**（Bootlin 是 .tar.bz2，Linaro 是 .tar.xz）。
#   用错解压器的现象是"下载成功但解压失败"，与"下载失败"同样表现为 UNAVAILABLE
#   ⇒ 分不清原因。这里把两种原因**分别打印**。
untar() {
    case "$1" in
        *.tar.xz|*.txz)   tar -xJf "$1" -C "$2" --strip-components=1 ;;
        *.tar.bz2|*.tbz2) tar -xjf "$1" -C "$2" --strip-components=1 ;;
        *.tar.gz|*.tgz)   tar -xzf "$1" -C "$2" --strip-components=1 ;;
        *) return 1 ;;
    esac
}

fetch_tc() {
    # $1=目录名 $2=url → stdout 输出解压目录；失败 1
    d="cache_tc/$1"
    # ★★ 第 66 轮：原写 `-x`，而 `.ok` 是 `touch` 建的（0644，**不可执行**）
    #   ⇒ 缓存**永远不命中** ⇒ CI 每次重下 3 个工具链（~190 MB）⇒ 静默烧分钟数。
    [ -f "$d/.ok" ] && { echo "$d"; return 0; }
    rm -rf "$d"; mkdir -p "$d"
    f="cache_tc/$1.$(echo "$2" | sed 's/.*\.\(tar\.[a-z0-9]*\)$/\1/')"
    echo "  下载 $1 ..." >&2
    if ! curl -fsSL --retry 3 --retry-delay 2 --max-time 600 -o "$f" "$2"; then
        echo "   ★ $1 下载失败（curl rc=$?）" >&2; return 1
    fi
    if ! untar "$f" "$d"; then echo "   ★ $1 解压失败" >&2; return 1; fi
    touch "$d/.ok"; echo "$d"
}

find_cc() {
    # → 该工具链里的 C 编译器（**自动判前缀**，不写死 triplet）
    # ★★ 第 66 轮更正：必须用 **`*-gcc.br_real`**（真编译器），不能用 `-gcc`。
    #   理由（读 Buildroot 产物实测）：`-gcc` 是指向 `toolchain-wrapper` 的**软链**，
    #   该 wrapper 会按 `buildroot.config` 注入 `-mcpu=cortex-a9 -mfpu=vfpv3-d16`，
    #   而工厂用的是 `-march=armv7-a -mfpu=neon` ⇒ **FPU/CPU 被静默改掉**，
    #   单变量前提当场失效，且错误不可见（旧版还把 `.br_real` 显式跳过，正好反了）。
    for c in "$1"/bin/*-gcc.br_real "$1"/bin/*-gcc; do
        [ -f "$c" ] || continue
        case "$c" in *-gcc-[0-9]*) continue ;; esac
        [ -x "$c" ] || continue
        echo "$c"; return 0
    done
    return 1
}

compile_all() {
    # $1=出目录  $2=flags  $3..=编译器
    out="$1"; FL="$2"; shift 2
    rm -rf "$out"; mkdir -p "$out"
    errf="report/_fid_err_$(basename "$out").txt"
    : > "$errf"
    ls -1 "$ROOT"/src/proprietary/*/*.c 2>/dev/null > "$out/.list"
    total=$(wc -l < "$out/.list")
    jobs="${FID_JOBS:-8}"
    # ★ 并行：223 个 .c × 4 候选，串行一轮太久 —— 慢会把人逼回 CI，那正是绕圈的成因之一。
    # shellcheck disable=SC2086
    xargs -P "$jobs" -I{} sh -c '
        f="$1"; out="$2"; errf="$3"; fl="$4"; shift 4
        stem=$(basename "$f" .c)
        if "$@" $fl "$f" -o "$out/$stem.o" 2>>"$errf"; then :; else rm -f "$out/$stem.o"; fi
    ' _ {} "$out" "$errf" "$FL" "$@" < "$out/.list"
    ok=$(ls -1 "$out"/*.o 2>/dev/null | wc -l)
    echo "$ok $((total - ok))"
}

RESULTS="report/_fid_matrix_results.txt"
: > "$RESULTS"

echo "======================= 编译（唯一变量 = 编译器）======================="
echo "  源文件数 = $(ls -1 "$ROOT"/src/proprietary/*/*.c 2>/dev/null | wc -l)"

# 1) clang 基线
mkdir -p "$ZIG_GLOBAL_CACHE_DIR"
if [ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ]; then
    r=$(compile_all build/fid/clang "$COMMON_CLANG" "$ZIGBIN cc -target arm-linux-gnueabihf")
    echo "  clang     : ok=${r% *} bad=${r#* }  [$("$ZIGBIN" cc --version 2>&1 | head -1)]"
    [ "${r% *}" = "0" ] && { echo '    --- clang 前 5 条错误 ---'; grep -aE 'error|Error|not found' report/_fid_err_clang.txt | head -5; }
    echo "clang ok=${r% *} bad=${r#* }  $("$ZIGBIN" cc --version 2>&1 | head -1)" >> "$RESULTS"
else
    echo "  clang     : UNAVAILABLE（找不到 zig）"; echo "clang UNAVAILABLE" >> "$RESULTS"
fi

# 2..4) 三个 GCC 候选
for spec in "bootlin63|$BOOTLIN63_URL|GCC6.3/glibc2.24/binutils2.27（与工厂同族同 libc 同 binutils）" \
            "bootlin54|$BOOTLIN54_URL|GCC5.4/glibc2.24/binutils2.27（对照组：只差 GCC 大版本）" \
            "linaro49|$LINARO49_URL|Linaro4.9.4-2016.02（.comment 第二标签；域名实测不可达）"; do
    name=$(echo "$spec" | cut -d'|' -f1)
    url=$(echo "$spec" | cut -d'|' -f2)
    note=$(echo "$spec" | cut -d'|' -f3)
    dir=$(fetch_tc "$name" "$url") || {
        echo "  $name : UNAVAILABLE（下载/解压失败）  <- $note"
        echo "$name UNAVAILABLE  [$note]" >> "$RESULTS"; continue; }
    cc=$(find_cc "$dir") || {
        echo "  $name : UNAVAILABLE（解压目录内无 *-gcc）  <- $note"
        echo "$name UNAVAILABLE(no-gcc)  [$note]" >> "$RESULTS"; continue; }
    printf '%s\n' "$cc" > "cache_tc/$name.cc"
    r=$(compile_all "build/fid/$name" "$COMMON" "$cc")
    echo "  $name : ok=${r% *} bad=${r#* }  [$("$cc" --version | head -1)]  <- $note"
    [ "${r% *}" = "0" ] && { echo '    --- 前 5 条错误 ---'; grep -aE 'error|Error|not found' "report/_fid_err_$name.txt" | head -5; }
    echo "$name ok=${r% *} bad=${r#* }  $("$cc" --version | head -1)  [$note]" >> "$RESULTS"
done

# ---------------------------------------------------------------------------
# ★ 探针（**必须在取到工具链之后**）：把各编译器的**真实**系统头里
#   `__timezone_ptr_t` 的原文打印出来，与我们 compat 头里的声明**对拍**。
#   为什么打印而不是猜：第 65 轮我们的声明让真实 glibc 2.24 报
#     `error: conflicting type qualifiers for '__timezone_ptr_t'`
#   —— 那是"**限定符**不同"，即我们缺了 `__restrict`（glibc 2.24 原文：
#     `typedef struct timezone *__restrict __timezone_ptr_t;`）。
#   本节把两侧原文都写进报告 ⇒ 下次有人改这行，报告会当场显示不一致。
# ---------------------------------------------------------------------------
echo "======================= 探针：四侧系统头的 __timezone_ptr_t 真实声明 ======================="
probe_one() {
    nm=$1; cc=$2
    [ -n "$cc" ] || return 0
    printf '  --- %-10s ' "$nm"
    # shellcheck disable=SC2086
    v=$($cc --version 2>/dev/null | head -1)
    echo "[$v]"
    # shellcheck disable=SC2086
    h=$(printf '#include <sys/time.h>\n' | $cc -E -dD -xc - 2>/dev/null \
        | grep -a '__timezone_ptr_t' | head -2)
    if [ -n "$h" ]; then echo "$h" | sed 's/^/      系统头: /'
    else echo "      系统头: （不声明该名字）"; fi
}
probe_one clang    "$( [ -n "${ZIGBIN:-}" ] && echo "$ZIGBIN cc -target arm-linux-gnueabihf.${GLIBC_VER_MATRIX:-2.24}" )"
for cand in bootlin63 bootlin54; do
    probe_one "$cand" "$(cat "cache_tc/$cand.cc" 2>/dev/null)"
done
echo "      我们的声明:"
grep -n '__timezone_ptr_t' src/compat/ghidra_compat.h | grep -v '^\s*\*' | sed 's/^/        /'
echo

# ---- 收敛到"所有活跃候选都编出的"同子集（防幸存者偏差）----------------------
ACTIVE=""
for cand in clang bootlin63 bootlin54 linaro49; do
    [ -d "build/fid/$cand" ] && [ -n "$(ls -A build/fid/$cand 2>/dev/null)" ] && ACTIVE="$ACTIVE $cand"
done
echo
echo "  活跃候选：$ACTIVE"
for cand in $ACTIVE; do
    for o in build/fid/$cand/*.o; do
        [ -f "$o" ] || continue
        b=$(basename "$o")
        for other in $ACTIVE; do
            [ "$other" = "$cand" ] && continue
            [ -f "build/fid/$other/$b" ] || { rm -f "$o"; break; }
        done
    done
done
for cand in $ACTIVE; do
    printf '    %-10s 同子集对象 %s\n' "$cand" "$(ls -1 build/fid/$cand/*.o 2>/dev/null | wc -l)"
done

SETS=""
for cand in $ACTIVE; do SETS="$SETS --set $cand=build/fid/$cand"; done
if [ -z "$SETS" ]; then echo "★★ 无任何候选产出对象 —— 仪器不可用" >&2; exit 11; fi

echo
echo "======================= 对拍 ======================="
# shellcheck disable=SC2086
"$PY" tools/fidelity_compare.py $SETS | tee report/fidelity_matrix.txt
rc=$?

{
  echo
  echo "======================= 候选身份（口径可复核）======================="
  cat "$RESULTS"
  echo
  echo "======================= 预登记判据与读法 ======================="
  echo "  · 唯一变量是编译器；flags 逐字取自目标程序自带的 DWARF（$OPT $ARCHF）。"
  echo "  · 主看两行：M1「±15% 命中数」（越大越像）/ M2「助记符 L1 中位」（越小越像）。"
  echo "  · bootlin63 明显优于 clang ⇒ 工具链对齐是有效的整类优化 ⇒ 下一步切主构建 CC。"
  echo "  · bootlin54 vs bootlin63 的差 = **GCC 大版本的贡献**（两者 libc/binutils 完全相同）。"
  echo "  · 体积比/直方图不是功能进度尺（GAP 16.43）；UNAVAILABLE 必须保留在表里。"
  echo "  · 工厂真值：GCC 6.2.0 / glibc 2.24 / AS 2.27 / gold 1.12（本表是**代理对比**，非逐位同款）。"
} >> report/fidelity_matrix.txt

echo
echo "→ 已写入 report/fidelity_matrix.txt"
exit $rc
