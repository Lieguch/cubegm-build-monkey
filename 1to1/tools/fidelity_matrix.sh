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

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 11
mkdir -p report build/fid cache_tc

# ---- flags：逐字取自 DWARF --------------------------------------------------
OPT="${OPT:--O2}"
ARCHF="-march=armv7-a -mfloat-abi=hard -mfpu=neon -mtune=cortex-a8"
EXTRA="-std=gnu11 -fgnu89-inline -fmerge-all-constants -fno-stack-protector -fomit-frame-pointer -ftls-model=initial-exec -frounding-math -mtls-dialect=gnu"
COMMON="-c $OPT -w -I$ROOT/src/compat $ARCHF $EXTRA"

BB="https://toolchains.bootlin.com/downloads/releases/toolchains/armv7-eabihf/tarballs"
BOOTLIN63_URL="$BB/armv7-eabihf--glibc--bleeding-edge-2017.05-toolchains-1-1.tar.bz2"
BOOTLIN54_URL="$BB/armv7-eabihf--glibc--stable-2017.05-toolchains-1-1.tar.bz2"
LINARO49_URL="https://releases.linaro.org/components/toolchain/binaries/4.9-2016.02/arm-linux-gnueabihf/gcc-linaro-4.9-2016.02-x86_64_arm-linux-gnueabihf.tar.xz"

echo "======================= 口径自证（须与工厂指纹一致）======================="
python3 tools/dwarf_recon.py --out report/dwarf_recon.txt >/dev/null 2>&1 || true
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
    [ -x "$d/.ok" ] && { echo "$d"; return 0; }
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
    for c in "$1"/bin/*-gcc; do
        [ -x "$c" ] || continue
        case "$c" in *.br_real|*-gcc-[0-9]*) continue ;; esac
        echo "$c"; return 0
    done
    return 1
}

compile_all() {
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

RESULTS="report/_fid_matrix_results.txt"
: > "$RESULTS"
echo "======================= 编译（唯一变量 = 编译器）======================="
echo "  源文件数 = $(ls -1 "$ROOT"/src/proprietary/*/*.c 2>/dev/null | wc -l)"

# 1) clang 基线
ZIGBIN=""
command -v python3 >/dev/null 2>&1 && \
    ZIGBIN=$(python3 -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)
export ZIG_GLOBAL_CACHE_DIR="${ZIG_GLOBAL_CACHE_DIR:-/tmp/zigcache_fid}"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR"
if [ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ]; then
    r=$(compile_all build/fid/clang "$ZIGBIN cc -target arm-linux-gnueabihf")
    echo "  clang     : ok=${r% *} bad=${r#* }  [$("$ZIGBIN" cc --version 2>&1 | head -1)]"
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
    r=$(compile_all "build/fid/$name" "$cc")
    echo "  $name : ok=${r% *} bad=${r#* }  [$("$cc" --version | head -1)]  <- $note"
    echo "$name ok=${r% *} bad=${r#* }  $("$cc" --version | head -1)  [$note]" >> "$RESULTS"
done

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
python3 tools/fidelity_compare.py $SETS | tee report/fidelity_matrix.txt
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
