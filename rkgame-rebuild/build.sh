#!/bin/bash
# Cross-compile for RK3036G (glibc 2.29 device)
# Uses Debian 9 (glibc 2.24) sysroot so DT_NEEDED resolves on device.
#
# KEY ISSUE (2026-09-04):
# Debian 9 glibc-dev ships libdl.so and libm.so as SYMLINKS to
# /lib/arm-linux-gnueabihf/libdl.so.2 (absolute host path).
# These absolute paths don't exist on CNB host (Ubuntu 22.04), so ld
# silently falls back to static libdl.a/libm.a, producing a broken
# .dynamic section (wrong DT_RELSZ/DT_RELENT/DT_RELACOUNT).
# Fix: create a temp dir with proper linker scripts for libdl.so and
# libm.so that point at the shared .so.2 in the sysroot, then use
# standard -lc -ldl -lpthread -lm flags.
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

RUNTIME_DIR="$SYSROOT/lib/arm-linux-gnueabihf"

# ---- Build a "linker-script dir" that mirrors sysroot but fixes broken symlinks ----
TMPDIR="$(mktemp -d /tmp/rkld.XXXXXX)"
trap 'rm -rf "$TMPDIR"' EXIT

# Verify runtime libs exist
for f in "$RUNTIME_DIR/libc.so.6" "$RUNTIME_DIR/libdl.so.2" \
         "$RUNTIME_DIR/libpthread.so.0" "$RUNTIME_DIR/libm.so.6" \
         "$RUNTIME_DIR/ld-linux-armhf.so.3"; do
    if [ ! -f "$f" ]; then
        echo "FATAL: missing $f"
        exit 1
    fi
done

# Generate linker scripts for shared-only libs (avoid broken host symlinks)
mk_script() {
    local name="$1"; shift
    local content="$*"
    cat > "$TMPDIR/${name}" <<EOF
/* GNU ld script
   Use shared + static fallback.  */
OUTPUT_FORMAT(elf32-littlearm)
GROUP ( AS_NEEDED ( $content ) )
EOF
}

# libc.so must pull in libc_nonshared.a (which contains __libc_csu_init/
# __libc_csu_fini that crt1.o references). Debian's real libc.so script
# does this; our minimal script must replicate it.
NONSHARED="$SYSROOT/usr/lib/arm-linux-gnueabihf/libc_nonshared.a"
if [ -f "$NONSHARED" ]; then
    mk_script libc.so "$RUNTIME_DIR/libc.so.6 $NONSHARED"
else
    echo "WARNING: libc_nonshared.a not found; __libc_csu_init will be unresolved"
    mk_script libc.so "$RUNTIME_DIR/libc.so.6"
fi

mk_script libdl.so    "$RUNTIME_DIR/libdl.so.2"
mk_script libm.so     "$RUNTIME_DIR/libm.so.6"
mk_script libpthread.so "$RUNTIME_DIR/libpthread.so.0"

echo "Linker scripts:"
ls -la "$TMPDIR/"

# Find libgcc
LIBGCC="$($CC -print-libgcc-file-name 2>/dev/null || echo "")"
LIBGCC_OPTS=""
if [ -n "$LIBGCC" ] && [ -f "$LIBGCC" ]; then
    LIBGCC_OPTS="-L$(dirname "$LIBGCC") -lgcc"
    echo "libgcc: $LIBGCC"
fi

echo "--- Building ---"

# Standard -lc -ldl -lpthread -lm using our temp linker scripts.
# -nostdlib + manual CRT: skip GCC's auto-injected Ubuntu 22.04 libs.
# --sysroot: ensures any absolute path in linker scripts resolves under sysroot.
$CC $CFLAGS \
    --sysroot="$SYSROOT" \
    -nostdlib \
    "$SYSROOT/usr/lib/arm-linux-gnueabihf/crt1.o" \
    "$SYSROOT/usr/lib/arm-linux-gnueabihf/crti.o" \
    $SRC \
    -o "$OUT" \
    -L"$TMPDIR" \
    -L"$SYSROOT/usr/lib/arm-linux-gnueabihf" \
    -L"$RUNTIME_DIR" \
    $LIBGCC_OPTS \
    -Wl,--no-as-needed \
    -Wl,--dynamic-linker,/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3 \
    -lc -ldl -lpthread -lm \
    "$SYSROOT/usr/lib/arm-linux-gnueabihf/crtn.o"

echo "Built: $OUT ($(stat -c%s "$OUT") bytes)"

# ---- Verify ELF consistency ----
echo "--- ELF verification ---"
# Check DT_* values are consistent with actual .rel.dyn/.rel.plt section sizes.
# Mismatched DT_RELSZ/DT_RELENT/DT_RELACOUNT would cause the loader to abort.
# This is the failure mode we hit on the last three device tests.
if command -v readelf >/dev/null 2>&1; then
    # readelf -d output the DT entries we care about
    DYN_OUT=$(readelf -d "$OUT" 2>/dev/null)
    # Section headers give real sizes
    SH_OUT=$(readelf -S "$OUT" 2>/dev/null)
    REL_DYN_SZ=$(echo "$SH_OUT" | grep -oP '\.rel\.dyn.*\K[\d]+' | head -1)
    REL_PLT_SZ=$(echo "$SH_OUT" | grep -oP '\.rel\.plt.*\K[\d]+' | head -1)
    DT_RELSZ=$(echo "$DYN_OUT" | grep -oP 'RELSZ.*0x\K[0-9a-f]+' | head -1)
    DT_PLTRELSZ=$(echo "$DYN_OUT" | grep -oP 'PLTRELSZ.*0x\K[0-9a-f]+' | head -1)
    DT_RELENT=$(echo "$DYN_OUT" | grep -oP 'RELENT.*0x\K[0-9a-f]+' | head -1)
    
    # Convert hex values to decimal for comparison using printf
    hex2dec() { printf "%d" "0x$1" 2>/dev/null || echo "?"; }
    RELSZ_DEC=$(hex2dec "${DT_RELSZ:-0}")
    PLTRELSZ_DEC=$(hex2dec "${DT_PLTRELSZ:-0}")
    RELENT_DEC=$(hex2dec "${DT_RELENT:-0}")
    
    echo "Section sizes: .rel.dyn=${REL_DYN_SZ} .rel.plt=${REL_PLT_SZ}"
    echo "Dynamic entries: DT_RELSZ=$RELSZ_DEC DT_PLTRELSZ=$PLTRELSZ_DEC DT_RELENT=$RELENT_DEC"
    
    if [ -n "$DT_RELSZ" ] && [ -n "$REL_DYN_SZ" ] && [ "$RELSZ_DEC" != "$REL_DYN_SZ" ]; then
        echo "FAIL: DT_RELSZ=$RELSZ_DEC != .rel.dyn size $REL_DYN_SZ"
        exit 1
    fi
    if [ -n "$DT_PLTRELSZ" ] && [ -n "$REL_PLT_SZ" ] && [ "$PLTRELSZ_DEC" != "$REL_PLT_SZ" ]; then
        echo "FAIL: DT_PLTRELSZ=$PLTRELSZ_DEC != .rel.plt size $REL_PLT_SZ"
        exit 1
    fi
    if [ -n "$DT_RELENT" ] && [ "$RELENT_DEC" != "8" ] && [ "$RELENT_DEC" != "12" ]; then
        echo "FAIL: DT_RELENT=$RELENT_DEC (expected 8 or 12)"
        exit 1
    fi
    echo "PASS: dynamic section consistent"
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
