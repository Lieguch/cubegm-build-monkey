#!/bin/sh
# ============================================================
# link_full.sh — P3 三期：完整链接（全部对象 + 工厂数据镜像 + 工厂布局）
#
# 输入（均已存在）：
#   build/obj/*.o         213 个专有函数对象
#   src/upstream/xunzip/XUnzip.o      XUnzip（C++ 移植）
#   build/upstream/*.o     stb / mxml / mp3 / libiconv
#   build/factory_local.o  factory_image.S + factory_local.S 汇编产物（工厂字节镜像 + 别名）
# 输出：build/rkgame.rebuilt.elf
#
# 说明：
#   · -nostdlib：不拉 CRT（数据段布局由脚本钉死；libc 符号留 UNDEF 由 -z undefs 放行）
#   · -T linker/factory.ld：复刻工厂 VMA（代码里有烧死的绝对地址）
#   · 本步骤用于验证「能否链接 + 段地址是否正确」，运行期仍需 P4/P5/P6
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CC="${CC:-arm-linux-gnueabihf-gcc}"
OUT="${1:-$ROOT/build/rkgame.rebuilt.elf}"
PY="${PY:-python}"

winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }

case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic" ;;
esac

# 静态试链用的 libstdc++ 替身（operator new/delete）
CXXOBJ="$ROOT/build/cxx_ops.o"
if [ ! -f "$CXXOBJ" ] || [ "$ROOT/src/compat/cxx_ops.c" -nt "$CXXOBJ" ]; then
    $CC -c -O1 -w $ARCH "$(winpath "$ROOT/src/compat/cxx_ops.c")" -o "$(winpath "$CXXOBJ")" 2>/dev/null \
      && echo "  cxx_ops.o 已编译"
fi

# 工厂数据镜像对象：每次链接前重建（避免用旧的段名/旧别名）
ALLS="$ROOT/build/factory_all.S"
cat "$ROOT/src/data/factory_image.S" "$ROOT/src/data/factory_local.S" > "$ALLS"
$CC $ARCH -c -I"$(winpath "$ROOT/src/data")" "$(winpath "$ALLS")" -o "$(winpath "$ROOT/build/factory_local.o")" \
  && echo "  factory_local.o 已重建" || { echo "  factory_local.o 汇编失败"; exit 1; }

OBJS=""
for o in "$ROOT"/build/obj/*.o; do [ -f "$o" ] && OBJS="$OBJS $o"; done
[ -f "$CXXOBJ" ] && OBJS="$OBJS $CXXOBJ"
for o in "$ROOT"/build/upstream/*.o; do [ -f "$o" ] && OBJS="$OBJS $o"; done
[ -f "$ROOT/src/upstream/xunzip/XUnzip.o" ] && OBJS="$OBJS $ROOT/src/upstream/xunzip/XUnzip.o"
[ -f "$ROOT/build/factory_local.o" ] && OBJS="$OBJS $ROOT/build/factory_local.o"
n=$(printf '%s' "$OBJS" | wc -w)
echo "== 对象数: $n =="

# 全部对象转 Windows 路径（zig.exe 原生程序）
WOBJS=""
for o in $OBJS; do WOBJS="$WOBJS $(winpath "$o")"; done

echo "== 链接 =="
# shellcheck disable=SC2086
$CC $ARCH -no-pie \
    -Wl,-T,"$(winpath "$ROOT/linker/factory.ld")" \
    -Wl,-z,undefs -Wl,--build-id=none \
    $WOBJS -o "$(winpath "$OUT")" 2>"$ROOT/report/link_full_err.txt"
rc=$?
echo "链接 rc=$rc"
if [ -f "$OUT" ]; then
    ls -la "$OUT"
    echo "== 段地址核对 =="
    $PY "$(winpath "$ROOT/tools/verify_layout.py")" "$(winpath "$OUT")" \
        "$(winpath "$ROOT/ledger/factory_globals.tsv")" 2>/dev/null | head -24
else
    echo "（无产物）错误摘要："
    grep -aE "error|undefined|overlap" "$ROOT/report/link_full_err.txt" | head -12
fi
exit $rc
