#!/bin/sh
# ============================================================
# link_full.sh — P3 三期：完整链接（全部对象 + 工厂数据镜像 + 工厂布局）
#
# 环境变量：
#   CC / SYSROOT / GLIBC_VER / FIDELITY / DIAG_*  —— 见下
#   ★ EXTRA_LDFLAGS —— 追加到链接行尾的额外 ld 参数（默认空 ⇒ 与旧版逐字等价）。
#     用途：单变量 A/B 给非 zig 工具链补齐**工厂同样拥有的**库。
#     实测依据：工厂 `DT_NEEDED` 含 `libm.so.6`，其动态未定义符号含
#     `pow/sqrt/sqrtf/floorf/ceilf/fmod`；而 `zig cc`（clang 驱动）会**自动加 `-lm`**，
#     GCC 路径不会 ⇒ 不补就 `undefined reference to pow/...`（CI 实测）。
#
# 输入（均已存在）：
#   build/obj/*.o         213 个专有函数对象
#   src/upstream/xunzip/XUnzip.o      XUnzip（C++ 移植）
#   build/upstream/*.o     stb / mxml / mp3 / libiconv
#   build/factory_local.o  factory_image.S + factory_local.S 汇编产物（工厂字节镜像 + 别名）
# 输出：build/rkgame.rebuilt.elf
#
# 说明：
#   · CRT：**本脚本不加任何 -nostdlib/-nostartfiles**（见下方「CRT 与链接器方言」注释）。
#     数据段布局由脚本钉死；libc 符号走正常动态链接（工厂同样 DT_NEEDED libc.so.6）。
#     ⚠ `-z undefs` 是 **lld 专属**写法，BFD ld 会 `warning: -z undefs ignored`
#       并真的忽略它 ⇒ BFD 侧需要 `--unresolved-symbols=ignore-all`（由调用方给）。
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
# ★★ 2026-09-28：门禁脚本依赖 pyelftools。实测踩到：PY 回退到系统 python（无 elftools）
#   ⇒ 门禁抛 `ModuleNotFoundError` 并以非零退出 ⇒ 被当成"门禁 FAIL"（**假失败**，
#   与"参数传错"同族）。这里先自检，并尝试已知 venv 路径兜底；都不行就**指名报错**。
if ! "$PY" -c 'import elftools' 2>/dev/null; then
    for _c in "$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
              "$HOME/.workbuddy/binaries/python/envs/default/bin/python" python3; do
        if command -v "$_c" >/dev/null 2>&1 && "$_c" -c 'import elftools' 2>/dev/null; then
            PY="$_c"; echo "  [env] PY 兜底为 $_c（含 pyelftools）" >&2; break
        fi
    done
fi
"$PY" -c 'import elftools' >/dev/null 2>&1 || {
    # ★★★ 2026-09-29（§0.35）：**脚本自足**（纪律 71）。原逻辑只找"本机 venv + python3"，
    #   CI 上都不含 pyelftools ⇒ `exit 5` ⇒ `1to1-verify` #233 / `1to1-qemu-behav` #201 连锁红。
    #   现在交给 `tools/ensure_pydeps.sh`：已就绪 ⇒ 零开销；缺 ⇒ 就地 `pip install`（幂等）；
    #   装不上 ⇒ 它自己 fail-closed（**不静默跳过门禁**）。引导逻辑**只此一处**（纪律 69）。
    #   回退：删掉下面这一行（回到"缺失即 exit 5"）。
    PY="$PY" sh "$ROOT/tools/ensure_pydeps.sh" || exit $?
}
"$PY" -c 'import elftools' >/dev/null 2>&1 || {
    echo "★★ 门禁依赖缺失：PY=$PY 无法 import elftools（已试 ensure_pydeps.sh 就地安装）" >&2
    exit 5
}

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

# ★★ LINK_DRIVER —— 链接驱动（2026-09-28 新增）
#   lld  （默认）：`zig ld.lld` + **工厂同期 sysroot**（Bootlin 2017.05）：
#                  DT_NEEDED 7 项同序、mem*/str* 动态导入、__aeabi_* 6 个静态助手尺寸同工厂、
#                  版本需求逐项同工厂；DIVERGE 44→42。
#   zigcc        ：旧行为（`zig cc` 当驱动 + compiler_rt），保留用于 A/B 与回退。
LINK_DRIVER="${LINK_DRIVER:-lld}"

# ★★★★★ 2026-09-30：**把「链接驱动」暴露给调用方**（纪律 69：口径只允许有一处）。
#   为什么必须有（CI `toolchain-ab` #12 实测）：`toolchain_ab.sh` 原本按**编译器**（`$cc`）
#   决定附加链接参数 —— GCC 腿给 `-nostartfiles -Wl,--unresolved-symbols=ignore-all`
#   （**BFD ld 方言**）。但**链接器**是由**本脚本**按 `LINK_DRIVER` 独立决定的（默认 `lld`）
#   ⇒ GCC 腿把 BFD 参数喂给直驱的 `ld.lld`：
#        `ld.lld: error: unknown argument '-nostartfiles'`
#        `ld.lld: error: unknown argument '-Wl,--unresolved-symbols=ignore-all'`
#        `ld.lld: error: unable to find library -lm / -lpthread / -ldl`
#     ⇒ 两条腿 BUILD_FAILED。**根因 = 参数跟着"编译器"走，而实际决定链接的是"链接器"。**
#   ⇒ 现在调用方可以 `sh tools/link_full.sh --print-ldenv` **读取**真正的驱动，再据此给参数。
if [ "${1:-}" = "--print-ldenv" ]; then
    echo "LINK_DRIVER=$LINK_DRIVER"
    exit 0
fi

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
# ★★★ 2026-09-29（根因修复，勿删）：把**被 `.incbin` 引用的镜像内容**纳入汇编输入哈希。
#   病灶：zig 的缓存键 = 源文件内容 + 命令行，**不追踪 `.incbin` 打开的文件**。
#   ⇒ 改了 `src/data/factory_*.bin` 之后，zig 直接复用旧的 `factory_local.o`，
#     产物**逐字节不变**（实测：`.fimg_text` 2,957,704 B 全零化后产物 sha 仍等于对照，
#     删除实验得到的是**假绿**）。同类陷阱在 GAP 16.56 已付过一次代价。
#   修法：在 `.S` 末尾追加一行含镜像 sha256 的注释 —— 内容一变，缓存键必变。
#   回退：删掉下面这 3 行（回到"缓存可能假绿"的旧行为）。
{
  printf '/* fimg-content-hash: %s */\n' \
    "$(cat "$ROOT"/src/data/factory_*.bin 2>/dev/null | sha256sum | cut -c1-32)"
} >> "$ALLS"
$CC $ARCH -c -I"$(winpath "$ROOT/src/data")" "$(winpath "$ALLS")" -o "$(winpath "$ROOT/build/factory_local.o")" \
  && echo "  factory_local.o 已重建（含镜像内容哈希）" || { echo "  factory_local.o 汇编失败"; exit 1; }

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
# ★★ 2026-09-28：`LINK_DRIVER=lld` 时**不链 cxx_ops.o**。
#   该文件是"没有 libstdc++ 时的静态试链替身"（malloc/free 实现 operator new/delete）。
#   接管链接后我们**真的**链了 `libstdc++.so.6` ⇒ 保留它只会把 `_Znwj/_Znaj/_ZdlPv/_ZdaPv`
#   变成**我方私有静态定义**，而工厂这 4 个是 **libstdc++ 的动态导入**（`.dynsym` 实测）
#   ⇒ 删掉才对齐。实测：删后行为尺**逐项不变**（782/735/42/5），而动态导入 107→111。
if [ "${LINK_DRIVER:-lld}" != "lld" ]; then
    [ -f "$CXXOBJ" ] && OBJS="$OBJS $CXXOBJ"
else
    echo "  [lld] 跳过 cxx_ops.o（operator new/delete 改由 libstdc++.so.6 动态提供）"
fi
[ -f "$CRTOBJ" ] && OBJS="$OBJS $CRTOBJ"
# ★ 2026-09-28：上游对象目录可用 UPOBJD 覆盖（编译器对齐实验用 build/gcc_upstream）
UPOBJD="${UPOBJD:-$ROOT/build/upstream}"
for o in "$UPOBJD"/*.o; do [ -f "$o" ] && OBJS="$OBJS $o"; done
# ★★ 2026-09-28：**fail-closed** —— XUnzip 对象缺失时立刻报错并指名。
#   实测踩到：臂 A 的 XUnzip 编译因 zig 缓存竞态（`CacheCheckFailed`）失败，
#   旧实现 `[ -f ... ] &&` **静默跳过** ⇒ 链接报一堆 `undefined symbol: TUnzip::*`，
#   把"某个 .o 根本没编出来"伪装成"链接问题"（与 `-z undefs` 掩盖 `_start` 同族）。
if [ ! -f "$DIAG_XUNZIP" ]; then
    echo "★★ XUnzip 对象不存在：$DIAG_XUNZIP" >&2
    echo "   （期望存在却缺失 ⇒ 就地失败，不靠下游 undefined symbol 兜底）" >&2
    exit 12
fi
OBJS="$OBJS $DIAG_XUNZIP"
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
# ★★★ CRT 与「允许未解析符号」的正确开关 —— **规范文档：docs/LINKER-FLAGS.md**
#   （GCC 手册 & ld 手册逐字条款 + 本工程该用哪个 + 怎么问工具自己核实版本支持）。
#   结论：该由**调用方按链接器方言**决定，本脚本**不加**任何 nostdlib/nostartfiles：
#   ① 命令行原本就没有 `-nostdlib`（上面第 21 行的注释是**旧的、与代码不符**）；
#   ② 我一度真的加上 `-nostdlib`，结果 **zig/lld 侧全崩**：
#        `ld.lld: error: undefined symbol: printf/malloc/sprintf/...`
#      —— 因为 `-nostdlib` = `-nodefaultlibs` + `-nostartfiles`，把 clang 默认的 `-lc` 一起砍了。
#   ③ GCC 侧的真问题**不是**缺 `-nostdlib`，而是 BFD ld 会按 sysroot 自动链
#      `crti.o`/`crtbegin.o`，与本工程的 `crt_init.o`（提供 `_init`/`_fini`）与
#      `factory_local.o`（提供 `__dso_handle`）**重复定义** ⇒ 正确的开关是 **`-nostartfiles`**
#      （只砍 crt1/crti/crtbegin/crtend/crtn，**保留 `-lc`**），且**只对需要的链接器加**
#      ⇒ 由 `EXTRA_LDFLAGS` 从外部传入（A/B 的 GCC 腿就是这样传的），主链行为逐字不变。
# ★★ 2026-09-27（实证事故）：**链接前必须先删掉目标产物**。
#   实测踩到：把 XUnzip 源码换成原版后链接因 `duplicate symbol: lasterrorU` 失败，
#   而脚本把**上一次成功链接的旧产物原样留在原地** —— 下游（投放打包 / 门禁 / 判定）
#   看到的是一个"看起来全新、其实是上一轮"的 ELF。这与 `check_obj_fresh.py` 要防的
#   "陈旧对象静默污染"是同一类事故，只是发生在**最终产物**这一层。
#   ⇒ fail-closed：先删、后链；链接失败则产物**不存在**，不可能被误用。
rm -f "$OUT"
if [ "${LINK_DRIVER:-lld}" = "lld" ]; then
    # ==========================================================================
    # ★★★ 2026-09-28：**接管链接** —— 直接驱动 `zig ld.lld`，按工厂口径给库。
    #
    # 为什么不继续用 `zig cc` 当驱动（取证见 LINKAGE-ALIGNMENT.md）：
    #   `zig cc` 的链接行把 `libcompiler_rt.a` 放在 libc **之后**，而该归档里的"大对象"
    #   会被别的符号（__udivsi3 等）拉进来，其中 **mem*/str* 是普通目标文件定义** ⇒ 按 ELF
    #   规则**盖过 DSO 定义** ⇒ 工厂从 libc 动态导入的 4 个符号（memcpy/memset/memmove/strlen）
    #   在我方变成 `.text` 里的 STB_LOCAL 静态定义；同时 DT_NEEDED 少两项、`__aeabi_*`
    #   助手有 69 个（工厂只有 6 个、且尺寸逐项相同）。
    #
    # 本分支改用**工厂同期工具链**（Bootlin 2017.05 = GCC 6.3 / glibc 2.24 / binutils 2.27）
    # 的 sysroot 当链接输入，并且**不链 compiler_rt**。实测收敛：
    #   · DT_NEEDED 5 → **7**，与工厂**逐项同序**（libz libdl libm libstdc++ libpthread libgcc_s libc）
    #   · `.symtab` 里 mem*/str* 变 SHN_UNDEF（动态导入），与工厂一致
    #   · `__aeabi_*` LOCAL 69 → **6**，idiv/uidiv(0B)/idiv0/ldiv0(16B)/idivmod/uidivmod(32B)
    #     **尺寸与工厂逐项相同**（同一份 lib1funcs.S）
    #   · `.gnu.version_r` 逐项与工厂一致（GLIBC_2.4/2.7 · GCC_3.5 · GLIBCXX_3.4 …）
    #   · 行为尺：共有 776→**782**、PASS 727→**735**、**DIVERGE 44→42**
    #
    # ★ 顺序照抄 GCC：`… objects … -lgcc … -lc … -lgcc`（libgcc.a 出现两次）。
    # ★ 不用 `-z undefs`：第一版带着它，`_start` 静默未解析 ⇒ **e_entry=0x0**
    #   （被 dyn_audit 的 e_entry 判据抓到）。去掉后本配置**无任何未定义符号**。
    # ==========================================================================
    sh "$ROOT/tools/fetch_bootlin63.sh" || { echo "★★ bootlin63 不可用（fail-closed）" >&2; exit 3; }
    TC="$ROOT/cache_tc/bootlin63/arm-buildroot-linux-gnueabihf"
    SL="$TC/sysroot/lib"
    SU="$TC/sysroot/usr/lib"
    LGCC="$(ls "$TC"/../lib/gcc/arm-buildroot-linux-gnueabihf/*/libgcc.a 2>/dev/null | head -1)"
    if [ -z "$LGCC" ] || [ ! -f "$LGCC" ]; then echo "★★ 缺 libgcc.a（bootlin63 不完整）" >&2; exit 3; fi
    # ★★★★★ 2026-09-29 根修（同类第 4 次；纪律 69「同一规则禁止写两处」）：
    #   旧实现（2026-09-28）只从 `$CC` 里抠 "zig"：
    #       ZIGEXE="${ZIG_BIN:-${CC% cc}}"; case "$ZIGEXE" in *zig*) ;; *) exit 3 ;;
    #   ⇒ 编译器对齐实验把 CC 设成工厂同期 GCC 6.3 时，`ZIG_BIN` 未设 ⇒ **必然 exit 3**
    #     ⇒ `toolchain-ab` 的 `gcc63-Os` / `gcc63-O2` **两条腿全 BUILD_FAILED**（CI #9/#10/#11 连续红）。
    #   现在改为调用**唯一解析器** `tools/zig_resolve.py`：
    #       ZIG_BIN → ZIG → CC 里的 zig（不含 zig 的 CC 被忽略）→ PATH → python 包 ziglang
    #   与 `ub_census.py` / `diff_exec.py` / `check_obj_fresh.py` **同源**（各写一份必然漂移）。
    ZIGEXE="$("$PY" "$(winpath "$ROOT/tools/zig_resolve.py")" 2>/dev/null)"
    if [ -z "$ZIGEXE" ]; then
        # 让解析器把"试过的候选"打到 stderr（fail-closed 必须指名，不得只说"找不到"）
        "$PY" "$(winpath "$ROOT/tools/zig_resolve.py")" >/dev/null
        echo "★★ LINK_DRIVER=lld 需要 zig 的 ld.lld，但解析不到 zig（候选见上方清单）" >&2
        exit 3
    fi
    echo "  链接器（ld.lld）来自 = $ZIGEXE"
    LLIBS="$(winpath "$LIBZ_W")
$(winpath "$LGCC")
$(winpath "$SL/libdl.so.2")
$(winpath "$SL/libm.so.6")
$(winpath "$TC/lib/libstdc++.so.6")
$(winpath "$SL/libpthread.so.0")
$(winpath "$SL/libgcc_s.so.1")
$(winpath "$SL/libc.so.6")
$(winpath "$SU/libc_nonshared.a")
$(winpath "$SU/libpthread_nonshared.a")
$(winpath "$LGCC")"
    "$ZIGEXE" ld.lld --error-limit=0 \
        -m armelf_linux_eabi \
        --entry _start \
        --dynamic-linker /lib/ld-linux-armhf.so.3 \
        -z stack-size=16777216 \
        -z now \
        -z max-page-size=0x1000 \
        --eh-frame-hdr \
        --build-id=none \
        -T "$(winpath "$ROOT/linker/factory.ld")" \
        "$(winpath "$SU/crt1.o")" $WOBJS $LLIBS \
        ${EXTRA_LDFLAGS:-} \
        -o "$(winpath "$OUT")" 2>"$ROOT/report/link_full_err.txt"
    rc=$?
    echo "链接（ld.lld 接管 / 工厂同期 sysroot）rc=$rc"
else
    $CC $ARCH $FIDELITY -no-pie \
        -Wl,-T,"$(winpath "$ROOT/linker/factory.ld")" \
        -Wl,-z,max-page-size=0x1000 \
        -Wl,-z,undefs -Wl,--build-id=none \
        ${DIAG_LDFLAGS:-} \
        $WOBJS "$LIBZ_W" ${EXTRA_LDFLAGS:-} -o "$(winpath "$OUT")" 2>"$ROOT/report/link_full_err.txt"
    rc=$?
    echo "链接（zig cc）rc=$rc"
fi
# ★★ fail-closed 必须看**链接退出码**，不能看"文件是否存在"：
#   实测教训（2026-09-27）—— 沙箱的 safe-delete 守卫会拦下 `rm -f`，
#   于是"文件不存在"这个判断会被**上一轮的旧产物**骗过（旧文件仍在 ⇒ 判定"有产物"）。
#   退出码是确定性的：rc != 0 ⇒ 本轮没有产物，直接失败。
if [ "$rc" != "0" ]; then
    echo "★★ 链接失败 ⇒ 本轮**没有可用产物**（fail-closed，禁止把旧产物当成新一轮结果）" >&2
    head -20 "$ROOT/report/link_full_err.txt" >&2 2>/dev/null || true
    exit 11
fi
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

# ★★★ 2026-09-27（本轮实证）：**体量覆盖门禁** —— 补行为尺的**结构性盲区**。
#   行为尺只在输入**真走进那段代码**时才看得见差异；入口条件不满足时两侧都"正常返回"
#   ⇒ 工厂 976 B 实现 / 我方 112 B 空壳，照样判 PASS（实测 `UpdateROM`）。
#   判据：共有函数 `ours_size / factory_size < 0.5` ⇒ SHORT ⇒ 拒绝上机。
#   已复现的两个真缺陷：`UpdateROM`（112/976）与 `ReadUSBJoy`（520/1196），均已根修。
if [ -f "$OUT" ] && [ -f "$ROOT/tools/size_coverage_gate.py" ]; then
    echo "== 体量覆盖门禁（防『空壳/缺体』：行为尺看不见的那一类）=="
    if ! $PY "$(winpath "$ROOT/tools/size_coverage_gate.py")" --ours "$(winpath "$OUT")" --top 12; then
        echo "★★ 体量覆盖门禁 FAIL —— 本产物**禁止**上机（有函数体量异常小＝疑似桩/缺体）" >&2
        exit 17
    fi
fi

# ★★★ 2026-09-27（本轮实证）：**编译期 UB 门禁** —— UB 会让优化器**静默删代码**。
#   实证：`UpdateROM` 里 Ghidra 把一块 3 字节缓冲拆成三个独立 `char`，其中两个
#   "从未被写" ⇒ 读未初始化 = UB ⇒ clang 判"条件恒真"并删掉 `fread` 之后整段（-864 B）。
#   而我们的构建一直用 `-w` 屏蔽全部警告 ⇒ 这类 UB **从来不可见**。
#   判据：高危 UB 类（对象越界 / 数组越界 / 字符串越界）命中数必须为 0。
#   可用 `CGM_SKIP_UB_GATE=1` 跳过（默认**不跳**，fail-closed）。
if [ -f "$ROOT/tools/ub_census.py" ] && [ "${CGM_SKIP_UB_GATE:-0}" != "1" ]; then
    echo "== 编译期 UB 门禁（防『优化器静默删代码』）=="
    if ! $PY "$(winpath "$ROOT/tools/ub_census.py")"; then
        echo "★★ 编译期 UB 门禁 FAIL —— 本产物**禁止**上机（UB 会让优化器删代码，行为尺看不见）" >&2
        exit 18
    fi
fi

# ★★★ 2026-09-28（本轮实证）：**单侧未建模门禁** —— 尺子按名字查 `libc_model`；
#   某符号**只在单侧存在且模型无条目** ⇒ 两侧走不同代码路径 ⇒ **假发散**。
#   实证两例：`_IO_putc`（模型只建了 `_IO_getc`）、`bcmp`（clang 把 `strcmp(x,"lit")==0`
#   优化成 `bcmp`，GCC 不做）。
#   判据：单侧未建模符号必须**全部登记**在 tools/model_asymmetry_ledger.txt（带原因）。
#   新增未登记者 ⇒ FAIL（exit 19）。
if [ -f "$OUT" ] && [ -f "$ROOT/tools/model_coverage.py" ]; then
    echo "== 单侧未建模门禁（防『尺子按名字查不到而判假发散』）=="
    if ! $PY "$(winpath "$ROOT/tools/model_coverage.py")" --ours "$(winpath "$OUT")"; then
        echo "★★ 单侧未建模门禁 FAIL —— 出现未登记的单侧未建模符号（潜在假发散），先定性再放行" >&2
        exit 19
    fi
fi
exit $rc
