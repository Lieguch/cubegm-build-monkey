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
CFLAGS="-c -O1 -w -Wno-error=implicit-function-declaration -I$WINROOT/src/compat -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"

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

: > "$ROOT/report/_link_syms.tsv"
if [ "$ok" -gt 0 ]; then
    winobj=$(winpath "$OBJD")
    # shellcheck disable=SC2086
    $PY "$(winpath "$ROOT/tools/elf_syms.py")" "$winobj"/*.o > "$ROOT/report/_link_syms.tsv" 2>/dev/null
fi
echo "== 符号条目: $(wc -l < "$ROOT/report/_link_syms.tsv") =="

$PY "$(winpath "$ROOT/tools/link_audit.py")" \
    "$(winpath "$ROOT/report/_link_syms.tsv")" \
    "$(winpath "$REP")"
rc=$?
echo "报告: $REP"
exit $rc
