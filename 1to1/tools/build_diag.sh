#!/bin/sh
# ============================================================
# build_diag.sh —— 构建**设备端诊断版** rkgame（不影响交付版）
#
# 产出：build/rkgame.diag
#
# 与交付版的唯一区别（三处，全部是**链接/编译期**开关，零源码改动）：
#   ① src/proprietary/**/*.c 与 xunzip 用 `-finstrument-functions` 编译
#      ⇒ 每个函数进出都进环形缓冲（768 KB，约 6.5 万帧历史）
#   ② 链接加 `-Wl,-wrap=<libc 符号>` × 65（zig 只认单横线；GCC 用 `--wrap=`）
#      ⇒ 文件/ioctl/mmap/dlopen/线程/时间/信号 全部留痕
#   ③ 额外链入 src/diag/cgm_diag.o + cgm_wrap.o（诊断仪自身）
#
# ★ 为什么不做成 LD_PRELOAD：设备启动链全是原厂文件（红线），
#   我们**没有任何地方**能注入环境变量 ⇒ 只能编进自己。
#
# ★ 为什么不给诊断仪文件加 -finstrument-functions：
#   GCC 有 `-finstrument-functions-exclude-file-list`，而 **clang/zig 没有**；
#   本脚本改用"诊断仪单独一次编译、不带该标志" ⇒ 同一份脚本在 GCC 与 zig 下都对
#   （否则诊断仪自己会被插桩 ⇒ 无限递归）。
#
# 用法：
#   CC="<zig> cc" OPT=-Os sh tools/build_diag.sh [输出路径]
#   DIAG_LEVEL=2 影响不了产物，只影响设备上的 cfg.ini 默认值说明
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CC="${CC:-arm-linux-gnueabihf-gcc}"
PY="${PY:-python}"
OPT="${OPT:--Os}"
OUT="${1:-$ROOT/build/rkgame.diag}"

winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
WINROOT=$(winpath "$ROOT")

case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic" ;;
esac
# ★ 与工厂/交付版**逐字一致**的保真标志（否则崩溃形态会变，诊断就失真了）
FIDELITY="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
INST="-finstrument-functions"
BASE="-c $OPT -w -Wno-error=implicit-function-declaration $ARCH $FIDELITY"

OBJD="$ROOT/build/diag_obj"      # 插桩后的专有函数对象
SELFD="$ROOT/build/diag_self"    # 诊断仪自身（**不插桩**）
mkdir -p "$OBJD" "$SELFD" "$ROOT/report"
rm -f "$OBJD"/*.o "$SELFD"/*.o 2>/dev/null

# ★★★ 拉开 wrap 列表与自检门禁 **在编译之前**
#   失败要快：旧版本把它放在 [4/5]，一个列表错误要先白编 213 个文件。
#   门禁本体在 tools/diag_wraps.sh（单独一个文件 ⇒ 可独立反证）。
. "$ROOT/tools/diag_wraps.sh" || exit 11

echo "== [1/5] 编译诊断仪自身（不插桩，避免递归）=="
SELFOBJS=""
for f in "$ROOT"/src/diag/*.c; do
    [ -f "$f" ] || continue
    b=$(basename "$f" .c)
    o="$SELFD/$b.o"
    if $CC $BASE -I"$(winpath "$ROOT/src/diag")" -I"$WINROOT/src/compat" "$(winpath "$f")" -o "$(winpath "$o")" 2>"$ROOT/report/diag_cc_err.txt"; then
        SELFOBJS="$SELFOBJS $o"
        echo "   ✓ $b.o  ($(wc -c < "$o" 2>/dev/null) B)"
    else
        echo "   ✗ $b 编译失败："; sed -n '1,12p' "$ROOT/report/diag_cc_err.txt"; exit 5
    fi
done
[ -s "$SELFD/cgm_diag.o" ] || { echo "!!! 缺 cgm_diag.o —— 'goto' 语义：诊断仪没编出来就别继续" >&2; exit 5; }
[ -s "$SELFD/cgm_wrap.o" ] || { echo "!!! 缺 cgm_wrap.o" >&2; exit 5; }

echo "== [2/5] 编译专有函数（-finstrument-functions）=="
n=0; bad=0; FAILED=""
for f in "$ROOT"/src/proprietary/*/*.c; do
    [ -f "$f" ] || continue
    n=$((n + 1))
    b=$(basename "$f" .c)
    if ! $CC $BASE $INST -I"$WINROOT/src/compat" "$(winpath "$f")" -o "$(winpath "$OBJD/$b.o")" 2>>"$ROOT/report/diag_cc_err.txt"; then
        bad=$((bad + 1)); FAILED="$FAILED $b"
    fi
done
echo "   插桩对象 $n 个，失败 $bad 个"
[ "$bad" = "0" ] || { echo "!!! 有编译失败（$FAILED）—— 诊断产物不可信，中止" >&2; exit 6; }

echo "== [3/5] 编译 xunzip（-finstrument-functions；zip 路径是重点观测区）=="
DIAG_XU="$ROOT/build/diag_XUnzip.o"
rm -f "$DIAG_XU"
if [ -f "$ROOT/src/upstream/xunzip/unzip.cpp" ]; then
    $CC -x c++ $BASE $INST -std=gnu++98 -fno-exceptions \
        -I"$(winpath "$ROOT/src/upstream/xunzip/posix")" \
        "$(winpath "$ROOT/src/upstream/xunzip/unzip.cpp")" -o "$(winpath "$DIAG_XU")" \
        2>>"$ROOT/report/diag_cc_err.txt" || { echo "!!! xunzip 插桩编译失败" >&2; exit 7; }
    echo "   ✓ diag_XUnzip.o ($(wc -c < "$DIAG_XU") B，交付版为 $(wc -c < "$ROOT/src/upstream/xunzip/XUnzip.o" 2>/dev/null || echo '?') B)"
else
    echo "   （跳过：无 unzip.cpp）"; DIAG_XU="$ROOT/src/upstream/xunzip/XUnzip.o"
fi

echo "== [4/5] wrap 列表（已在脚本开头 source tools/diag_wraps.sh）=="
echo "   wrap 符号 $cnt 个（形式 $WFLAG<sym>）"

echo "== [5/5] 链接 =="
DIAG_OBJD="$OBJD" \
DIAG_XUNZIP="$DIAG_XU" \
DIAG_EXTRA="$SELFOBJS" \
DIAG_LDFLAGS="$LDF" \
CC="$CC" PY="$PY" GLIBC_VER="${GLIBC_VER:-2.7}" \
sh "$ROOT/tools/link_full.sh" "$OUT" || { echo "!!! 链接失败，详见 report/link_full_err.txt" >&2; exit 8; }

echo
echo "================ 诊断产物自检 ================"
if [ -f "$OUT" ]; then
    echo " 产物 = $OUT ($(wc -c < "$OUT") B)  交付版 = $(wc -c < "$ROOT/build/rkgame.rebuilt.elf" 2>/dev/null || echo '?') B"
    "$PY" "$(winpath "$ROOT/tools/abi_check.py")" "$(winpath "$OUT")" 2>&1 | tail -8
    h=$(sha256sum "$OUT" 2>/dev/null | cut -c1-16)
    echo " sha256(前16) = $h"
    # ★ 诊断仪是否真的被链进去了（不要让"没链上"看起来像"没触发"）
    if "$PY" - "$(winpath "$OUT")" <<'PYEOF' 2>/dev/null
import sys, struct
d = open(sys.argv[1], 'rb').read()
es = struct.unpack_from('<H', d, 46)[0]; sh = struct.unpack_from('<I', d, 32)[0]
n = struct.unpack_from('<H', d, 48)[0]
S = [struct.unpack_from('<10I', d, sh + i * es) for i in range(n)]
names = set()
for s in S:
    if s[1] != 2:
        continue
    stro = S[s[6]][4]; ent = s[9] or 16
    for j in range(s[5] // ent):
        nmn, val, sz, inf, oth, shx = struct.unpack_from('<IIIBBH', d, s[4] + j * ent)
        if nmn == 0:
            continue
        k = d.index(b'\x00', stro + nmn)
        names.add(d[stro + nmn:k].decode('utf-8', 'replace'))
need = ['cgm_diag_boot', '__wrap_open', '__wrap_ioctl', '__wrap___libc_start_main',
        '__cyg_profile_func_enter', '__cyg_profile_func_exit', 'cgm_putline']
miss = [x for x in need if x not in names]
if miss:
    print('   ✗ 诊断仪符号缺失: %s' % miss); sys.exit(1)
print('   ✓ 诊断仪 7 个关键符号全部落进产物（cgm_diag_boot / __wrap_open / __wrap_ioctl /')
print('     __wrap___libc_start_main / __cyg_profile_func_enter/exit / cgm_putline）')
sys.exit(0)
PYEOF
    then :; else echo "   ✗ 诊断仪未完整链入 —— 产物不可用于诊断（这必须是硬失败，否则设备上会静默 0 日志）"; exit 9; fi
else
    echo " !! 无产物"; exit 10
fi
