#!/bin/sh
# ============================================================
# build_upstream.sh — 编译上游组件（1:1 符号级对齐工厂）
#
# 组件与证据：
#   stb   : stb_truetype v1.26（头文件版本宏）→ C 编译
#   mxml  : mini-XML **v2.9**（工厂实证：mxmlDelete 真递归⇒<2.10；无 mxml_free⇒<2.10；
#           无 2.11 新 API⇒<2.11；有 mxmlFindPath/mxmlGet*⇒>=2.7。换 2.9 后 DIVERGE 75->57）
#           ★ 旧注释写「v3.3.1（16 个静态函数全集比对）」—— 那个判据**没有判别力**：
#             实测 2.6..3.1 的库本体静态函数名集合完全一致（tools/mxml_version_fingerprint.py）。
#   mp3   : Helix MP3 RealNetworks fixpnt（pub/statname.h STAT_PREFIX=xmp3）→ C 编译
#   libiconv: 见 --libiconv 说明（需真源码，本批不含）
#
# 用法:
#   CC="<zig> cc" ZIG_GLOBAL_CACHE_DIR=... sh tools/build_upstream.sh [outdir]
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/build/upstream}"
CC="${CC:-arm-linux-gnueabihf-gcc}"
PY="${PY:-python}"
mkdir -p "$OUT"

winpath() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi
}

case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic" ;;
esac
# ★ 与工厂对齐（见 recon_build.sh 顶部说明）
FIDELITY="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
# ★ 2026-09-28：优化档可覆盖（构建事实对齐实验用）。
#   实测证据（mxml 单变量，见 BUILD-FACT-ALIGNMENT.md）：工厂 = **真 glibc 2.24 头 + -O2**。
#     · 真头：`putc`→`_IO_putc`、`getc`→`_IO_getc`
#     · ≥-O1（即非 -Os，因 -Os 定义 __OPTIMIZE_SIZE__ 关掉 extern-inline）：`strdup`→`__strdup`
UPOPT="${UPOPT:--Os}"
# ★★★ 2026-10-01（第 104 轮）**优化档根因修复**：`-O2` -> `-Os`。
#   依据 = `tools/upstream_opt_matrix.py` 的机械扫描（编译器固定为 zig cc = 我们实际用的那一个，
#   唯一变量是档位）。判据 M1 =「与工厂**体积逐字节相同**的共有函数个数」（巧合概率极低）：
#     stb  ：-O2 → 3   ｜ **-Os → 19**  ｜ M2 体积比中位 1.120 → 0.994
#     mxml ：-O2 → 3   ｜ **-Os → 23**  ｜ M2 1.200 → **1.000**
#     mp3  ：-O2 → 1   ｜ **-Os → 6**   ｜ M2 1.216 → 0.950
#   合计 M1 7 → **48**（7 倍）。报告：`report/upstream_opt_matrix.txt`。
#   ★ 与 §0.47「换编译器判负」不矛盾：那个实验的样本混入了"我们重建的 C"的误差，
#     本扫描的样本是**未被重建的上游源码** ⇒ 唯一变量是编译档。
#   ★ `report/dwarf_recon.txt` 里的 `-O2` 只来自 8 个 glibc/CRT CU，**不代表**上游库 ——
#     这正是把"上游库档位"当成已知事实所犯的错。
# ★ 2026-09-28：头集合改为**尾置**（`EXTRA_INC_TRAIL`）——必须在组件自己的 `-I` 之后，
#   否则会盖住组件 vendored 的头（实测：盖住 libiconv 的 iconv.h ⇒ converters.h 编译失败）。
CFLAGS="-c $UPOPT -w -fno-strict-aliasing $ARCH $FIDELITY"
# ★★ 与工厂对齐的第二层：**per-TU 优化档**（2026-09-27 新证据）
#   工厂 DWARF 只覆盖 8 个 CRT/glibc CU ⇒ 应用对象无 DWARF，拿不到 per-TU 的 `-O`。
#   改用**代码形态普查**（tools/codegen_style_census.py，判"帧指针 + r0..r3 全部落栈"的 -O0 序言）：
#       工厂 804 个函数里 **304 个是 -O0 形态**，且 **304 个全部属于 libiconv**；
#       mxml / stb / unzip / mp3 / 应用 **0 个** -O0 形态。
#       交叉表： Thumb∩O0=304 ｜ Thumb∩OTHER=4 ｜ ARM∩O0=0 ｜ ARM∩OTHER=496
#   ⇒ 工厂构建 = 「**libiconv 整 TU 用 `-O0 -mthumb`，其余 ARM + 优化**」。
#   ⇒ 这就是 iconv 族逐函数对拍**全部分歧**的根因：-O0 不删未使用的开头参数（ABI 保持
#     名义形态 r0..r3 = conv,pwc,s,n）；我们在 -Os 下编，LLVM 删掉未使用的 `conv`
#     ⇒ **ABI 左移一格** ⇒ 喂参错位 ⇒ 假发散。证据与最小复现见 `ROOTCAUSE-ABI-SHIFT.md`。
#
#   ★★ 2026-09-27 实测纠错（我先前把第一次链接失败的归因写错了，此处更正）：
#      第一次把 libiconv 改成 `-O0` 后链接失败，报
#          ld.lld: undefined symbol: pipe2 / preadv64 / pwritev64
#      我当时写成"libiconv 在 -O0 下引用了 glibc≥2.10 符号"—— **错了**。
#      lld 的完整报文显示真实引用方是 **zig 自带运行库归档 `libubsan_rt.a`**
#      （`Io.Threaded.processSpawnPosix` / `fileReadPositional`，Threaded.zig）。
#      原因：**zig 的 `-O0` 是 Debug 档 ⇒ 默认启用运行时安全检查 ⇒ 把 libubsan_rt.a 拉进链接**，
#      而该归档引用了我们 glibc 2.7 sysroot 里没有的 `pipe2/preadv64/pwritev64`。
#      ⇒ 与 libiconv 源码无关，**用 `-fno-sanitize=all` 关掉安全检查即可**（下面已加）。
#      （附带仍成立的一条事实：我们的 zig 腿按 glibc **2.7** 出，工厂 CRT DWARF 显示 glibc **2.24**；
#        这是**独立**的一项错配，见 PROJECT-MEMORY §0.17，不由此错误链条推断。）

# ★★★ 2026-09-28：**构建事实**（臂 C 实测，见 BUILD-FACT-ALIGNMENT.md）
#   工厂用**真 glibc 2.24 头**（证据：`putc`→`_IO_putc`、`getc`→`_IO_getc`；
#   真头 `stdio.h:587` 把 putc 定义为无条件宏）＋ clang 不做 `strcmp(x,"lit")==0`→`bcmp`
#   的变换（GCC 不做，需 `-fno-builtin-strcmp`）。
#   头搜索顺序**必须**是「组件自己的头 → GCC include → GCC include-fixed → sysroot/usr/include」：
#     · 额外头排在组件 `-I` 之前会盖住组件 vendored 头（实测盖住 libiconv 的 iconv.h）；
#     · 真 glibc 的 limits.h 用 `#include_next`，不插 GCC include-fixed 会跳进 zig 自带的新版
#       glibc limits.h ⇒ `'__GLIBC_USE' is not defined`。
CGM_TC="${CGM_TC:-$ROOT/cache_tc/bootlin63}"
CGM_GI="$CGM_TC/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include"
CGM_GIF="$CGM_TC/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include-fixed"
CGM_GD="$CGM_TC/arm-buildroot-linux-gnueabihf/sysroot/usr/include"
if [ ! -f "$CGM_GD/stdio.h" ] || [ ! -f "$CGM_GI/stddef.h" ]; then
    echo "★★ 缺工厂同期真头（$CGM_GD）—— 这是构建事实，不是可选优化。" >&2
    echo "   先跑：sh tools/fetch_bootlin63.sh" >&2
    exit 4
fi
CGM_HDR="-nostdinc -I$CGM_GI -I$CGM_GIF -I$CGM_GD"
CGM_FID_EXTRA="-fno-builtin-strcmp"

LIBOPT="${LIBOPT:--O0}"
# ★★★ 2026-10-01（第 107 轮）**回退记录**：曾试改为 `-Os`，**实测净恶化，已回退**。
#   实测（同产物、同判据）：`-O0` → 函数总数 788 / PASS 766 / **DIVERGE 17**；
#                          `-Os` → 函数总数 756 / PASS 714 / **DIVERGE 37**。
#   根因：`-O0` **不内联** ⇒ libiconv 的 charset 转换函数各自独立存在，与工厂的 300+ 个
#     独立函数**集合对齐**；`-Os` 把小函数内联掉 ⇒ **32 个函数直接消失**。
#   ★ 我的判据失误（**必须记住**）：libiconv 扫描用的是"空前缀 + 工厂交集" ⇒
#     M3（工厂独有）/M4（我方独有）在**空前缀**下失去意义，于是只剩 M2（体积比中位）
#     ⇒ 被 `-O0` 的 M2=1.853 误导，而**漏掉了"函数消失"这个最严重的退化**。
#     ⇒ 纪律 110：空/宽前缀的组件扫描，**必须**把"共有函数数"也当判据。
#   ★ 仍然成立、且已登记的未对齐项：工厂 libiconv 相关 **296 个函数全是 Thumb**，
#     我方 809 个函数 Thumb = 0（全 ARM）。`zig cc` **静默忽略 `-mthumb`**
#     （实测 `-O2` 与 `-O2 -mthumb` 产物**逐字节相同**；`-Xclang -mthumb` 报 unknown argument）
#     ⇒ Thumb 只能用**真 GCC**（Linux）产出，已登记为待办（`tools/isa_mode_gate.py` 棘轮守着）。
# ★★★ 2026-10-01（第 107 轮）**libiconv/libcharset 的档位根因修复**：`-O0` -> `-Os`。
#   依据 = `_r107_iconv_thumb.py` 的机械判定（编译器固定 zig cc，唯一变量 = 档位；
#   样本 = libiconv17/iconv.c 与 libcharset/localcharset.c，与工厂**同源码**）：
#     档位    M1 体积逐字节相同   M2 体积比中位
#     -O0     0                  1.853   ← 原用档，**所有档位里最差**
#     -O1/-O2 0                  0.844
#     -Os     1                  0.783   ← 采纳
#   ★ 原 `-O0` 的依据是 `codegen_style_census` 的"工厂 304 个 -O0 形态函数全属 libiconv"，
#     **本轮实测推翻**：工厂 libiconv 相关 296 个函数**全是 Thumb**（见下），
#     而 Thumb 的序言（`push {r7,lr}; sub sp,#8; add r7,sp,#0`）与 -O0 序言形似 ⇒ **误判**。
#   ★ 仍未对齐的部分：工厂 libiconv 是 **Thumb**，我方 809 个函数 Thumb = 0（全 ARM）；
#     `zig cc` **静默忽略 `-mthumb`**（实测 `-O2` 与 `-O2 -mthumb` 产物逐字节相同；
#     `-Xclang -mthumb` 报 unknown argument）⇒ Thumb 只能用**真 GCC**（Linux）产出。已登记。
LIBCFLAGS="-c $LIBOPT -fno-sanitize=all -w -fno-strict-aliasing $ARCH $FIDELITY"

# ★★★ 第 115 轮（2026-10-02）Thumb 根修：libiconv/libcharset **独立用真 GCC 编 Thumb**。
#   工厂构建事实（第 107 轮已证）：libiconv 296 个函数全是 Thumb，`.comment`=GCC 6.x，
#   即工厂用 `arm-linux-gnueabihf-gcc -O0 -mthumb` **单独**编这两个 TU；应用层才是 ARM。
#   `zig cc` **静默忽略 -mthumb**（实测 -O2 与 -O2 -mthumb 产物逐字节相同）——
#   这是 zig(clang 驱动)对本 target 的限制，不是 libiconv 的问题。
#   联网核实（第 115 轮）：LLVM D33448 / HowToCrossCompileBuiltinsOnArm.rst / llvm-dev ——
#   在**真 clang/gcc** 下 `-mthumb` 或 `thumbv7-linux-gnueabihf` 完整支持 Thumb2。
#   ⇒ 根修 = libiconv 走独立的 ICONV_CC（默认=$CC，保本机 zig 仍可编 ARM 对象）；
#     云上设 ICONV_CC=<真 GCC> 即产出 Thumb。收敛验证交 `tools/isa_mode_gate.py`
#     （期望 mismatch 从基线 308 大幅下降）。这是**工具链根因**，非补丁。
ICONV_CC="${ICONV_CC:-$CC}"
# ★ ICONV_CC 可能 ≠ $CC（云上用真 GCC，本机/CI 仍是 zig）⇒ 目标/架构参数必须跟着 ICONV_CC 走，
#   不能复用上面只跟 $CC 分支的 $ARCH —— 否则本机/CI 的 zig 会收到 `-march=armv7-a` 而无
#   `-target` ⇒ 默认 x86_64 target 直接报 "unsupported option -march"（回归）。
case "$ICONV_CC" in
  *zig*) ICONV_ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ICONV_ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic" ;;
esac
# -mthumb：zig cc（clang 驱动）对该 target 静默忽略 ⇒ 回到旧 ARM 行为（不回归）；
#          真 GCC 产出 Thumb2 ⇒ 根修生效。收敛验证交 `tools/isa_mode_gate.py`。
ICONV_FLAGS="-c $LIBOPT -mthumb -fno-sanitize=all -w -fno-strict-aliasing $ICONV_ARCH $FIDELITY"

say() { echo "== $* =="; }

# ★★★ ICONV_ONLY=1：只编 libiconv/libcharset（第 115 轮 Thumb 根修实验专用），跳过
#   stb/mxml/mp3 —— 它们已由上传的 `build/upstream/*.o`（zig ARM）供应，不重编，
#   从而把「libiconv 变 Thumb」做成严格单变量（其余上游库保持 zig ARM 不变）。
#   默认 0 = 全量（原行为逐字不变）。
if [ "${ICONV_ONLY:-0}" != "1" ]; then

# ---------- 1) stb_truetype ----------
say "stb_truetype v1.26"
SDL="$ROOT/src/upstream/stb"
if $CC $CFLAGS -I"$(winpath "$SDL")" ${EXTRA_INC_TRAIL:-$CGM_HDR} "$(winpath "$SDL/stb_truetype_impl.c")" -o "$(winpath "$OUT/stb_truetype.o")" 2>"$OUT/_err_stb.txt"; then
    echo "  OK stb_truetype.o"
else
    echo "  FAIL stb"; head -3 "$OUT/_err_stb.txt"
fi

# ---------- 2) mini-XML v2.9 ----------
say "mini-XML v2.9"
MD="$ROOT/src/upstream/mxml"
mxml_ok=0; mxml_bad=0
for f in "$MD"/mxml-*.c; do
    [ -f "$f" ] || continue
    b=$(basename "$f" .c)
    # testmxml.c 是示例程序，不编
    if $CC $CFLAGS -I"$(winpath "$MD")" ${EXTRA_INC_TRAIL:-$CGM_HDR} "$(winpath "$f")" -o "$(winpath "$OUT/mxml_$b.o")" 2>"$OUT/_err_$b.txt"; then
        mxml_ok=$((mxml_ok + 1))
    else
        mxml_bad=$((mxml_bad + 1)); echo "  FAIL $b"; head -3 "$OUT/_err_$b.txt"
    fi
done
echo "  mxml: OK $mxml_ok / FAIL $mxml_bad"

# ---------- 3) Helix MP3 (fixpnt) ----------
say "Helix MP3 fixpnt (STAT_PREFIX=xmp3)"
PD="$ROOT/src/upstream/mp3"
mp3_ok=0; mp3_bad=0
for f in "$PD"/real/*.c; do
    [ -f "$f" ] || continue
    b=$(basename "$f" .c)
    # 纯数据文件：其表由工厂 .rodata 镜像供应（factory_image.S 已别名），跳过编译
    case "$b" in mp3tabs|trigtabs|hufftabs) echo "  SKIP $b（纯数据，由工厂镜像供应）"; continue ;; esac
    MP3EXTRA=""
    case "$b" in mp3dec) MP3EXTRA="-DMP3GetNextFrameInfo=mp3_unused_GetNextFrameInfo" ;; esac
    if $CC $CFLAGS $MP3EXTRA -I"$(winpath "$PD")" -I"$(winpath "$PD/pub")" -I"$(winpath "$PD/real")" ${EXTRA_INC_TRAIL:-$CGM_HDR} \
         "$(winpath "$f")" -o "$(winpath "$OUT/mp3_$b.o")" 2>"$OUT/_err_mp3_$b.txt"; then
        mp3_ok=$((mp3_ok + 1))
    else
        mp3_bad=$((mp3_bad + 1)); echo "  FAIL $b"; head -3 "$OUT/_err_mp3_$b.txt"
    fi
done
echo "  mp3: OK $mp3_ok / FAIL $mp3_bad"

fi   # end ICONV_ONLY

# ---------- 4) GNU libiconv 1.17（真源码，非桩） ----------
say "GNU libiconv 1.17"
LD="$ROOT/src/upstream/libiconv17"
if [ -f "$LD/iconv.c" ]; then
    if $ICONV_CC $ICONV_FLAGS -I"$(winpath "$LD")" "$(winpath "$LD/iconv.c")" ${EXTRA_INC_TRAIL:-$CGM_HDR} -o "$(winpath "$OUT/libiconv_iconv.o")" 2>"$OUT/_err_libiconv.txt"; then
        echo "  OK libiconv_iconv.o"
    else
        echo "  FAIL libiconv"; head -3 "$OUT/_err_libiconv.txt"
    fi
else
    echo "  SKIP（缺 src/upstream/libiconv17/iconv.c）"
fi

# ---------- 5) libiconv 附属：libcharset/localcharset.c（locale_charset） ----------
LC="$ROOT/src/upstream/libcharset"
if [ -f "$LC/localcharset.c" ]; then
    if $ICONV_CC $ICONV_FLAGS -I"$(winpath "$LD")" -I"$(winpath "$LC")" "$(winpath "$LC/localcharset.c")" ${EXTRA_INC_TRAIL:-$CGM_HDR} -o "$(winpath "$OUT/libiconv_localcharset.o")" 2>"$OUT/_err_localcharset.txt"; then
        echo "  OK libiconv_localcharset.o"
    else
        echo "  FAIL localcharset"; head -3 "$OUT/_err_localcharset.txt"
    fi
fi

echo "== 产物 =="
ls -1 "$OUT"/*.o 2>/dev/null | wc -l
echo "== 符号核对 =="
{
    for o in "$OUT"/*.o; do
        [ -f "$o" ] || continue
        $PY "$(winpath "$ROOT/tools/elf_syms.py")" "$(winpath "$o")" 2>/dev/null
    done
} > "$OUT/_syms.tsv"
for s in stbtt_InitFont stbtt_ScaleForPixelHeight stbtt_GetFontVMetrics \
         mxmlFindElement mxmlLoadFile mxmlSaveFile mxmlDelete MP3InitDecoder MP3Decode \
         libiconv libiconv_open libiconv_close; do
    printf "  %-30s %s\n" "$s" "$(awk -F'\t' -v s="$s" '$1=="DEFINED" && $2==s {c++} END{print c+0}' "$OUT/_syms.tsv")"
done
