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
#   CGM_UPGRADE=both|sram|evdev|0（默认 **both**）—— R259：诊断版默认开 both，
#     因为 DIAG-RUNBOOK 第十一节的 evdev/sram 观测点依赖升级模块在场；
#     传 0 得纯净 1:1 诊断版（用于"交付口径本身出问题"的场景）。
#     规则与交付版共用 tools/cgm_upgrade_flags.sh（纪律 69）。
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# ★ 2026-10-04（第 138 轮）改为引用**唯一权威探测** tools/cgm_cc_probe.sh。
#   原为 `CC="${CC:-arm-linux-gnueabihf-gcc}"`（**硬编**）：三个环境各自只装其中一种
#   （云开发只有 ziglang / CI 只有 arm-gcc / 本机只有 zig.exe）
#   ⇒ 硬编任何一种都会在其余两个失败。实测已连续三轮踩坑：
#     build_guest_shim.sh 静默降级、build_upstream.sh 的 XUnzip 自举失败、
#     而本脚本报 `arm-linux-gnueabihf-gcc: command not found` 且无产物。
#   收敛到一处的收益：以后新增构建脚本只需 source 它，不会再复制第 5 份探测代码。
if [ -z "${CC:-}" ] && [ -z "${CC_ARM:-}" ]; then
    . "$(cd "$(dirname "$0")" && pwd)/cgm_cc_probe.sh" \
        || { echo "!! 编译器探测失败（见上方说明）" >&2; exit 13; }
fi
PY="${PY:-python}"
OPT="${OPT:--Os}"
OUT="${1:-$ROOT/build/rkgame.diag}"

winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
WINROOT=$(winpath "$ROOT")
# ★ R259：升级开关规则（与 link_audit.sh 共用唯一来源 tools/cgm_upgrade_flags.sh）
CGM_UPGRADE="${CGM_UPGRADE:-both}"
. "$(dirname "$0")/cgm_upgrade_flags.sh" || { echo "!! 缺 tools/cgm_upgrade_flags.sh" >&2; exit 14; }

case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic" ;;
esac
# ★ 与工厂/交付版**逐字一致**的保真标志（否则崩溃形态会变，诊断就失真了）
FIDELITY="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
INST="-finstrument-functions"
BASE="-c $OPT -w -Wno-error=implicit-function-declaration $ARCH $FIDELITY"
# ★ R259：专有函数 + 升级模块的编译口径 = BASE + 升级宏/头（诊断仪自身**不用**它）
PRIBASE="$BASE$CGM_DEFS $CGM_HDR"

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
    if ! $CC $PRIBASE $INST -I"$WINROOT/src/compat" "$(winpath "$f")" -o "$(winpath "$OBJD/$b.o")" 2>>"$ROOT/report/diag_cc_err.txt"; then
        bad=$((bad + 1)); FAILED="$FAILED $b"
    fi
done
echo "   插桩对象 $n 个，失败 $bad 个"
[ "$bad" = "0" ] || { echo "!!! 有编译失败（$FAILED）—— 诊断产物不可信，中止" >&2; exit 6; }

echo "== [2b/5] 编译升级模块（**不插桩**：poll 每帧/15ms 调，插桩会以每秒上百帧刷爆 65536 帧环形缓冲，冲掉真正的崩溃前历史）=="
if [ "$CGM_UP_ANY" = "1" ]; then
    for f in "$ROOT"/src/upgrade/*.c; do
        [ -f "$f" ] || continue
        b=$(basename "$f" .c)
        [ "$b" = "selftest" ] && continue      # 自测 main 不进产物
        if $CC $PRIBASE "$(winpath "$f")" -o "$(winpath "$OBJD/cgm_$b.o")" 2>>"$ROOT/report/diag_cc_err.txt"; then
            echo "   ✓ cgm_$b.o（$(wc -c < "$OBJD/cgm_$b.o") B，未插桩，观测点在场）"
        else
            echo "   ✗ cgm_$b 编译失败："; sed -n '1,8p' "$ROOT/report/diag_cc_err.txt"; exit 6
        fi
    done
else
    echo "   （CGM_UPGRADE=0 ⇒ 纯净 1:1 诊断版，无 evdev/sram 观测点）"
fi

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
