#!/bin/sh
# ============================================================
# link_probe.sh — P3 试链探针
#
# 步骤：
#   1) 编译全部 src/proprietary/**.c → build/obj/*.o
#   2) 汇编 src/data/factory_image.S（工厂数据镜像 + 1094 个符号别名）
#   3) 用 linker/factory.ld（复刻工厂 VMA）链接成 ELF
#   4) 过 tools/abi_check.py（P4 ABI 门禁）
#
# 说明：上游组件（MP3*/XUnzip_*/mxml*）与少数 Ghidra 合成名尚未供应；
#       探针用 --unresolved-symbols=ignore-all 仍产出 ELF，并把真实缺口列出。
#
# 用法：
#   CC="<zig> cc" PY=python sh tools/link_probe.sh [输出 ELF]
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CC="${CC:-arm-linux-gnueabihf-gcc}"
PY="${PY:-python}"
OUT="${1:-$ROOT/build/rkgame.rebuilt}"
OBJD="$ROOT/build/obj"
REP="$ROOT/report/link_probe.txt"

# -m = Windows 风格但用正斜杠（D:/...）：zig 接受，且不破坏 bash 通配
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
WINROOT=$(winpath "$ROOT")

CFLAGS="-c -O1 -w -Wno-error=implicit-function-declaration -I$WINROOT/src/compat -target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"
LDFLAGS="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon -no-pie -ldl -lpthread -lm"
LDFLAGS="$LDFLAGS -Wl,-T,$(winpath "$ROOT/linker/factory.ld")"
# 未解析符号：GNU ld 与 lld(zig) 开关不同
case "$CC" in
  *zig*) UNDEF="-Wl,-z,undefs" ;;
  *)     UNDEF="-Wl,--unresolved-symbols=ignore-all -Wl,--warn-unresolved-symbols" ;;
esac
LDFLAGS="$LDFLAGS $UNDEF" 

mkdir -p "$OBJD" "$ROOT/build" "$ROOT/report"
: > "$REP"

{
  echo "============================================================"
  echo "P3 试链探针   CC=$CC"
  echo "============================================================"

  ok=0; bad=0; total=0
  for f in "$ROOT"/src/proprietary/*/*.c; do
      [ -f "$f" ] || continue
      total=$((total + 1))
      no=$(winpath "$OBJD/$(basename "$f" .c).o")
      if $CC $CFLAGS "$(winpath "$f")" -o "$no" 2>/dev/null; then
          ok=$((ok + 1))
      else
          bad=$((bad + 1)); echo "  [compile-fail] $(basename "$f")"
      fi
  done
  echo "1) 编译函数对象: $ok / $total"

  # ---- 数据镜像 ----
  ( cd "$ROOT/src/data" && $CC $CFLAGS "factory_image.S" -o "$(winpath "$OBJD/zz_factory_image.o")" ) 2>&1 | head -20
  if [ -f "$OBJD/zz_factory_image.o" ]; then echo "2) 数据镜像汇编: OK"; else echo "2) 数据镜像汇编: 失败"; fi

  # ---- 链接 ----
  echo "3) 链接 ..."
  # shellcheck disable=SC2086
  $CC $LDFLAGS $(winpath "$OBJD")/*.o -o "$(winpath "$OUT")" 2>&1 | head -60
  rc=$?
  if [ -f "$OUT" ]; then
      echo "4) 产出 ELF: $OUT ($(wc -c < "$OUT") 字节)"
      echo ""
      echo "5) P4 ABI 门禁:"
      $PY "$(winpath "$ROOT/tools/abi_check.py")" "$(winpath "$OUT")" 2>&1 | head -20
  else
      echo "4) 链接失败（无 ELF 产出）"
  fi
} 2>&1 | tee "$REP"
exit 0
