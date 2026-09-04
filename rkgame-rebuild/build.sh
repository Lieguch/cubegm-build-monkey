#!/bin/bash
set -e
# Cross-compile for RK3036G (glibc 2.29 device)
# Uses -nostdlib to bypass Ubuntu 22.04's default glibc 2.35 and
# link against Debian 9 glibc 2.24 from the sysroot instead.
#
# Root cause: --sysroot alone does NOT override the compiler's built-in
# CRT files and libc search paths. The compiler still links against its
# default glibc 2.35, producing GLIBC_2.34 symbols that crash on device.
# With -nostdlib, we explicitly control every linked file.

CC="${CC:-arm-linux-gnueabihf-gcc}"
SYSROOT="${SYSROOT:-}"

if [ -z "$SYSROOT" ] || [ ! -d "$SYSROOT" ]; then
    echo "ERROR: SYSROOT not set or does not exist"
    echo "Set SYSROOT to the extracted Debian sysroot directory"
    exit 1
fi

CFLAGS="-march=armv7-a -mtune=cortex-a7 -mfpu=neon-vfpv4 -mfloat-abi=hard -O2 -D_GNU_SOURCE -Wall"
SRC="src/main.c src/core.c src/evdev.c src/sram.c src/debug.c"
OUT="${1:-output/rkgame}"
mkdir -p "$(dirname "$OUT")"

# Sysroot paths (Debian layout)
CRT_DIR="$SYSROOT/usr/lib/arm-linux-gnueabihf"
RUNTIME_DIR="$SYSROOT/lib/arm-linux-gnueabihf"

echo "CC=$CC"
echo "SYSROOT=$SYSROOT"
echo "CRT_DIR=$CRT_DIR"
echo "RUNTIME_DIR=$RUNTIME_DIR"

# --- Verify sysroot contents ---
echo "--- Checking sysroot ---"
MISSING=0
for f in "$CRT_DIR/crt1.o" "$CRT_DIR/crti.o" "$CRT_DIR/crtn.o" \
         "$CRT_DIR/libc.so" "$CRT_DIR/libc_nonshared.a"; do
    if [ ! -f "$f" ]; then
        echo "MISSING: $f"
        MISSING=1
    fi
done
for f in "$RUNTIME_DIR/libc.so.6" "$RUNTIME_DIR/ld-linux-armhf.so.3" \
         "$RUNTIME_DIR/libdl.so.2" "$RUNTIME_DIR/libpthread.so.0" \
         "$RUNTIME_DIR/libm.so.6"; do
    if [ ! -f "$f" ]; then
        echo "MISSING: $f"
        MISSING=1
    fi
done
if [ $MISSING -eq 1 ]; then
    echo "ERROR: sysroot incomplete"
    echo "Contents:"
    ls -la "$CRT_DIR/" 2>/dev/null || echo "(no CRT_DIR)"
    ls -la "$RUNTIME_DIR/" 2>/dev/null || echo "(no RUNTIME_DIR)"
    exit 1
fi
echo "Sysroot OK"

# --- Find libgcc (provided by GCC, not in sysroot) ---
LIBGCC="$($CC -print-libgcc-file-name 2>/dev/null || echo "")"
LIBGCC_DIR=""
if [ -n "$LIBGCC" ] && [ -f "$LIBGCC" ]; then
    LIBGCC_DIR="$(dirname "$LIBGCC")"
    echo "libgcc: $LIBGCC"
else
    echo "WARNING: libgcc not found via -print-libgcc-file-name"
fi

# --- Build with -nostdlib ---
echo "Building..."
"$CC" $CFLAGS \
    -nostdlib \
    "$CRT_DIR/crt1.o" "$CRT_DIR/crti.o" \
    $SRC -o "$OUT" \
    -L"$CRT_DIR" \
    -L"$RUNTIME_DIR" \
    ${LIBGCC_DIR:+-L"$LIBGCC_DIR" -lgcc} \
    -Wl,--no-as-needed \
    -Wl,--dynamic-linker,/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 \
    -lc -ldl -lpthread -lm \
    "$CRT_DIR/crtn.o"

echo "Built: $OUT ($(stat -c%s "$OUT") bytes)"

# --- Verify no high GLIBC symbols ---
echo "--- Verifying GLIBC version ---"
if grep -aq "GLIBC_2\.3" "$OUT" || grep -aq "GLIBC_2\.4" "$OUT"; then
    echo "ERROR: Binary contains GLIBC_2.3x+ symbols!"
    echo "Found:"
    grep -ao "GLIBC_2\.[0-9]\+" "$OUT" | sort -u
    exit 1
fi
echo "GLIBC check passed"
echo "Done!"
