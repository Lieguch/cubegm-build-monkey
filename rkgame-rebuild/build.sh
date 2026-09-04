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
    local name="$1"; local shared="$2"
    cat > "$TMPDIR/${name}" <<EOF
/* GNU ld script
   Use the shared library only.  */
OUTPUT_FORMAT(elf32-littlearm)
GROUP ( AS_NEEDED ( "$shared" ) )
EOF
}

mk_script libdl.so    "$RUNTIME_DIR/libdl.so.2"
mk_script libm.so     "$RUNTIME_DIR/libm.so.6"
mk_script libpthread.so "$RUNTIME_DIR/libpthread.so.0"
mk_script libc.so     "$RUNTIME_DIR/libc.so.6"

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
python3 - "$OUT" << 'PYEOF'
import sys, struct
data = open(sys.argv[1],'rb').read()
if data[:4] != b'\x7fELF':
    print('FAIL: not ELF'); sys.exit(1)

# Section headers
e_shoff = struct.unpack_from('<I', data, 32)[0]
e_shnum = struct.unpack_from('<H', data, 48)[0]
e_shentsize = struct.unpack_from('<H', data, 46)[0]
sections = []
for i in range(e_shnum):
    off = e_shoff + i*e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_addralign, sh_entsize = struct.unpack_from('<IIIIIIIIII', data, off)
    sections.append(dict(name=sh_name, type=sh_type, addr=sh_addr, off=sh_offset, size=sh_size, entsize=sh_entsize))

shstrtab_off = struct.unpack_from('<H', data, 50)[0]
sst = sections[shstrtab_off]
strtab = data[sst['off']:sst['off']+sst['size']]
def gs(off):
    e = strtab.find(b'\0', off)
    return strtab[off:e].decode() if e >= 0 else '?'

# Dynamic section entries
DT_NEEDED=1; DT_RELSZ=10; DT_RELENT=11; DT_JUMPREL=14; DT_INIT_ARRAY=18; DT_FINI_ARRAY=19
DT_INIT_ARRAYSZ=20; DT_FINI_ARRAYSZ=21; DT_SYMTAB=7; DT_STRTAB=5; DT_STRSZ=6
DT_RELACOUNT=0x6ffffff9; DT_PLTRELSZ=2; DT_GNU_HASH=0x6ffffef5
TAGS={DT_NEEDED:'NEEDED',DT_STRTAB:'STRTAB',DT_STRSZ:'STRSZ',DT_SYMTAB:'SYMTAB',
      DT_PLTRELSZ:'PLTRELSZ',DT_RELSZ:'RELSZ',DT_RELENT:'RELENT',DT_JUMPREL:'JUMPREL',
      DT_INIT_ARRAY:'INIT_ARRAY',DT_FINI_ARRAY:'FINI_ARRAY',
      DT_INIT_ARRAYSZ:'INIT_ARRAYSZ',DT_FINI_ARRAYSZ:'FINI_ARRAYSZ',
      DT_RELACOUNT:'RELACOUNT',DT_GNU_HASH:'GNU_HASH'}

dyn = next((s for s in sections if gs(s['name'])==' .dynamic'.strip()), None)
if not dyn:
    print('FAIL: no .dynamic'); sys.exit(1)

d = {}
for i in range(dyn['size']//8):
    tag, val = struct.unpack_from('<iI', data, dyn['off']+i*8)
    if tag in TAGS:
        d.setdefault(TAGS[tag], []).append(val)

# Reloc section sizes
rel_dyn = next((s for s in sections if gs(s['name'])=='.rel.dyn'), None)
rel_plt = next((s for s in sections if gs(s['name'])=='.rel.plt'), None)

print(f'.rel.dyn: size={rel_dyn["size"]}, entries={rel_dyn["size"]//rel_dyn["entsize"]}, entsize={rel_dyn["entsize"]}')
print(f'.rel.plt: size={rel_plt["size"]}, entries={rel_plt["size"]//rel_plt["entsize"]}, entsize={rel_plt["entsize"]}')

# Sanity checks
err = []
if DT_RELSZ in d:
    if d[DT_RELSZ][0] != rel_dyn['size']:
        err.append(f'DT_RELSZ={d[DT_RELSZ][0]} != .rel.dyn size {rel_dyn["size"]}')
if DT_RELENT in d:
    if d[DT_RELENT][0] != rel_dyn['entsize']:
        err.append(f'DT_RELENT={d[DT_RELENT][0]} != .rel.dyn entsize {rel_dyn["entsize"]}')
if DT_RELACOUNT in d and rel_dyn:
    expected = rel_dyn['size'] // rel_dyn['entsize']
    if d[DT_RELACOUNT][0] != expected:
        err.append(f'DT_RELACOUNT={d[DT_RELACOUNT][0]} != expected {expected}')
if DT_PLTRELSZ in d and rel_plt:
    if d[DT_PLTRELSZ][0] != rel_plt['size']:
        err.append(f'DT_PLTRELSZ={d[DT_PLTRELSZ][0]} != .rel.plt size {rel_plt["size"]}')

if err:
    print('FAIL: dynamic section inconsistencies:')
    for e in err:
        print(f'  {e}')
    sys.exit(1)
print('PASS: dynamic section consistent')
PYEOF

# Verify GLIBC version
echo "--- GLIBC check ---"
GLIBC_HIGH=$(grep -ao "GLIBC_2\.[3-9][0-9]" "$OUT" 2>/dev/null || true)
if [ -n "$GLIBC_HIGH" ]; then
    echo "FAIL: found high GLIBC: $GLIBC_HIGH"
    exit 1
fi
echo "PASS: no GLIBC_2.3x+ symbols"

echo "=== DONE ==="
