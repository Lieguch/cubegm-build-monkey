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
CC="${CC:-cc}"
SRC="$ROOT/tools/guest_shim/fake_mem.c"

# ★ Windows 开发机：zig.exe 是**原生 Windows 程序**，不认 `/d/...` 这类 MSYS 路径
#   （技能库第 24 条：入参与 -o 都要 cygpath -w；-m 只用于 bash 通配）。
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

# ★ 并发/多次调用时共用 zig global cache 会 CacheCheckFailed（技能库第 27 条）⇒ 给本脚本一个专属目录。
if [ -z "${ZIG_GLOBAL_CACHE_DIR:-}" ]; then
    ZIG_GLOBAL_CACHE_DIR="${TMPDIR:-/tmp}/zigcache_guestshim"
    export ZIG_GLOBAL_CACHE_DIR
fi

# zig 用 -target；GCC 用 -march（见技能库第 68 条：换工具链前必须对齐 flags）
case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon" ;;
esac

mkdir -p "$(dirname "$OUT")"
# shellcheck disable=SC2086
$CC $ARCH -shared -fPIC -O2 -w "$(winpath "$SRC")" -o "$(winpath "$OUT")" || exit 1
ls -la "$OUT"
