#!/bin/bash
set -e
# Direct compile — bypass CMake (CMake flags not applied in CI)
# Uses CC from env (default: crosstool-NG glibc-2.29 toolchain or apt fallback)
# SYSROOT env var adds --sysroot for crosstool-NG sysroot

CC="${CC:-arm-linux-gnueabihf-gcc}"
SYSROOT="${SYSROOT:-}"

CFLAGS="-march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard -O2 -D_GNU_SOURCE -Wall"
LDFLAGS="-Wl,--no-as-needed -ldl -lpthread -lm -lc"

if [ -n "$SYSROOT" ] && [ -d "$SYSROOT" ]; then
  CFLAGS="$CFLAGS --sysroot=$SYSROOT"
  LDFLAGS="$LDFLAGS --sysroot=$SYSROOT"
fi

# 标准入口点，不需要 entry.c（-nostartfiles 会跳过 glibc 初始化导致启动失败）
SRC="src/main.c src/core.c src/evdev.c src/sram.c src/debug.c"
OUT="${1:-output/rkgame}"
mkdir -p "$(dirname "$OUT")"

echo "CC=$CC"
echo "SYSROOT=$SYSROOT"
echo "CFLAGS=$CFLAGS"
"$CC" $CFLAGS $SRC -o "$OUT" $LDFLAGS
echo "Built: $OUT ($(stat -c%s "$OUT") bytes)"
