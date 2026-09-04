#!/bin/bash
# Cross-compile for RK3036G (glibc 2.29 device)
# Uses Debian 9 (glibc 2.24) sysroot so DT_NEEDED resolves on device.
#
# ROOT CAUSE (2026-09-04, fixed):
# Debian 9 glibc-dev ships libdl.so/libm.so/libpthread.so as SYMLINKS to
# absolute paths like /lib/arm-linux-gnueabihf/libdl.so.2. On CNB host
# (Ubuntu 22.04) these absolute paths don't exist. We create temp linker
# scripts pointing at the shared .so.2 in the sysroot.
#
# CRITICAL BUG (found 2026-09-04): The linker scripts previously used paths
# WITH the $SYSROOT prefix (e.g. /arm-root/lib/...). Since --sysroot=/arm-root
# prepends /arm-root to root-relative paths, the linker saw /arm-root/arm-root/...
# which doesn't exist. The linker silently fell back to wrong libraries,
# producing a SCRAMBLED .dynamic section:
#   - DT_RELSZ missing entirely
#   - DT_REL pointing to .fini address instead of .rel.dyn
#   - DT_INIT_ARRAY pointing to .rel.dyn address
#   - DT_FINI_ARRAY containing .rel.dyn size (440)
# Any loader refuses to load such a binary → main() never runs → no log.
#
# FIX: linker script paths must be ROOT-RELATIVE (e.g. /lib/... NOT /arm-root/lib/...).
# --sysroot will prepend /arm-root correctly.
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
DEV_DIR="$SYSROOT/usr/lib/arm-linux-gnueabihf"

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

# Generate linker scripts for shared-only libs (avoid broken host symlinks).
# CRITICAL: paths inside scripts must be ROOT-RELATIVE (e.g. /lib/...) NOT
# absolute with $SYSROOT prefix (e.g. /arm-root/lib/...). --sysroot prepends
# $SYSROOT to root-relative paths; if the path already includes $SYSROOT,
# the linker sees /arm-root/arm-root/... and silently falls back to wrong
# libs, producing a scrambled .dynamic section (DT_REL/DT_RELSZ/DT_INIT_ARRAY
# all pointing to wrong addresses).
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
NONSHARED_REAL="$DEV_DIR/libc_nonshared.a"
if [ -f "$NONSHARED_REAL" ]; then
    mk_script libc.so "/lib/arm-linux-gnueabihf/libc.so.6 /usr/lib/arm-linux-gnueabihf/libc_nonshared.a"
else
    echo "WARNING: libc_nonshared.a not found; __libc_csu_init will be unresolved"
    mk_script libc.so "/lib/arm-linux-gnueabihf/libc.so.6"
fi

mk_script libdl.so    "/lib/arm-linux-gnueabihf/libdl.so.2"
mk_script libm.so     "/lib/arm-linux-gnueabihf/libm.so.6"
mk_script libpthread.so "/lib/arm-linux-gnueabihf/libpthread.so.0"

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
        echo "FAIL: dynamic section has errors"
        exit 1
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
