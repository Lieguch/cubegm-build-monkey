#!/bin/sh
# ============================================================
# build_libdrm_stub.sh —— 造桩 `libdrm.so.2`（让厂商闭源 driver.so 的图形初始化能过）
#
# 和 build_libkms_stub.sh 是同一套机制（LD_LIBRARY_PATH 前置覆盖），但**不是空桩**：
# 它实现 driver.so 实际引用的 17 个 `drm*` 符号，并保证返回值**全部完整初始化**。
#
# 为什么需要：
#   设备真实 rootfs 里有 `libkms.so.1` ⇒ `dlopen(driver.so)` 成功
#   ⇒ 进 `video_drivers_init()` → `gr_init()`，而沙箱没有真 DRM 设备
#   ⇒ `gr_init` 拿到 NULL ⇒ `driver.so + 0x3ca8` 的 `ldr r3,[r3]`（r3=0）必崩。
#   ⇒ 只要 driver.so 加载成功，沙箱必死在厂商代码里，走不到 rkgame 的任何菜单逻辑。
#   本桩把 DRM 初始化"做成成功"，让执行流越过 `gr_init`。
#
# ★ 公平性：两侧（工厂/重建/控制）注入同一份桩、同一目录 ⇒ 仍是"同环境比实现"。
# ★ 保守性：只进 LD_LIBRARY_PATH，且由**显式开关**（`CGM_DRM_STUB=1`）启用；默认关，行为不变。
# ★ 位置必须**最前**：`LD_LIBRARY_PATH=<stub 目录>:<sysroot 库目录>`，否则真 libdrm 先生效。
#
# 用法: sh tools/build_libdrm_stub.sh <outdir>
# 例:   sh tools/build_libdrm_stub.sh report/stublib
# ============================================================
set -eu

OUT="${1:?usage: build_libdrm_stub.sh <outdir>}"
mkdir -p "$OUT"

# 交叉编译器选择：① 显式 CC_ARM ② 系统 arm gcc（CI 已 apt 安装）③ zig
TARGET="arm-linux-gnueabihf.2.29"     # 设备真实 glibc = 2.29（实测自 org.bin 的 rootfs）
if [ -n "${CC_ARM:-}" ]; then
    CC="$CC_ARM"
elif command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1; then
    CC="arm-linux-gnueabihf-gcc"
elif command -v zig >/dev/null 2>&1; then
    CC="zig cc"
elif [ -n "${CC:-}" ]; then
    :   # 用调用方给的 CC
else
    echo "!! 找不到 ARM 交叉编译器（CC_ARM / arm-linux-gnueabihf-gcc / zig / CC）" >&2
    exit 1
fi

# ★★ 关键：zig **必须显式给 `-target`**，否则它按**本机宿主**编译。
#   实测（2026-09-19）：`CC_ARM="<zig> cc"` 不加 -target ⇒ 产出 Windows COFF，
#   报错 `lld-link: undefined symbol: _DllMainCRTStartup` —— 而这个错**看不出**是"目标架构错了"，
#   很容易被误读成"缺 memset"。凡是 zig 路径，这里统一补 `-target`。
case "$CC" in
  *zig*)
     case "$CC" in
       *-target*) ;;                                    # 调用方已指定，尊重
       *) CC="$CC -target $TARGET" ;;
     esac ;;
esac
echo "  [libdrm 桩] CC=$CC"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/tools/guest_shim/drm_stub.c"
[ -f "$SRC" ] || { echo "!! 缺源文件 $SRC" >&2; exit 1; }

# ★ Windows 开发机：zig.exe 是**原生 Windows 程序**，不认 `/d/...` 这类 MSYS 路径
#   （技能库第 24 条：入参与 -o 都要 cygpath -w）。
#   实测踩坑（2026-09-19）：不给 → zig 报 `error: CacheCheckFailed`（**症状与病因完全无关**，
#   极易被误读成缓存/源码问题；实际是路径无法解析）。
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

# -nostdlib：本桩不调用 libc（静态数据 + 纯指针写 + 自带 hidden memset）⇒ 无任何运行时依赖，
#            也就不会因为宿主/设备的 glibc 差异而引入新变量。
# -fno-unwind-tables / -fno-asynchronous-unwind-tables：不加会因 .ARM.exidx 引用
#            `__aeabi_unwind_cpp_pr0/pr1`，而 `-nostdlib` 不提供它们 ⇒ 留下 2 个未定义符号。
#            加上后产物**完全自洽（0 未定义符号）**，不依赖任何库。
# -Wl,-soname：必须与 driver.so 的 DT_NEEDED 完全一致（libdrm.so.2）；
#            SONAME 缺失会让 DT_NEEDED 的解析在某些 loader 上退化成"按文件名匹配"。
# shellcheck disable=SC2086
$CC -shared -fPIC -nostdlib -O1 -w \
    -fno-unwind-tables -fno-asynchronous-unwind-tables \
    -Wl,-soname,libdrm.so.2 \
    "$(winpath "$SRC")" -o "$(winpath "$OUT/libdrm.so.2")"

echo "  已生成 $OUT/libdrm.so.2（$(wc -c < "$OUT/libdrm.so.2") B）"

# ---- 自证：导出符号必须覆盖 driver.so 引用的那 17 个 drm* ----
if command -v arm-linux-gnueabihf-nm >/dev/null 2>&1; then
    NM=arm-linux-gnueabihf-nm
elif command -v nm >/dev/null 2>&1; then
    NM=nm
else
    NM=""
fi
NEED="drmGetCap drmIoctl drmModeAddFB2 drmModeFreeConnector drmModeFreeCrtc \
drmModeFreeEncoder drmModeFreeResources drmModeGetConnector drmModeGetCrtc \
drmModeGetEncoder drmModeGetPlaneResources drmModeGetResources drmModePageFlip \
drmModeRmFB drmModeSetCrtc drmModeSetPlane drmSetClientCap"
if [ -n "$NM" ]; then
    got="$($NM -D --defined-only "$OUT/libdrm.so.2" 2>/dev/null | awk '{print $NF}' | sort)"
    miss=""
    for s in $NEED; do
        echo "$got" | grep -qx "$s" || miss="$miss $s"
    done
    if [ -n "$miss" ]; then
        echo "  ★ 缺失符号:$miss" >&2
        exit 1
    fi
    echo "  自证：17 个 drm* 全部导出 ✓"
fi
