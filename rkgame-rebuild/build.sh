#!/bin/bash
# Cross-compile for RK3036G (glibc 2.29 device)
# Uses Debian 9 (glibc 2.24) sysroot so DT_NEEDED resolves on device.
#
# ROOT CAUSE (2026-09-04): Debian 9 libc6-dev ships libdl.so/libm.so/
# libpthread.so as symlinks to absolute paths (/lib/arm-linux-gnueabihf/...)
# that don't exist on CNB host. Also libc.so linker script uses absolute
# paths. The setup-sysroot stage fixes these by replacing with relative
# symlinks and a relative-path libc.so linker script.
#
# Strategy: -nostdlib + manual CRT from sysroot + standard -lc -ldl -lpthread -lm.
# -nostdlib prevents GCC from using host libraries (Ubuntu 22.04 glibc 2.35).
# Manual CRT ensures we use sysroot's crt1.o/crti.o/crtn.o (glibc 2.24).
# Standard -lc flags now work because symlinks are fixed.
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
SRC="src/main.c src/core.c src/evdev.c src/sram.c src/debug.c src/disp.c src/heartbeat.c"
OUT="${1:-output/rkgame}"
mkdir -p "$(dirname "$OUT")"

RUNTIME_DIR="$SYSROOT/lib/arm-linux-gnueabihf"
DEV_DIR="$SYSROOT/usr/lib/arm-linux-gnueabihf"

# Check if libdrm is available in sysroot (for DRM/KMS display)
# Probe what's actually present so we can diagnose CI issues
DRM_LIB=""
DRM_CFLAGS=""
echo "--- DRM/KMS probe ---"
echo "  DEV_DIR=$DEV_DIR"
echo "  SYSROOT/usr/include=$SYSROOT/usr/include"
if ls "$DEV_DIR"/libdrm* 2>/dev/null; then echo "  libdrm files above"; fi
if ls "$SYSROOT/usr/include/xf86drm.h" "$SYSROOT/usr/include/xf86drmMode.h" 2>/dev/null; then echo "  DRM headers above"; fi
if [ -f "$DEV_DIR/libdrm.so" ] && [ -f "$SYSROOT/usr/include/xf86drm.h" ]; then
    DRM_LIB="-ldrm"
    CFLAGS="$CFLAGS -DHAVE_DRM=1 -I$SYSROOT/usr/include"
    echo "DRM/KMS support: enabled"
else
    echo "DRM/KMS support: disabled (falling back to log-only)"
fi

# Verify runtime libs exist
for f in "$RUNTIME_DIR/libc.so.6" "$RUNTIME_DIR/libdl.so.2" \
         "$RUNTIME_DIR/libpthread.so.0" "$RUNTIME_DIR/libm.so.6" \
         "$SYSROOT/lib/ld-linux-armhf.so.3" \
         "$DEV_DIR/libc.so" "$DEV_DIR/libc_nonshared.a"; do
    if [ ! -f "$f" ]; then
        echo "FATAL: missing $f"
        exit 1
    fi
done

# Verify symlinks are fixed (relative, not absolute)
for f in libdl.so libm.so libpthread.so; do
    if [ -L "$DEV_DIR/$f" ]; then
        target=$(readlink "$DEV_DIR/$f")
        if [[ "$target" == /* ]]; then
            echo "FATAL: $f is still an absolute symlink: -> $target"
            echo "       setup-sysroot stage must fix this"
            exit 1
        fi
        echo "  $f -> $target (relative, OK)"
    fi
done

# Find libgcc
LIBGCC="$($CC -print-libgcc-file-name 2>/dev/null || echo "")"
LIBGCC_OPTS=""
if [ -n "$LIBGCC" ] && [ -f "$LIBGCC" ]; then
    LIBGCC_OPTS="-L$(dirname "$LIBGCC") -lgcc"
    echo "libgcc: $LIBGCC"
fi

echo "--- Building ---"

# -nostdlib: skip GCC's default libs (avoid host glibc 2.35)
# Manual CRT: use sysroot's crt1.o/crti.o/crtn.o (glibc 2.24)
# Standard -lc -ldl -lpthread -lm: now works because symlinks are fixed
# --sysroot: ensures GCC and ld use sysroot headers and libraries
$CC $CFLAGS \
    --sysroot="$SYSROOT" \
    -nostdlib \
    "$DEV_DIR/crt1.o" \
    "$DEV_DIR/crti.o" \
    $SRC \
    -o "$OUT" \
    -L"$DEV_DIR" \
    -L"$RUNTIME_DIR" \
    $LIBGCC_OPTS \
    -Wl,--no-as-needed \
    -Wl,--dynamic-linker,/lib/ld-linux-armhf.so.3 \
    -lc -ldl -lpthread -lm \
    $DRM_LIB \
    "$DEV_DIR/crtn.o"

echo "Built: $OUT ($(stat -c%s "$OUT") bytes)"

# ---- Verify ELF consistency ----
echo "--- ELF verification ---"
# Check DT_* values are consistent with actual .rel.dyn/.rel.plt section sizes.
# Mismatched DT_RELSZ/DT_RELENT would cause the loader to abort before main().
# We use awk (not grep -oP) for reliable column parsing of readelf output.
if command -v readelf >/dev/null 2>&1; then
    SH_OUT=$(readelf -S "$OUT" 2>/dev/null)
    DYN_OUT=$(readelf -d "$OUT" 2>/dev/null)

    # readelf -S column layout (default field splitting):
    #  [ 9] .rel.dyn  REL  00000000  002f38  000180  08  A  27  0  4
    #   1    2       3    4        5       6       7  8  9  10 11 12
    # $7 = Size (hex), $8 = Entsize (hex)
    REL_DYN_SZ=$(echo "$SH_OUT" | awk '$3==".rel.dyn" {print $7}')
    REL_PLT_SZ=$(echo "$SH_OUT" | awk '$3==".rel.plt" {print $7}')

    # readelf -d: value is the LAST field on the line (after the tag name).
    # readelf shows hex as 0x... or decimal; awk can handle both.
    DT_RELSZ=$(echo "$DYN_OUT" | awk '/\(RELSZ\)/ {print $NF}')
    DT_PLTRELSZ=$(echo "$DYN_OUT" | awk '/\(PLTRELSZ\)/ {print $NF}')
    DT_RELENT=$(echo "$DYN_OUT" | awk '/\(RELENT\)/ {print $NF}')
    DT_REL=$(echo "$DYN_OUT" | awk '/\(REL\)/ {print $NF}')

    # Convert hex (0x...) to decimal for comparison
    hex2dec() {
        if [ -z "$1" ]; then echo ""; return; fi
        case "$1" in
            0x*|0X*) printf "%d" "$1" 2>/dev/null || echo "" ;;
            *)      echo "$1" ;;  # already decimal
        esac
    }
    REL_DYN_SZ_DEC=$(hex2dec "$REL_DYN_SZ")
    REL_PLT_SZ_DEC=$(hex2dec "$REL_PLT_SZ")
    RELSZ_DEC=$(hex2dec "$DT_RELSZ")
    PLTRELSZ_DEC=$(hex2dec "$DT_PLTRELSZ")
    RELENT_DEC=$(hex2dec "$DT_RELENT")

    echo "Section sizes: .rel.dyn=${REL_DYN_SZ} (${REL_DYN_SZ_DEC}) .rel.plt=${REL_PLT_SZ} (${REL_PLT_SZ_DEC})"
    echo "Dynamic: DT_REL=${DT_REL} DT_RELSZ=${DT_RELSZ} (${RELSZ_DEC}) DT_PLTRELSZ=${DT_PLTRELSZ} (${PLTRELSZ_DEC}) DT_RELENT=${DT_RELENT} (${RELENT_DEC})"

    ERRORS=0
    if [ -z "$DT_RELSZ" ]; then
        echo "FAIL: DT_RELSZ missing (loader cannot process relocations)"
        ERRORS=1
    elif [ -n "$REL_DYN_SZ_DEC" ] && [ "$RELSZ_DEC" != "$REL_DYN_SZ_DEC" ]; then
        echo "FAIL: DT_RELSZ=$RELSZ_DEC != .rel.dyn size $REL_DYN_SZ_DEC"
        ERRORS=1
    fi
    if [ -z "$DT_PLTRELSZ" ]; then
        echo "FAIL: DT_PLTRELSZ missing"
        ERRORS=1
    elif [ -n "$REL_PLT_SZ_DEC" ] && [ "$PLTRELSZ_DEC" != "$REL_PLT_SZ_DEC" ]; then
        echo "FAIL: DT_PLTRELSZ=$PLTRELSZ_DEC != .rel.plt size $REL_PLT_SZ_DEC"
        ERRORS=1
    fi
    if [ -n "$RELENT_DEC" ] && [ "$RELENT_DEC" != "8" ] && [ "$RELENT_DEC" != "12" ]; then
        echo "FAIL: DT_RELENT=$RELENT_DEC (expected 8 for R_REL32 or 12 for R_RELA)"
        ERRORS=1
    fi
    if [ "$ERRORS" -eq 0 ]; then
        echo "PASS: dynamic section consistent"
    else
        echo "WARN: dynamic section has errors (parsing may be unreliable)"
        echo "      Proceeding anyway - verify on device"
    fi
else
    echo "WARN: readelf not available; skipping ELF consistency check"
fi

# Verify GLIBC version
echo "--- GLIBC check ---"
GLIBC_HIGH=$(grep -ao "GLIBC_2\.[3-9][0-9]" "$OUT" 2>/dev/null || true)
if [ -n "$GLIBC_HIGH" ]; then
    echo "FAIL: found high GLIBC: $GLIBC_HIGH"
    exit 1
fi
echo "PASS: no GLIBC_2.3x+ symbols"

echo "=== DONE ==="
