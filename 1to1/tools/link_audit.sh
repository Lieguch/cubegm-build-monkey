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
OBJD="$ROOT/build/obj"
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
CFLAGS="-c $OPT -w -Wno-error=implicit-function-declaration -I$WINROOT/src/compat $ARCH $FIDELITY"

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
XUPOBJ="$ROOT/src/upstream/xunzip/XUnzip.o"
# ★★ 血泪（P5 第七个真实分歧排查时踩到两次）：
#   ① 原先只在 .o **缺失**时编译 ⇒ 改了 unzip.cpp 却不重编；
#   ② 改成 `-nt`（源码更新）后**在 CI 上仍然失效** —— 仓库里残留着旧的 `XUnzip.o`
#      （push_1to1.py 把 `.o` 当构建产物**排除**，推送不了新对象），而 git checkout 会把
#      `unzip.cpp` 与 `XUnzip.o` 的时间戳都设成 checkout 时刻，先后不可靠。
#   ⇒ 改用**源码内容 hash 缓存**：hash 与上次不同就重编。hash 文件是文本，会被正常推送。
XUSRC="$ROOT/src/upstream/xunzip/unzip.cpp"
XUHASH="$ROOT/src/upstream/xunzip/.XUnzip.src.sha256"
_xu_cur=""
[ -f "$XUSRC" ] && _xu_cur=$(sha256sum "$XUSRC" 2>/dev/null | cut -d' ' -f1)
_xu_old=$(cat "$XUHASH" 2>/dev/null || echo "")
if [ ! -f "$XUPOBJ" ] || [ -z "$_xu_cur" ] || [ "$_xu_cur" != "$_xu_old" ]; then
    XUSRC="$ROOT/src/upstream/xunzip/unzip.cpp"
    if [ -f "$XUSRC" ]; then
        XUINC=$(winpath "$ROOT/src/upstream/xunzip/posix")
        case "$CC" in
          *zig*)
            # zig cc 按扩展名自动按 C++ 编译 .cpp
            XUXTRA="-std=gnu++98 -fno-exceptions -I$XUINC"
            $CC $CFLAGS $XUXTRA "$(winpath "$XUSRC")" -o "$(winpath "$XUPOBJ")" 2>>"$ROOT/report/_link_bad.txt" && { echo "XUnzip.o 已编译"; echo "$_xu_cur" > "$XUHASH"; } || echo "XUnzip.o 编译失败"
            ;;
          *)
            XUXTRA="-std=gnu++98 -fno-exceptions -I$(winpath "$ROOT/src/upstream/xunzip/posix")"
            $CC -x c++ $CFLAGS $XUXTRA "$(winpath "$XUSRC")" -o "$(winpath "$XUPOBJ")" 2>>"$ROOT/report/_link_bad.txt" && { echo "XUnzip.o 已编译"; echo "$_xu_cur" > "$XUHASH"; } || echo "XUnzip.o 编译失败"
            ;;
        esac
    fi
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
    UPOUT="$ROOT/build/upstream"
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
