#!/bin/bash
# Cross-compile for RK3036G (glibc 2.29 device)
# Uses -nostdlib to bypass Ubuntu 22.04's default glibc 2.35.
set -e

CC="${CC:-arm-linux-gnueabihf-gcc}"
SYSROOT="${SYSROOT:-}"

echo "=== rkgame-rebuild ==="
echo "CC=$CC"
echo "SYSROOT=$SYSROOT"

if [ -z "$SYSROOT" ] || [ ! -d "$SYSROOT" ]; then
    echo "FATAL: SYSROOT not set or does not exist"
    exit 1
fi

CFLAGS="-march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard -O2 -D_GNU_SOURCE -Wall"
SRC="src/main.c src/core.c src/evdev.c src/sram.c src/debug.c"
OUT="${1:-output/rkgame}"
mkdir -p "$(dirname "$OUT")"

CRT_DIR="$SYSROOT/usr/lib/arm-linux-gnueabihf"
RUNTIME_DIR="$SYSROOT/lib/arm-linux-gnueabihf"

echo "CRT_DIR=$CRT_DIR"
echo "RUNTIME_DIR=$RUNTIME_DIR"

# Verify critical files exist
for f in "$CRT_DIR/crt1.o" "$CRT_DIR/crti.o" "$CRT_DIR/crtn.o" "$CRT_DIR/libc.so" \
         "$RUNTIME_DIR/libc.so.6" "$RUNTIME_DIR/ld-linux-armhf.so.3"; do
    if [ ! -f "$f" ]; then
        echo "FATAL: missing $f"
        ls -la "$(dirname "$f")/" 2>/dev/null || echo "(dir not found)"
        exit 1
    fi
done

# Create libc_nonshared.a if missing (referenced by libc.so linker script)
if [ ! -f "$CRT_DIR/libc_nonshared.a" ]; then
    echo "NOTE: creating empty libc_nonshared.a"
    arm-linux-gnueabihf-ar rcs "$CRT_DIR/libc_nonshared.a" 2>/dev/null || \
    ar rcs "$CRT_DIR/libc_nonshared.a" 2>/dev/null || true
fi

# Find libgcc
LIBGCC="$($CC -print-libgcc-file-name 2>/dev/null || echo "")"
LIBGCC_OPTS=""
if [ -n "$LIBGCC" ] && [ -f "$LIBGCC" ]; then
    LIBGCC_OPTS="-L$(dirname "$LIBGCC") -lgcc"
    echo "libgcc: $LIBGCC"
fi

echo "--- Building ---"

# Build with -nostdlib + --sysroot
# --sysroot is critical: libc.so linker script uses absolute paths like
# /lib/arm-linux-gnueabihf/libc.so.6 which must be resolved relative to sysroot
#
# IMPORTANT: libdl.so and libm.so in Debian 9 are broken symlinks pointing to
# /lib/arm-linux-gnueabihf/libdl.so.2 (absolute host path) which does NOT exist
# on the CNB host. So -ldl/-lm silently fall back to static libdl.a/libm.a,
# which have undefined __dlopen/__dlclose/__dlsym that only resolve via
# libc.so.6 shared. Fix: pass shared runtime libs by absolute path.
$CC $CFLAGS \
    --sysroot="$SYSROOT" \
    -nostdlib \
    "$CRT_DIR/crt1.o" \
    "$CRT_DIR/crti.o" \
    $SRC \
    -o "$OUT" \
    -L"$CRT_DIR" \
    -L"$RUNTIME_DIR" \
    $LIBGCC_OPTS \
    -Wl,--no-as-needed \
    -Wl,--dynamic-linker,/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 \
    "$RUNTIME_DIR/libc-2.24.so" \
    "$RUNTIME_DIR/libdl-2.24.so" \
    "$RUNTIME_DIR/libpthread-2.24.so" \
    "$RUNTIME_DIR/libm-2.24.so" \
    "$CRT_DIR/libc_nonshared.a" \
    "$CRT_DIR/libpthread_nonshared.a" \
    "$CRT_DIR/crtn.o"

echo "Built: $OUT ($(stat -c%s "$OUT") bytes)"

# Verify GLIBC version
echo "--- GLIBC check ---"
GLIBC_HIGH=$(grep -ao "GLIBC_2\.[3-9][0-9]" "$OUT" 2>/dev/null || true)
if [ -n "$GLIBC_HIGH" ]; then
    echo "FAIL: found high GLIBC: $GLIBC_HIGH"
    exit 1
fi
echo "PASS: no GLIBC_2.3x+ symbols"

echo "=== DONE ==="
