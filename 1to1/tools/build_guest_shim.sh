#!/bin/sh
# build_guest_shim.sh — 构建「假硬件 shim」（armhf DSO，供 LD_PRELOAD 注入两侧 guest）
#
# 为什么需要：`InitJoystick()` 里 `sunxi_gpio_init()` 因 `open("/dev/mem")` / `mmap(物理地址)`
# 在 qemu 下必然失败而返回非 0 ⇒ 打印 `Failed to initialize GPIO`，随后**无条件**执行
# `InitRFJoystick()`，其中 `*(u32*)(GPIO2 + 4) |= 8` 而 `GPIO2 == NULL` ⇒ SIGSEGV。
# 于是两侧的可观测窗口只有 13 行 stdout，"等价"很浅。shim 把「物理寄存器映射」换成匿名零页，
# 让 GPIO/SPI/SFC 初始化能跑完，从而把可观测窗口推深。
#
# ★ 两侧加载**同一份** shim（同一绝对路径），因此差分仍然是「同一环境下比实现」。
#
# 用法: CC="<zig> cc" sh tools/build_guest_shim.sh <out.so>
# 退出码: 0 = 产出；非 0 = 失败（调用方自行决定是否降级为"不带 shim 跑"）
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:?usage: build_guest_shim.sh <out.so>}"
CC="${CC:-}"
SRC="$ROOT/tools/guest_shim/fake_mem.c"

# ★★ R221：可选叠加 ABI 探针（`CGM_ABI_PROBE_BUILD=1`）。
#   为什么必须**编进同一个 DSO** 而不是单独一个 .so：
#     探针要 wrap 全局 `dlsym`。若做成独立 .so 并 LD_PRELOAD 叠加在 guest_shim 之前，
#     guest_shim 内部的 `dlsym(RTLD_NEXT,"fopen")` 会落到探针实现；
#     而 RTLD_NEXT 的语义是「从**调用者** link_map 之后找」——
#     转发进另一个 DSO 后调用者上下文已变，会先命中 guest_shim **自己**的 fopen
#     ⇒ 无限递归 ⇒ SIGSEGV（R221 实测 exit=139、stdout 0 行，两次复现）。
#     编进同一个 DSO 后，`dlsym(RTLD_NEXT,..)` 的调用者与真 dlsym 的返回地址同属一个
#     link_map ⇒ glibc 从本 so 之后继续找（libc），语义天然正确、不递归。
#   ★ 默认**不编**（`CGM_ABI_PROBE_BUILD` 未设 ⇒ 行为与旧版逐字节一致），
#     避免影响 CI 行为差分主链。
EXTRA=""
if [ "${CGM_ABI_PROBE_BUILD:-0}" = "1" ]; then
    EXTRA="$ROOT/tools/guest_shim/abi_probe.c"
    echo "  [shim] + ABI 探针（abi_probe.c）"
fi

# ★ 2026-10-04（第 138 轮）统一到**唯一权威探测** tools/cgm_cc_probe.sh。
#   历程：第 137 轮把 `CC="${CC:-cc}"`（硬编宿主 cc）改成四段探测；
#   第 138 轮发现同一段探测已在 **6 个脚本里各写一份** ⇒ 违反「同一规则禁止写两处」，
#   且其中一个副本的 sed 分隔符与 alternation 冲突（自证抓出 5/5 腿全空）。
#   ⇒ 收敛到 cgm_cc_probe.sh 一处；本文件只保留 source 调用。
. "$(cd "$(dirname "$0")" && pwd)/cgm_cc_probe.sh" \
    || { echo "!! 编译器探测失败（见 cgm_cc_probe.sh 的说明）" >&2; exit 13; }

# ★ Windows 开发机：zig.exe 是**原生 Windows 程序**，不认 `/d/...` 这类 MSYS 路径
#   （技能库第 24 条：入参与 -o 都要 cygpath -w；-m 只用于 bash 通配）。
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

# ★ 并发/多次调用时共用 zig global cache 会 CacheCheckFailed（技能库第 27 条）⇒ 给本脚本一个专属目录。
if [ -z "${ZIG_GLOBAL_CACHE_DIR:-}" ]; then
    ZIG_GLOBAL_CACHE_DIR="${TMPDIR:-/tmp}/zigcache_guestshim"
    export ZIG_GLOBAL_CACHE_DIR
fi

# ★★ 目标 glibc 版本必须钉死 —— 这不是优化，是"能不能在设备上跑"的前提。
#   实测（2026-09-19）：不钉版本时 zig 用 arm-linux-gnueabihf 的默认 glibc，产物要求
#   **GLIBC_2.34**；而设备真实 glibc 是 **2.29**（org.bin 的 rootfs 里是
#   `GNU C Library (Buildroot) stable release version 2.29`，实测）
#   ⇒ 不钉版本的话，shim 在设备上**根本加载不了**，我们永远做不了"贴近设备"的差分，
#     更不可能把它带上真机（而 shim 是差分环境的组成部分，不能比被测对象更苛刻）。
#   钉 2.29 后产物只要求 ≤2.29：CI 的 jammy(2.35) 与设备(2.29) 上**都**能加载。
#   `CGM_SHIM_GLIBC` 可覆盖（例如做"设备向下兼容"实验时钉 2.7）。
SHIM_GLIBC="${CGM_SHIM_GLIBC:-2.29}"
# zig 用 -target；GCC 用 -march（见技能库第 68 条：换工具链前必须对齐 flags）
case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf.${SHIM_GLIBC} -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon" ;;
esac
echo "  [shim] CC=$CC  目标 glibc=${SHIM_GLIBC}"

mkdir -p "$(dirname "$OUT")"
# shellcheck disable=SC2086
# shellcheck disable=SC2086
if [ -n "$EXTRA" ]; then
    $CC $ARCH -shared -fPIC -O2 -w "$(winpath "$SRC")" "$(winpath "$EXTRA")" -o "$(winpath "$OUT")" || exit 1
else
    $CC $ARCH -shared -fPIC -O2 -w "$(winpath "$SRC")" -o "$(winpath "$OUT")" || exit 1
fi
ls -la "$OUT"

# ★★ 2026-11-04：**产物 glibc 需求自检**（fail-closed，防"仪器静默降级"）
#   病灶：`ARCH` 的 zig 分支钉了 glibc 版本，但 **GCC 分支没钉** ⇒ GCC 用**宿主 libc 头**
#     ⇒ 产物可能要求**高于设备**的 GLIBC_x.y。
#   实测（InstaBox / Debian 13 + gcc-arm-linux-gnueabihf）：产物要求 GLIBC_2.34 与
#     GLIBC_2.38 ⇒ 设备 sysroot（Buildroot glibc **2.29**）**拒绝加载**：
#     `/sdcard/cubegm/rkgame: /arm-root-device/lib/libc.so.6: version 'GLIBC_2.38' not found`
#     ⇒ **guest 连 M0（进程启动）都到不了**，三侧全 exit=1。
#   ★ 为什么这是"仪器缺陷"而不是"环境噪声"：shim **编译成功**（exit 0）⇒ 调用方
#     `ci_qemu_behav.sh` 的 `if ... sh build_guest_shim.sh` 判成功 ⇒ **不会触发它那句
#     响亮的"构建失败"告警** ⇒ 门禁"看起来跑完了"，实则全链路失真。
#   ⇒ 根修：**产物必须自证**它的 glibc 需求 ≤ 目标基线；超标 ⇒ ① 能用 zig 就用 zig
#     重编（zig 可精确 `-target arm-linux-gnueabihf.<版本>`）→ 再验；② 仍超标 ⇒
#     **exit 1 fail-closed**（宁可门禁红，不许静默失真）。
_glibc_max_need() {           # 打印产物要求的最高 GLIBC_x.y（形如 2.38；无则空）
    _so="$1"; _re=""
    for t in readelf arm-linux-gnueabihf-readelf; do
        command -v "$t" >/dev/null 2>&1 && { _re="$t"; break; }
    done
    [ -z "$_re" ] && return 0
    "$_re" -V "$_so" 2>/dev/null \
      | sed -n 's/.*Name: GLIBC_\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1 \2/p' \
      | awk '{v=$1*100+$2; if (v>m) m=v} END {if (m>0) printf "%d.%d\n", int(m/100), m%100}'
}
_ver_num() { echo "$(( $(echo "$1" | cut -d. -f1) * 100 + $(echo "$1" | cut -d. -f2) ))"; }
_need="$(_glibc_max_need "$OUT")"
_limit="$(echo "$SHIM_GLIBC" | cut -d. -f1).$(echo "$SHIM_GLIBC" | cut -d. -f2)"
if [ -z "$_need" ]; then
    echo "  [shim] glibc 需求：无法判定（无 readelf 或产物无版本需求）⇒ 跳过自检"
elif [ "$(_ver_num "$_need")" -le "$(_ver_num "$_limit")" ]; then
    echo "  [shim] glibc 需求自检：最高 GLIBC_$_need ≤ 目标 $_limit ✓"
else
    echo "  [shim] glibc 需求自检：★★ 最高 GLIBC_$_need > 目标 $_limit ⇒ 产物在设备上**装不上**"
    # ① 能用 zig 就用 zig 重编（zig 能精确钉 glibc 基线）
    _zig=""
    command -v zig >/dev/null 2>&1 && _zig="$(command -v zig)"
    if [ -z "$_zig" ]; then
        _zig="$(python3 -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)"
    fi
    if [ -n "$_zig" ]; then
        echo "  [shim] 改用 zig 重编（-target arm-linux-gnueabihf.${SHIM_GLIBC}）: $_zig"
        _ZARCH="-target arm-linux-gnueabihf.${SHIM_GLIBC} -mfloat-abi=hard -mfpu=neon"
        if [ -n "$EXTRA" ]; then
            "$_zig" cc $_ZARCH -shared -fPIC -O2 -w "$(winpath "$SRC")" "$(winpath "$EXTRA")" -o "$(winpath "$OUT")" || exit 1
        else
            "$_zig" cc $_ZARCH -shared -fPIC -O2 -w "$(winpath "$SRC")" -o "$(winpath "$OUT")" || exit 1
        fi
        _need2="$(_glibc_max_need "$OUT")"
        if [ -n "$_need2" ] && [ "$(_ver_num "$_need2")" -le "$(_ver_num "$_limit")" ]; then
            echo "  [shim] glibc 需求自检：重编后最高 GLIBC_$_need2 ≤ 目标 $_limit ✓"
            ls -la "$OUT"
            exit 0
        fi
        echo "  [shim] 重编后仍不达标（最高 GLIBC_${_need2:-?} > $_limit）"
    else
        echo "  [shim] 无 zig 可用 ⇒ 无法钉 glibc 基线"
    fi
    echo "★★ fail-closed：shim 的 glibc 需求高于设备基线 $_limit ⇒ 仪器不可信，**禁止继续**。"
    echo "★★ 修法：① pip install ziglang（用 zig cc -target arm-linux-gnueabihf.${SHIM_GLIBC}）；"
    echo "★★       ② 或设 CGM_SHIM_GLIBC=<设备 glibc>；③ 或用工厂同期工具链（bootlin63）编 shim。"
    exit 1
fi
