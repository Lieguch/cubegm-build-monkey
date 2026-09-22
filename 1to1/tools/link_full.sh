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

# ★★ 诊断版扩展点（2026-09-21）：默认值与旧行为**逐字节等价**；只有 tools/build_diag.sh 会改它们。
#   DIAG_OBJD   —— 专有函数对象目录（默认 build/obj；诊断版用 build/diag_obj，多带 -finstrument-functions）
#   DIAG_XUNZIP —— XUnzip 对象（默认 src/upstream/xunzip/XUnzip.o；诊断版用插桩版）
#   DIAG_EXTRA  —— 额外对象（诊断仪自身：cgm_diag.o / cgm_wrap.o）
DIAG_OBJD="${DIAG_OBJD:-$ROOT/build/obj}"
DIAG_XUNZIP="${DIAG_XUNZIP:-$ROOT/src/upstream/xunzip/XUnzip.o}"

OBJS=""
for o in "$DIAG_OBJD"/*.o; do [ -f "$o" ] && OBJS="$OBJS $o"; done
[ -f "$CXXOBJ" ] && OBJS="$OBJS $CXXOBJ"
[ -f "$CRTOBJ" ] && OBJS="$OBJS $CRTOBJ"
for o in "$ROOT"/build/upstream/*.o; do [ -f "$o" ] && OBJS="$OBJS $o"; done
[ -f "$DIAG_XUNZIP" ] && OBJS="$OBJS $DIAG_XUNZIP"
[ -f "$ROOT/build/factory_local.o" ] && OBJS="$OBJS $ROOT/build/factory_local.o"
[ -n "${DIAG_EXTRA:-}" ] && OBJS="$OBJS $DIAG_EXTRA"
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
    ${DIAG_LDFLAGS:-} \
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

# ★★★ 2026-09-22（GAP 16.69）：**PT_LOAD 几何门禁** —— 钉在链接脚本里，本地/CI 都绕不过。
#   为什么必须钉在这：产出一份**畸形程序头表**的 ELF 时，下面这些都会通过——
#     · abi_check（只看 ELF 头 4 个字段）· dyn_audit（只看动态段）· verify_layout（只看
#       符号是否落在 PT_LOAD 内 —— 畸形段**也是** PT_LOAD，符号照样"在里面"）
#   于是在 PC/qemu 上一路全绿，在真机上 exec 失败、**零日志**（2026-09-21 实测）。
if [ -f "$OUT" ]; then
    echo "== PT_LOAD 几何门禁（防『畸形段』这一类：重叠 / 跨洞 / 最高地址 / 体积）=="
    if ! $PY "$(winpath "$ROOT/tools/elf_load_audit.py")" "$(winpath "$OUT")"; then
        echo "★★ PT_LOAD 几何门禁 FAIL —— 本产物**禁止**上机（详见上面的 [FAIL] 行）" >&2
        echo "   历史教训：畸形段在 qemu 上跑得通，在真机上 exec 直接失败、一条日志都不产生。" >&2
        exit 12
    fi
fi

# ★★★ 2026-09-22（GAP 16.71）：**RELRO 门禁** —— 同样钉进链接脚本。
#   为什么必须钉在这：`PT_GNU_RELRO` 一旦覆盖 `.data`，**链接与所有静态门禁照样全绿**，
#   但内核按页取整后会把我们的全局变量所在页设成**只读** ⇒ 进程**第一次写自己的全局变量**
#   就 SIGSEGV。真机实证（探针 v3 / t2=diag）：`si_addr=0x4e1010`（diag 的 `g_lvl`）、
#   PC 在 `cgm_diag_boot` —— 连 `-finstrument-functions` 的插桩都没跑起来。
#   这类缺陷只在"**写一个 .data 全局变量**"这一刻暴露，属于典型的"静态看不出来"。
if [ -f "$OUT" ]; then
    echo "== RELRO 门禁（防『.data 被圈进只读』：页面级判据）=="
    if ! $PY "$(winpath "$ROOT/tools/relro_audit.py")" "$(winpath "$OUT")"; then
        echo "★★ RELRO 门禁 FAIL —— 本产物**禁止**上机（.data 会在运行期变成只读）" >&2
        exit 13
    fi
fi

# ★★★ 2026-09-22（GAP 16.72）：**「立即数被误反编译成符号名」门禁**（源码级，秒级）。
#   真机实证：工厂 `InitSound` 是 `movw r1,#44100`，而 44100 == 0xAC44 == 工厂里
#   `UpdateROM` 的地址 ⇒ Ghidra 反编译成 `UpdateROM`，重建原样抄下 ⇒ 我们产物里该符号
#   被链接到 0x4e4060 ⇒ 传给 driver.so 的采样率变成 5,128,288 ⇒ `hwparams -22(EINVAL)`。
#   这一类**任何静态/二进制判据都看不出来**（符号尺寸、等价性、ABI 全绿），必须机器码对拍。
if [ -f "$ROOT/tools/lint_const_args.py" ]; then
    echo "== 立即数 vs 符号名 门禁（工厂机器码 ↔ 源码实参，防 Ghidra 常量混淆）=="
    if ! $PY "$(winpath "$ROOT/tools/lint_const_args.py")"; then
        echo "★★ 常量/符号混淆门禁 FAIL —— 先修源码再链接" >&2
        exit 14
    fi
fi

# ★★★ 2026-09-22（GAP 16.76）：**MMIO 访存宽度门禁**。
#   真机实证：`sfc_init` 读 SFC 寄存器时 SIGBUS —— 工厂是 `ldr`（32 位），
#   我们被**编译器**把 `g_sfc_reg[0xb] & 0xffff` 窄化成了 `ldrh`（16 位）。
#   （★ 更正：不是 GCC 而是 **clang 21.1.0** —— 工厂才是 GCC 6.2.0；见 ROUTE-DECISION.md 3.1）
#   **宽度是 MMIO 契约的一部分**，且窄化还会连带改变「写/读顺序」。
if [ -f "$OUT" ]; then
    echo "== MMIO 访存宽度门禁（设备寄存器必须与工厂同宽：整字）=="
    if ! $PY "$(winpath "$ROOT/tools/mmio_width_audit.py")" "$(winpath "$OUT")"; then
        echo "★★ MMIO 访存宽度门禁 FAIL —— 本产物**禁止**上机（窄访问可能直接总线报错）" >&2
        exit 15
    fi
fi

# ★★★ 2026-09-22（ROUTE-DECISION.md §五②）：**设备访存"类级"检测器**（取代白名单式抽检）。
#   旧门禁（exit 15）只硬判 2 个函数白名单，其余只提示 —— 这正是"逐个差异当根因、
#   每轮只采样一个成员"的成因。本门禁改为：
#     ① 函数集**机械推导**（源码里 `X = mmap(..., 0x1xxxxxxx|0x2xxxxxxx)` ⇒ 设备全局 ⇒
#        引用了它的文件 ⇒ 函数名；再并上反汇编里出现外设常量的函数），**无手写白名单**；
#     ② 判据单向且可判定：**对同一立即数偏移，我们不得比工厂"更窄"**（更宽不算缺陷）；
#     ③ 自带两态自证：喂"修复前产物"必须报错、自比必须零差异（本机 `--selftest` 跑）。
#   前置：`golden/factory.funcs.json.gz`（3.67 MB）+ `golden/factory.rkgame.bin` —— **已在仓库**，
#         CI 检出即可用（已核实远端 `1to1/golden/` 含这两份）。
if [ -f "$OUT" ] && [ -f "$ROOT/tools/mmio_access_audit.py" ]; then
    echo "== 设备访存 类级检测器（防『比工厂更窄』：偏移级，函数集机械推导）=="
    if ! $PY "$(winpath "$ROOT/tools/mmio_access_audit.py")" "$(winpath "$OUT")"; then
        echo "★★ 设备访存类级门禁 FAIL —— 本产物**禁止**上机（有偏移比工厂窄，可能总线报错）" >&2
        exit 16
    fi
fi
exit $rc
