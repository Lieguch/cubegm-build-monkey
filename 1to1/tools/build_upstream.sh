#!/bin/sh
# ============================================================
# build_upstream.sh — 编译上游组件（1:1 符号级对齐工厂）
#
# 组件与证据：
#   stb   : stb_truetype v1.26（头文件版本宏）→ C 编译
#   mxml  : mini-XML v3.3.1（工厂 16 个静态函数全集比对）→ C 编译
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
CFLAGS="-c -O1 -w -fno-strict-aliasing $ARCH"

say() { echo "== $* =="; }

# ---------- 1) stb_truetype ----------
say "stb_truetype v1.26"
SDL="$ROOT/src/upstream/stb"
if $CC $CFLAGS -I"$(winpath "$SDL")" "$(winpath "$SDL/stb_truetype_impl.c")" -o "$(winpath "$OUT/stb_truetype.o")" 2>"$OUT/_err_stb.txt"; then
    echo "  OK stb_truetype.o"
else
    echo "  FAIL stb"; head -3 "$OUT/_err_stb.txt"
fi

# ---------- 2) mini-XML v3.3.1 ----------
say "mini-XML v3.3.1"
MD="$ROOT/src/upstream/mxml"
mxml_ok=0; mxml_bad=0
for f in "$MD"/mxml-*.c; do
    [ -f "$f" ] || continue
    b=$(basename "$f" .c)
    # testmxml.c 是示例程序，不编
    if $CC $CFLAGS -I"$(winpath "$MD")" "$(winpath "$f")" -o "$(winpath "$OUT/mxml_$b.o")" 2>"$OUT/_err_$b.txt"; then
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
    if $CC $CFLAGS $MP3EXTRA -I"$(winpath "$PD")" -I"$(winpath "$PD/pub")" -I"$(winpath "$PD/real")" \
         "$(winpath "$f")" -o "$(winpath "$OUT/mp3_$b.o")" 2>"$OUT/_err_mp3_$b.txt"; then
        mp3_ok=$((mp3_ok + 1))
    else
        mp3_bad=$((mp3_bad + 1)); echo "  FAIL $b"; head -3 "$OUT/_err_mp3_$b.txt"
    fi
done
echo "  mp3: OK $mp3_ok / FAIL $mp3_bad"

# ---------- 4) GNU libiconv 1.17（真源码，非桩） ----------
say "GNU libiconv 1.17"
LD="$ROOT/src/upstream/libiconv17"
if [ -f "$LD/iconv.c" ]; then
    if $CC $CFLAGS -I"$(winpath "$LD")" "$(winpath "$LD/iconv.c")" -o "$(winpath "$OUT/libiconv_iconv.o")" 2>"$OUT/_err_libiconv.txt"; then
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
    if $CC $CFLAGS -I"$(winpath "$LD")" -I"$(winpath "$LC")" "$(winpath "$LC/localcharset.c")" -o "$(winpath "$OUT/libiconv_localcharset.o")" 2>"$OUT/_err_localcharset.txt"; then
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
