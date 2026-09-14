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
# ★ 与工厂对齐（工厂 .comment 印着 `... -fno-stack-protector`；二进制里 stack_chk/FORTIFY 出现 0 次）。
#   本地 zig 驱动会顺带链进 compiler_rt.ssp（symtab 里可见 compiler_rt.ssp.__stack_chk_guard）——
#   那是**本地链接器行为**，CI 的 GCC 不会带；带上此标志可让两侧尽量一致。
FIDELITY="${FIDELITY:--fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0}"
OUT="${1:-$ROOT/build/rkgame.rebuilt.elf}"
PY="${PY:-python}"

# ★★ glibc 版本下限 —— 设备兼容性的硬约束
#   实测（golden/factory.rkgame.bin 的 .gnu.version_r / .dynstr）：工厂 rkgame 需要的最高
#   GLIBC 标签 = **GLIBC_2.7**；设备 SD 上原厂 ARM 运行库（SDL/libz/libpng/freetype/libcrypto）
#   最高只用到 GLIBC_2.16，且 rkgame 的 .comment 是 **GCC 6.2.0**（SD 上 libstdc++ = 6.0.22，
#   GCC 5/6 时代）⇒ 设备 glibc 处于 2.16~2.24 区间。
#   而 CI 的 Ubuntu 22.04 GCC 链接出的产物要求 **GLIBC_2.29/2.33/2.34** ⇒ 到设备上会
#   `version GLIBC_2.34 not found` 直接起不来（这是 P6 真机验收的硬阻断）。
#   zig cc 支持在目标三元组里指定 glibc 版本：`-target arm-linux-gnueabihf.2.7` ⇒ 产物只要求
#   GLIBC_2.4/2.7（与工厂同级，向下兼容到任意 ≥2.7 的设备 glibc）。
#   ⇒ 因此链接**必须**用 zig；用 GCC 时必须显式给 SYSROOT（否则 abi_check 的 GLIBC 门禁会 FAIL）。
GLIBC_VER="${GLIBC_VER:-2.7}"

winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }

case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf.${GLIBC_VER} -mfloat-abi=hard -mfpu=neon" ;;
  *)     if [ -n "${SYSROOT:-}" ]; then
             ARCH="--sysroot=$SYSROOT -march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic"
         else
             ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic"
             echo "!! 警告：非 zig 链接且未给 SYSROOT ⇒ 产物的 GLIBC 下限 = 宿主 glibc（会远高于设备）" >&2
         fi ;;
esac

# 静态试链用的 libstdc++ 替身（operator new/delete）
CXXOBJ="$ROOT/build/cxx_ops.o"
if [ ! -f "$CXXOBJ" ] || [ "$ROOT/src/compat/cxx_ops.c" -nt "$CXXOBJ" ]; then
    $CC -c -O1 -w $ARCH $FIDELITY "$(winpath "$ROOT/src/compat/cxx_ops.c")" -o "$(winpath "$CXXOBJ")" 2>/dev/null \
      && echo "  cxx_ops.o 已编译"
fi

# 工厂数据镜像对象：每次链接前重建（避免用旧的段名/旧别名）
ALLS="$ROOT/build/factory_all.S"
cat "$ROOT/src/data/factory_image.S" "$ROOT/src/data/factory_local.S" > "$ALLS"
$CC $ARCH -c -I"$(winpath "$ROOT/src/data")" "$(winpath "$ALLS")" -o "$(winpath "$ROOT/build/factory_local.o")" \
  && echo "  factory_local.o 已重建" || { echo "  factory_local.o 汇编失败"; exit 1; }

# ★★ 最小 CRT 初始化桩（_init/_fini）：zig **不提供 crti.o**（GCC 提供）。
#   缺了它 ⇒ `_init` 未定义 ⇒ 若链接脚本里还留 `PROVIDE_HIDDEN(_init = 0)` 就会生成
#   `DT_INIT = 0` ⇒ glibc 的 call_init 跳地址 0 ⇒ **任何输出之前 SIGSEGV**（CI 实测回归）。
#   现在由 src/compat/crt_init.S 提供真实 .init/.fini 节；漏链它会**链接报错**（响亮失败）。
CRTOBJ="$ROOT/build/crt_init.o"
if [ ! -f "$CRTOBJ" ] || [ "$ROOT/src/compat/crt_init.S" -nt "$CRTOBJ" ]; then
    $CC $ARCH -c "$(winpath "$ROOT/src/compat/crt_init.S")" -o "$(winpath "$CRTOBJ")" || { echo "!! FATAL crt_init.S 汇编失败" >&2; exit 4; }
    echo "  crt_init.o 已编译"
fi

OBJS=""
for o in "$ROOT"/build/obj/*.o; do [ -f "$o" ] && OBJS="$OBJS $o"; done
[ -f "$CXXOBJ" ] && OBJS="$OBJS $CXXOBJ"
[ -f "$CRTOBJ" ] && OBJS="$OBJS $CRTOBJ"
for o in "$ROOT"/build/upstream/*.o; do [ -f "$o" ] && OBJS="$OBJS $o"; done
[ -f "$ROOT/src/upstream/xunzip/XUnzip.o" ] && OBJS="$OBJS $ROOT/src/upstream/xunzip/XUnzip.o"
[ -f "$ROOT/build/factory_local.o" ] && OBJS="$OBJS $ROOT/build/factory_local.o"
n=$(printf '%s' "$OBJS" | wc -w)
echo "== 对象数: $n =="

# 全部对象转 Windows 路径（zig.exe 原生程序）
WOBJS=""
for o in $OBJS; do WOBJS="$WOBJS $(winpath "$o")"; done

echo "== 链接 =="
# ★★ libz.so.1 —— 必须真实产生（不能再把 compress/uncompress 置 0）
#   实测：这两个符号被 retro_save_state / retro_load_state 调用；绑成 ABS 0 ⇒ 调用即跳地址 0
#   ⇒ 存档/读档必崩。工厂的取值方式 = 从 libz.so.1 **动态导入**（NEEDED libz.so.1）。
#   ★ 做法：生成一个**链接期桩 DSO**（src/compat/zstub.c，SONAME=libz.so.1）。
#     只让引用变成动态导入 ⇒ NEEDED 里出现 libz.so.1（与工厂一致），
#     但**不绑死符号版本** —— 实测链接真实 libz 会写下 `ZLIB_1.2.x` 版本需求，
#     而设备 SD 上原厂 ARM libz 的版本集是非标准的（ZLIB_1.2.0…1.2.12）⇒ 可能
#     `version ZLIB_x not found`。桩没有任何版本标签，因此对任何 zlib 都安全。
#     桩不打包、不在设备上执行：运行期由设备自己的 libz.so.1 解析。
#   （LIBZ=<path> 可指定一个真实 libz 做对照实验，但**不要**用于交付产物。）
STUBDIR="$ROOT/build/stub"
mkdir -p "$STUBDIR"
if [ -n "${LIBZ:-}" ]; then
    echo "  [对照模式] 使用真实 libz：$LIBZ（注意会绑死符号版本，勿用于交付）"
    LIBZ_W="$(winpath "$LIBZ")"
else
    $CC $ARCH -shared -fPIC -O1 -w -Wl,-soname,libz.so.1 \
        "$(winpath "$ROOT/src/compat/zstub.c")" -o "$(winpath "$STUBDIR/libz.so.1")" \
        || { echo "!! FATAL 生成 libz 桩失败" >&2; exit 3; }
    LIBZ_W="$(winpath "$STUBDIR/libz.so.1")"
    echo "  libz 桩 = build/stub/libz.so.1（SONAME=libz.so.1，不绑符号版本）"
fi

# ★ -z max-page-size=0x1000 与工厂一致（工厂各 LOAD 的 al=0x1000，首个 LOAD 从 0x8000 起）。
#   默认 0x10000 会让链接器把首段起点向下取整到 0x0 ⇒ 地址 0..0x7fff 变成**已映射**；
#   工厂那里是空洞 ⇒ NULL 写会静默成功而不是 SIGSEGV（真实差分抓到的假分歧）。
#   注意：注释必须写在命令**之前** —— `\` 续行后的 `#` 不是注释，会作为参数传给编译器。
# shellcheck disable=SC2086
$CC $ARCH $FIDELITY -no-pie \
    -Wl,-T,"$(winpath "$ROOT/linker/factory.ld")" \
    -Wl,-z,max-page-size=0x1000 \
    -Wl,-z,undefs -Wl,--build-id=none \
    $WOBJS "$LIBZ_W" -o "$(winpath "$OUT")" 2>"$ROOT/report/link_full_err.txt"
rc=$?
echo "链接 rc=$rc"
if [ -f "$OUT" ]; then
    ls -la "$OUT"
    echo "== 动态段 / 初始化链自洽 =="
    # ★ 本地 zig 不链 crti.o ⇒ DT_INIT=0 属工具链差异（dyn_audit 会判 WARN 而非 FAIL）；
    #   CI 用 GCC 必然链 crti.o ⇒ 若 DT_INIT=0 会直接判 FAIL。判定以 CI 为准。
    $PY "$(winpath "$ROOT/tools/dyn_audit.py")" "$(winpath "$OUT")" \
        > "$ROOT/report/dyn_audit.txt" 2>&1 || true
    sed -n '1,20p' "$ROOT/report/dyn_audit.txt"
    echo "== 段地址核对 =="
    $PY "$(winpath "$ROOT/tools/verify_layout.py")" "$(winpath "$OUT")" \
        "$(winpath "$ROOT/ledger/factory_globals.tsv")" 2>/dev/null | head -24
else
    echo "（无产物）错误摘要："
    grep -aE "error|undefined|overlap" "$ROOT/report/link_full_err.txt" | head -12
fi
exit $rc
