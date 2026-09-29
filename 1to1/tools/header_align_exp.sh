#!/bin/sh
# ============================================================
# header_align_exp.sh —— 单变量实验：**把编译器头文件换成工厂同期 glibc 2.24 头**
#
# ## 依据（2026-09-28 四路探针，全部编译成功）
#   | 头文件                | -Os        | -O2        |
#   |-----------------------|------------|------------|
#   | zig 自带 glibc 头      | putc/getc  | putc/getc  |
#   | **工厂同期 glibc 2.24**| **_IO_putc/_IO_getc** | **_IO_putc/_IO_getc** |
#   ⇒ 决定 `.dynsym` 那 8 项差异的是**头文件**，与编译器族/优化档**都无关**。
#   glibc 的 `features.h` 逐字写着开关：`__USE_EXTERN_INLINES` 需要 `__extern_inline`
#   （真 glibc 的 `sys/cdefs.h` 提供），zig 自带头把它裁掉了。
#
# ## 单变量纪律
#   只加 `-nostdinc -I<cache_tc/bootlin63/.../sysroot/usr/include>`（头文件），
#   编译器、优化档、链接驱动、库、源码**全部不动**。
#   ★ 必须 `-I` 而非 `-isystem`：实测 zig 把自带 libc 头当 internal-isystem，
#     `-isystem` 排在它后面 ⇒ 无效（仍出 `putc`）。
#
# ## 判据
#   ① 编译 213/213；② link rc=0；③ `.dynsym` 的 `putc/getc` 变成 `_IO_putc/_IO_getc`；
#   ④ **行为尺 DIVERGE 必须 < 基线**（基线由 tools/ruler_baseline.py 从当前交付产物的权威报告
#      取，★ 不硬编码 —— 纪律 50），否则回退。
# ============================================================
set -u
ROOT="D:/output/rkgame-1to1"
cd "$ROOT" || exit 9
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
ZIGEXE="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe"
CC="$ZIGEXE cc"
export ZIG_GLOBAL_CACHE_DIR="$ROOT/build/_zigcache_ha"
mkdir -p "$ZIG_GLOBAL_CACHE_DIR" build/hdr_obj build/hdr_upstream report

TC="$ROOT/cache_tc/bootlin63/arm-buildroot-linux-gnueabihf/sysroot"
INC="-nostdinc -I$TC/usr/include"
[ -f "$TC/usr/include/stdio.h" ] || { echo "!! 缺工厂同期头：$TC/usr/include/stdio.h" >&2; exit 3; }

if [ -n "${RERUN_PROP:-}" ]; then rm -rf build/hdr_obj; fi
echo "== 1) 并行编译专有对象（flags 同主链 + EXTRA_INC）=="
ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"
FID="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
CFLAGS="-c -Os -w -Wno-error=implicit-function-declaration -I$ROOT/src/compat $INC $ARCH $FID"
mkdir -p build/hdr_obj; : > report/_ha_err.txt
export CCZ="$CC" CFLAGS
find "$ROOT/src/proprietary" -name '*.c' -print0 \
  | xargs -0 -P 8 -I{} sh -c 'b=$(basename "$1" .c); $CCZ $CFLAGS "$1" -o "build/hdr_obj/$b.o" 2>>report/_ha_err.txt' _ {}
N=$(ls -1 build/hdr_obj/*.o 2>/dev/null | wc -l)
echo "   专有对象 $N/213"
[ "$N" -ge 200 ] || { echo "★★ 编译失败过多"; head -8 report/_ha_err.txt; exit 5; }

echo "== 2) XUnzip（C++，同头文件）=="
$CC -x c++ $CFLAGS -std=gnu++98 -fno-exceptions -I"$ROOT/src/upstream/xunzip/posix" \
    "$ROOT/src/upstream/xunzip/unzip.cpp" -o build/hdr_xunzip.o 2>>report/_ha_err.txt
echo "   XUnzip $(stat -c%s build/hdr_xunzip.o 2>/dev/null || echo 0) B"

# ★ 2026-09-28 实测教训：EXTRA_INC 的 `-I<glibc 头>` 会**盖住 libiconv 自己的 iconv.h**
#   （命令行里 EXTRA_INC 的 -I 排在组件 -I 之前）⇒ `libiconv_close` 未定义、链接失败。
#   准则：**头文件对齐只作用于专有代码**（那 8 项差异本就来自应用代码）；
#   第三方库保留各自 vendored 的权威头。
echo "== 3) 上游（保留各自权威头，不吃 EXTRA_INC）=="
rm -rf build/hdr_upstream
CC="$CC" PY="$PY" SYSROOT="" sh tools/build_upstream.sh build/hdr_upstream > report/_ha_up.txt 2>&1
echo "   上游对象 $(ls -1 build/hdr_upstream/*.o 2>/dev/null | wc -l)"

echo "== 4) 链接（ld.lld，其余与主链逐字一致）=="
LINK_DRIVER=lld ZIG_BIN="$ZIGEXE" CC="$CC" SYSROOT="" PY="$PY" \
  DIAG_OBJD="$ROOT/build/hdr_obj" UPOBJD="$ROOT/build/hdr_upstream" \
  DIAG_XUNZIP="$ROOT/build/hdr_xunzip.o" \
  sh tools/link_full.sh build/ab/hdr24.elf > report/_ha_link.txt 2>&1
rc=$?
echo "   link rc=$rc"
[ "$rc" = "0" ] && [ -s build/ab/hdr24.elf ] || { echo "★★ 链接失败"; tail -12 report/link_full_err.txt; exit 5; }
$PY tools/probe_link_binding.py build/ab/hdr24.elf

echo "== 5) 行为尺（唯一判据）=="
# ★ 基线自证（纪律 50）：不硬编码，从当前交付产物自己的权威报告取；取不到即 fail-closed。
if [ -n "${BASE_DV:-}" ]; then
    echo "   基线（外部注入）：BASE_DV=$BASE_DV ${BASE_LINE:-}"
else
    BASE_LINE=$($PY tools/ruler_baseline.py) || { echo "★★ 取不到行为尺基线（纪律 50 fail-closed）" >&2; exit 7; }
    BASE_DV=$(printf '%s\n' "$BASE_LINE" | awk '{print $5}')
    echo "   基线（就地取值）：$BASE_LINE"
fi
export BASE_DV BASE_LINE
$PY tools/diff_exec.py --batch --steps 3000 --ours build/ab/hdr24.elf --out report/_ha_diff.txt > report/_ha_diff_stdout.txt 2>&1
grep -a '共有函数\|汇总：PASS\|自洽校验' report/_ha_diff.txt
echo "== 6) 判决 =="
$PY - <<'PYE'
import io, os, re
t = io.open('report/_ha_diff.txt', encoding='utf-8', errors='replace').read()
m = re.search(r'汇总：PASS\s+(\d+)\s*｜\s*DIVERGE\s+(\d+)', t)
if not m:
    print('   !! 解析失败'); raise SystemExit(6)
pa, dv = int(m.group(1)), int(m.group(2))
base = int(os.environ['BASE_DV'])   # ★ 纪律 50：基线由 ruler_baseline.py 提供，不硬编码
print('   基线：%s' % os.environ.get('BASE_LINE', '(外部注入)').strip())
print('   本次（zig头换工厂同期glibc头）：PASS %d ｜ DIVERGE %d' % (pa, dv))
v = 'ADOPT' if dv < base else 'REJECT'
print('   ★ 判决：%s（DIVERGE %d vs 基线 %d）' % (v, dv, base))
io.open('report/header_align_verdict.txt', 'w', encoding='utf-8').write(
    '%s: PASS %d DIVERGE %d (baseline %d)\n' % (v, pa, dv, base))
PYE
