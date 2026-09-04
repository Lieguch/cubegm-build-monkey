#!/bin/bash
set -e
# Cross-compile for RK3036G (glibc 2.29 device)
# Uses -nostdlib to bypass Ubuntu 22.04's default glibc 2.35 and
# link against Debian 9 glibc 2.24 from the sysroot.
#
# Root cause: --sysroot alone does NOT override the compiler's built-in
# CRT files and libc search paths. The compiler still links against
# its default glibc 2.35, producing GLIBC_2.34 symbols that crash on device.

CC="${CC:-arm-linux-gnueabihf-gcc}"
SYSROOT="${SYSROOT:-}"

echo "========================================"
echo "  rkgame-rebuild build.sh"
echo "========================================"
echo "CC=$CC"
echo "SYSROOT=$SYSROOT"

if [ -z "$SYSROOT" ] || [ ! -d "$SYSROOT" ]; then
    echo "ERROR: SYSROOT not set or does not exist"
    exit 1
fi

CFLAGS="-march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard -O2 -D_GNU_SOURCE -Wall"
SRC="src/main.c src/core.c src/evdev.c src/sram.c src/debug.c"
OUT="${1:-output/rkgame}"
mkdir -p "$(dirname "$OUT")"

# Sysroot paths (Debian layout)
CRT_DIR="$SYSROOT/usr/lib/arm-linux-gnueabihf"
RUNTIME_DIR="$SYSROOT/lib/arm-linux-gnueabihf"

echo ""
echo "--- Sysroot layout ---"
echo "CRT_DIR=$CRT_DIR"
echo "RUNTIME_DIR=$RUNTIME_DIR"

# --- Print sysroot contents for debugging ---
echo ""
echo "--- CRT_DIR contents ---"
ls -la "$CRT_DIR/" 2>/dev/null || echo "(directory not found)"
echo ""
echo "--- RUNTIME_DIR contents ---"
ls -la "$RUNTIME_DIR/" 2>/dev/null || echo "(directory not found)"

# --- Verify critical sysroot files ---
echo ""
echo "--- Verifying sysroot ---"
CRITICAL_MISSING=0

for f in "$CRT_DIR/crt1.o" "$CRT_DIR/crti.o" "$CRT_DIR/crtn.o" "$CRT_DIR/libc.so"; do
    if [ ! -f "$f" ]; then
        echo "MISSING (critical): $f"
        CRITICAL_MISSING=1
    else
        echo "OK: $f"
    fi
done

for f in "$RUNTIME_DIR/libc.so.6" "$RUNTIME_DIR/ld-linux-armhf.so.3"; do
    if [ ! -f "$f" ]; then
        echo "MISSING (critical): $f"
        CRITICAL_MISSING=1
    else
        echo "OK: $f"
    fi
done

if [ $CRITICAL_MISSING -eq 1 ]; then
    echo "ERROR: Critical sysroot files missing"
    exit 1
fi

# --- Check optional files (create if missing) ---
echo ""
echo "--- Optional files ---"

# libc_nonshared.a is referenced by libc.so linker script
if [ ! -f "$CRT_DIR/libc_nonshared.a" ]; then
    echo "WARNING: libc_nonshared.a missing, creating empty archive"
    # Find ar from the cross-compiler toolchain
    AR="$($CC -print-prog-name=arm-linux-gnueabihf-ar 2>/dev/null || echo "arm-linux-gnueabihf-ar")"
    if command -v "$AR" &>/dev/null; then
        "$AR" rcs "$CRT_DIR/libc_nonshared.a"
        echo "Created: $CRT_DIR/libc_nonshared.a"
    else
        # Fallback: create empty archive with host ar
        ar rcs "$CRT_DIR/libc_nonshared.a" 2>/dev/null || true
        echo "Created (host ar): $CRT_DIR/libc_nonshared.a"
    fi
else
    echo "OK: $CRT_DIR/libc_nonshared.a"
fi

# Check runtime libs (warn but don't fail)
for f in "$RUNTIME_DIR/libdl.so.2" "$RUNTIME_DIR/libpthread.so.0" "$RUNTIME_DIR/libm.so.6"; do
    if [ -f "$f" ]; then
        echo "OK: $f"
    else
        echo "WARNING: $f missing (may cause link issues)"
    fi
done

# --- Check libc.so linker script content ---
echo ""
echo "--- libc.so linker script ---"
cat "$CRT_DIR/libc.so" 2>/dev/null || echo "(cannot read)"

# --- Find libgcc ---
echo ""
echo "--- Finding libgcc ---"
LIBGCC="$($CC -print-libgcc-file-name 2>/dev/null || echo "")"
LIBGCC_OPTS=""
if [ -n "$LIBGCC" ] && [ -f "$LIBGCC" ]; then
    LIBGCC_DIR="$(dirname "$LIBGCC")"
    LIBGCC_OPTS="-L$LIBGCC_DIR -lgcc"
    echo "Found: $LIBGCC"
    echo "Opts: $LIBGCC_OPTS"
else
    echo "WARNING: libgcc not found"
    # Try to find it manually
    LIBGCC_DIR=$(dirname "$($CC -print-libgcc-file-name 2>/dev/null || echo "/usr/lib/gcc-cross/arm-linux-gnueabihf/11/libgcc.a")")
    if [ -f "$LIBGCC_DIR/libgcc.a" ]; then
        LIBGCC_OPTS="-L$LIBGCC_DIR -lgcc"
        echo "Found at fallback: $LIBGCC_DIR/libgcc.a"
    fi
fi

# --- Build with -nostdlib ---
echo ""
echo "--- Building ---"
echo "CFLAGS=$CFLAGS"
echo "SRC=$SRC"
echo "OUT=$OUT"
echo "LIBGCC_OPTS=$LIBGCC_OPTS"

BUILD_CMD="$CC $CFLAGS -nostdlib $CRT_DIR/crt1.o $CRT_DIR/crti.o $SRC -o $OUT -L$CRT_DIR -L$RUNTIME_DIR $LIBGCC_OPTS -Wl,--no-as-needed -Wl,--dynamic-linker,/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 -lc -ldl -lpthread -lm $CRT_DIR/crtn.o"
echo "CMD: $BUILD_CMD"
echo ""

eval "$BUILD_CMD"

echo ""
echo "Built: $OUT ($(stat -c%s "$OUT") bytes)"

# --- Verify GLIBC version ---
echo ""
echo "--- Verifying GLIBC version ---"
GLIBC_FOUND=""
if grep -ao "GLIBC_2\.[0-9]\+" "$OUT" 2>/dev/null | sort -u | while read v; do
    echo "  $v"
done; then
    true
fi

if grep -aq "GLIBC_2\.3" "$OUT" 2>/dev/null || grep -aq "GLIBC_2\.4" "$OUT" 2>/dev/null; then
    echo "ERROR: Binary contains GLIBC_2.3x+ symbols!"
    echo "Found:"
    grep -ao "GLIBC_2\.[0-9]\+" "$OUT" | sort -u
    exit 1
fi
echo "GLIBC check passed (no 2.3x+ symbols)"

# --- Show ELF NEEDED entries ---
echo ""
echo "--- ELF NEEDED entries ---"
strings "$OUT" 2>/dev/null | grep -E "libc\.so|libdl\.so|libpthread\.so|libm\.so|ld-linux" || true

echo ""
echo "========================================"
echo "  BUILD SUCCESS"
echo "========================================"
