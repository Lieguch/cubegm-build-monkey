#!/bin/sh
# ============================================================
# link_audit.sh — P3 链接就绪审计
#
# 1) 把 src/proprietary/ 全部 .c 编译为 .o 到 build/obj/
# 2) 用 tools/elf_syms.py 提取每个 .o 的符号
# 3) 用 tools/link_audit.py 汇总：重复定义 / 未解析引用分类
#
# 用法:
#   sh tools/link_audit.sh [报告路径]
# 依赖环境变量 CC（默认 zig cc 包装）:
#   CC="<zig> cc" ZIG_GLOBAL_CACHE_DIR=... sh tools/link_audit.sh
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REP="${1:-$ROOT/report/link_audit.txt}"
# ★ 2026-09-28：对象输出目录可用 OBJD 覆盖（编译器对齐实验用 build/gcc_obj，不污染主链）
OBJD="${OBJD:-$ROOT/build/obj}"
SRCDIR="$ROOT/src/proprietary"
PY="${PY:-python}"

# CC 可以是 "zig cc" 这样的多词命令
CC="${CC:-arm-linux-gnueabihf-gcc}"

# Windows 上的原生 Python / zig.exe 需要 Windows 风格路径
winpath() {
    if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi
}
WINROOT=$(winpath "$ROOT")
# CC 自适应：zig(cc/clang) 用 -target，GCC 用 -march/-mfloat-abi
case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic" ;;
esac
# ★ 与工厂对齐（见 recon_build.sh 顶部说明）：关掉 canary 与 FORTIFY
FIDELITY="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
# ★★ 2026-09-20（GAP 16.33）：**优化级别默认 -Os**（此前 -O1）。
#   本脚本是**唯一**把 src/proprietary/*.c 编成 build/obj/*.o 的地方（cnb_env.sh [6/7] 调它），
#   所以"编译口径"在这里定，而不是在 link_full.sh（那只做链接）。
#   ── 依据（单变量抽样实测，zig cc -target arm-linux-gnueabihf.2.29，同一份 src 逐个编译）──
#     SPI_RR         工厂  92 B ⇒ -O1 384 B (4.17x)  vs  **-Os  92 B (1.00x，精确到字节)**
#     gameType       工厂  60 B ⇒ -O1 276 B (4.60x)  vs  **-Os  52 B (0.87x)**
#     Convert_Stereo 工厂  56 B ⇒ -O1 412 B (7.36x)  vs  **-Os  76 B (1.36x)**
#     outputblankxy  工厂 220 B ⇒ -O1 644 B (2.93x)  vs  **-Os 272 B (1.24x)**
#     DrawSelectBar  工厂 168 B ⇒ -O1 488 B (2.90x)  vs  **-Os 196 B (1.17x)**
#     SPI_WW         工厂 104 B ⇒ -O1 296 B (2.85x)  vs  **-Os  96 B (0.92x)**
#     DrawFrame      工厂 552 B ⇒ -O1 644 B (1.17x)  vs  **-Os 508 B (0.92x)**
#   ⇒ **工厂 rkgame 是用 -Os 编译的**。`-O1` 会把"次数为编译期常量的小循环"完全展开
#     （源码里的 `do{...}while(cVar2 != 0)`），制造 4~7x 的**纯编译差异**，
#     被 tools/prop_equiv.py 的 size 比值判据误报成 FAIL（7 个 FAIL 里 5+ 个源于此）。
#   ★ 单变量纪律：`OPT=-O1 sh tools/link_audit.sh <out>` 可回到旧口径做对照。
OPT="${OPT:--Os}"
# ★ 2026-09-28：EXTRA_INC 允许追加头文件搜索路径（头文件对齐实验用
#   `-nostdinc -I<工厂同期 glibc 头>`；默认为空 ⇒ 主链行为逐字不变）。

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
    # ★★★ 2026-09-29（§0.34）：**就地抓取**，而不是"让调用方先跑"。
    #   病灶（CI 实测，commit 259abb43）：`.github/workflows/` 里**没有** fetch 步骤
    #   （而该目录在本机被代理拦截、无法推送修改）⇒ CI 上 `cache_tc/bootlin63` 永远缺
    #   ⇒ 本脚本 exit 4 ⇒ 213 个对象未产出 ⇒ XUnzip.o 未产出 ⇒
    #   `1to1-verify` / `1to1-qemu-behav` / `toolchain-ab` **三个 workflow 连锁红**。
    #   （09-27 那版绿，是因为当时还没有"工厂同期真头"这条要求。）
    #   修法：把"先跑 fetch"变成脚本**自己**做 —— `fetch_bootlin63.sh` 幂等
    #   （`.ok` 存在即秒返回），本地零开销，CI 首次多约 1~3 分钟。**不依赖改 workflow**。
    #   回退：删掉下面这 3 行（回到"缺失即 exit 4"）。
    echo "★★ 缺工厂同期真头（$CGM_GD）⇒ 就地抓取（幂等；CI 无 actions/cache）" >&2
    sh "$ROOT/tools/fetch_bootlin63.sh" >&2 \
        || { echo "★★ fetch_bootlin63 失败 ⇒ fail-closed（不静默降级到宿主头）" >&2; exit 4; }
fi
if [ ! -f "$CGM_GD/stdio.h" ] || [ ! -f "$CGM_GI/stddef.h" ]; then
    echo "★★ 抓取后**仍**缺真头（$CGM_GD）—— fail-closed，不降级" >&2
    exit 4
fi
CGM_HDR="-nostdinc -I$CGM_GI -I$CGM_GIF -I$CGM_GD"
CGM_FID_EXTRA="-fno-builtin-strcmp"
OPT="${OPT:--Os}"
# ★ 头集合**排在组件 -I 之后**（这里只有 src/compat 在它前面，是故意的：compat 是我们的垫片）。
CFLAGS="-c $OPT -w -Wno-error=implicit-function-declaration -I$WINROOT/src/compat ${CGM_HDR} ${EXTRA_INC:-} $CGM_FID_EXTRA $ARCH $FIDELITY"

# ★★★★★ 2026-09-29：**本脚本是编译口径的唯一来源**（纪律 69「同一规则禁止写两处」）。
#   别的门禁可以用 `sh tools/link_audit.sh --print-cflags xunzip` **读到同一份口径**。
#
#   为什么必须这样（真实代价）：`tools/check_obj_fresh.py` 的判据是"**用同一条流水线的口径**
#   重编一次再与产物逐符号对拍"。但它自己另抄了一份 flags，且漏掉 `${CGM_HDR}`（`-nostdinc`
#   + 工厂同期 glibc 2.24 真头）与 `-I src/compat`，还用 `-target arm-linux-gnueabihf.2.29`
#   ⇒ 编出的对象**本就不可能相同** ⇒ 报 `_ZN6TUnzip3GetEiP8ZIPENTRY 现编 816 / 链接后 808`
#   ⇒ **假阳性 FAIL**（反证：本脚本编的 `XUnzip.o` 该符号 = 808，与交付 ELF 逐项一致）。
#   ⇒ 修法：XUnzip 的编译**命令组件在这里定义一次**，真编译与 `--print-cflags` **共用**。
XUINC="$(winpath "$ROOT/src/upstream/xunzip/posix")"
XUFLAGS="-std=gnu++98 -fno-exceptions -I$XUINC"
case "$CC" in
  *zig*) XUCMODE=""        ;;   # zig cc 按扩展名自动按 C++ 编译 .cpp
  *)     XUCMODE="-x c++"  ;;   # 真 GCC 需要显式指定语言
esac

if [ "${1:-}" = "--print-cflags" ]; then
    # 供别的门禁**读**口径用（不是让人抄）。四个变量都是"命令组件"，
    # 调用方按 `CC + XUCMODE + XUFLAGS + CFLAGS + <src> -o <out>` 拼即可。
    echo "CC=$CC"
    echo "CFLAGS=$CFLAGS"
    echo "XUCMODE=$XUCMODE"
    echo "XUFLAGS=$XUFLAGS"
    exit 0
fi

mkdir -p "$OBJD" "$(dirname "$REP")"
rm -f "$OBJD"/*.o 2>/dev/null

ok=0; bad=0; total=0
: > "$ROOT/report/_link_bad.txt"

for f in "$SRCDIR"/*/*.c; do
    [ -f "$f" ] || continue
    total=$((total + 1))
    base=$(basename "$f" .c)
    # zig.exe（Windows 原生）要求入参与 -o 均为 Windows 原生路径
    nf=$(winpath "$f")
    no=$(winpath "$OBJD/$base.o")
    if $CC $CFLAGS "$nf" -o "$no" 2>"$ROOT/report/_link_err.txt"; then
        ok=$((ok + 1))
    else
        bad=$((bad + 1))
        echo "$f | $(grep -a -m1 'error:' "$ROOT/report/_link_err.txt" | head -c 180)" \
            >> "$ROOT/report/_link_bad.txt"
    fi
done

echo "== 编译: 总计 $total，成功 $ok，失败 $bad =="

# 上游组件对象（已预编译 / 本脚本内编译）一并纳入符号审计
XUPOBJ="${XUPOBJ:-$ROOT/src/upstream/xunzip/XUnzip.o}"
XUSRC="$ROOT/src/upstream/xunzip/unzip.cpp"

# ★★★ 2026-09-21（GAP 16.56）：**每次必重编**，不再用「源码哈希缓存」做跳过依据。
#
# ── 为什么废掉哈希缓存（这是本项目最贵的一次静默失效，代价 ≈ 十几轮）──
#   旧逻辑：`if [ ! -f .o ] || [ hash(src) != 记账值 ]; then 编; fi`
#   失效实况（2026-09-21 实测）：
#     · 记账哈希 == 当前源码哈希（9ee99732…）⇒ **永远判定"无需重编"**；
#     · 而仓库里的 `XUnzip.o`（147,896 B，**带 7 个 .debug_* 节 = 早期 -g 编的**）
#       **不是由当前源码编出来的** —— 同一份源码用本脚本的 CFLAGS 重编只要 **0.96 秒**，
#       编出来的对象与工厂命中 **21/30（7 个精确到字节）**，而那个陈旧对象只有 **11/30**。
#     · `build/rkgame.rebuilt.elf` 里的 zip 符号与**陈旧对象逐字一致** ⇒ 一直在链接它。
#   后果：`TUnzip::Open/Get/Unzip/Close`、`unz*many`、`unzStringFileNameCompare` 等
#        整整一族符号的 size 全部偏离工厂（1.5×~48×），而**我们的源码其实是对的**。
#   更早两轮还踩过它的两个前身：① 只在 .o 缺失时编；② 用 `-nt` 比时间戳（checkout 后
#     两边 mtime 都等于 checkout 时刻，判定不可靠）⇒ 已登记进 GAP 的"同一根因三次复发"。
#
# ── 为什么"缓存"本身就该废 ──
#   本对象编译 **0.96 秒**。任何缓存带来的收益都远小于它引入的"静默陈旧"风险：
#   陈旧对象**不报错、不告警**，只是让所有基于符号 size / 反汇编的判据读出**错误结论**
#   （实测：我因此把"源码不对"当结论，去做了一件完全没必要的大改）。
#
# ── 失败必须**硬失败** ──
#   旧逻辑编译失败只 `echo "XUnzip.o 编译失败"` 就继续 ⇒ 链接脚本见 .o 存在照样链接
#   ⇒ 推送时又把旧 .o 带上 ⇒ **陈旧对象永久循环**（`push_1to1.py` 当时还专门给它开了
#   "必须入库"的例外，等于把陈旧对象钉死在仓库里）。现在：编译失败 ⇒ 删掉目标 ⇒ 中止。
XUFAIL=0
if [ -f "$XUSRC" ]; then
    # ★ XUINC / XUFLAGS / XUCMODE 已在前面**定义一次**（与 `--print-cflags` 共用）。
    XUTMP="$XUPOBJ.new"
    rm -f "$XUTMP"
    # shellcheck disable=SC2086
    $CC $XUCMODE $XUFLAGS $CFLAGS "$(winpath "$XUSRC")" -o "$(winpath "$XUTMP")" 2>>"$ROOT/report/_link_bad.txt"
    if [ -s "$XUTMP" ]; then
        mv -f "$XUTMP" "$XUPOBJ"
        echo "XUnzip.o 已重编（$(wc -c < "$XUPOBJ" 2>/dev/null || echo '?') B，源码 hash $(sha256sum "$XUSRC" 2>/dev/null | cut -c1-12)）"
        sha256sum "$XUSRC" 2>/dev/null | cut -d' ' -f1 > "$ROOT/src/upstream/xunzip/.XUnzip.src.sha256"
    else
        rm -f "$XUTMP" "$XUPOBJ"
        echo "★★ XUnzip.o 编译失败 —— 已删除目标对象并中止（禁止链接陈旧对象）"
        echo "   详见 $ROOT/report/_link_bad.txt"
        XUFAIL=1
    fi
else
    echo "★★ 缺 $XUSRC —— 中止"
    XUFAIL=1
fi

if [ "$XUFAIL" = 1 ]; then
    exit 1
fi

: > "$ROOT/report/_link_syms.tsv"
if [ "$ok" -gt 0 ]; then
    winobj=$(winpath "$OBJD")
    # shellcheck disable=SC2086
    $PY "$(winpath "$ROOT/tools/elf_syms.py")" "$winobj"/*.o > "$ROOT/report/_link_syms.tsv" 2>/dev/null
    if [ -f "$XUPOBJ" ]; then
        $PY "$(winpath "$ROOT/tools/elf_syms.py")" "$(winpath "$XUPOBJ")" >> "$ROOT/report/_link_syms.tsv" 2>/dev/null
    fi
    # 上游组件对象（stb / mxml / mp3）：若缺失则先构建
    UPOUT="${UPOBJD:-$ROOT/build/upstream}"
    if [ -z "$(ls -A "$UPOUT"/*.o 2>/dev/null)" ]; then
        echo "== 上游对象缺失，调用 build_upstream.sh =="
        CC="$CC" PY="$PY" sh "$ROOT/tools/build_upstream.sh" "$UPOUT" >/dev/null 2>&1
    fi
    if [ -n "$(ls -A "$UPOUT"/*.o 2>/dev/null)" ]; then
        $PY "$(winpath "$ROOT/tools/elf_syms.py")" "$(winpath "$UPOUT")"/*.o >> "$ROOT/report/_link_syms.tsv" 2>/dev/null
    fi
    # 工厂 LOCAL 数据对象别名：拼接镜像+别名后单文件汇编（.set 引用跨段基址需同 TU）
    LOCALS="$ROOT/src/data/factory_local.S"
    LOCOBJ="$ROOT/build/factory_local.o"   # 不放 build/obj/：那里的 *.o 会被上面的 glob 重复扫描
    if [ -f "$LOCALS" ]; then
        IMG="$ROOT/src/data/factory_image.S"
        ALLS="$ROOT/build/obj/factory_all.S"
        cat "$IMG" "$LOCALS" > "$ALLS"
        DATINC=$(winpath "$ROOT/src/data")
        $CC $ARCH -c -I"$DATINC" "$(winpath "$ALLS")" -o "$(winpath "$LOCOBJ")" 2>>"$ROOT/report/_link_bad.txt" \
          && $PY "$(winpath "$ROOT/tools/elf_syms.py")" "$(winpath "$LOCOBJ")" >> "$ROOT/report/_link_syms.tsv" 2>/dev/null \
          || echo "factory_all 汇编失败"
    fi
fi
echo "== 符号条目: $(wc -l < "$ROOT/report/_link_syms.tsv") =="

$PY "$(winpath "$ROOT/tools/link_audit.py")" \
    "$(winpath "$ROOT/report/_link_syms.tsv")" \
    "$(winpath "$REP")"
rc=$?
echo "报告: $REP"
exit $rc
