#!/bin/sh
# ============================================================
# build_libasound_stub.sh —— 造桩 `libasound.so.2`（让厂商闭源 driver.so 的音频初始化能过）
#
# 和 build_libdrm_stub.sh 是同一套机制（LD_LIBRARY_PATH 前置覆盖），实现 driver.so
# 实测引用的全部 20 个 `snd_*` 符号，返回值**全部完整初始化/语义自洽**。
#
# 为什么需要（见 GAP 16.23）：
#   桩 libdrm 打通图形后，两侧都止于
#     `pcm.c:3009: snd_pcm_avail: Assertion 'pcm' failed.`（该行来自真实 alsa-lib）
#   ⇒ `snd_pcm_open()` 在假硬件上失败，driver.so 未检查返回值就继续用 NULL 句柄 ⇒ abort()。
#   本桩把音频初始化也"做成成功"，让执行流越过这次 abort。
#
# ★ 全仓普查：**只有 driver.so 引用 `snd_*`**（工厂 rkgame / 重建 elf / icube 均为 0）
#   ⇒ 整体替换 `libasound.so.2` 不影响任何其它模块。
# ★ 公平性：两侧（工厂/重建/控制）注入同一份桩、同一目录 ⇒ 仍是"同环境比实现"。
# ★ 保守性：只进 LD_LIBRARY_PATH，且由**显式开关**（`CGM_ALSA_STUB=1`）启用；默认关。
# ★ 位置必须**最前**（与 drm 桩同区），否则真 libasound 先生效。
#
# 用法: sh tools/build_libasound_stub.sh <outdir>
# 例:   sh tools/build_libasound_stub.sh report/alsastublib
# ============================================================
set -eu

OUT="${1:?usage: build_libasound_stub.sh <outdir>}"
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
#   报错 `lld-link: undefined symbol: _DllMainCRTStartup` —— 这个错**看不出**是"目标架构错了"。
case "$CC" in
  *zig*)
     case "$CC" in
       *-target*) ;;
       *) CC="$CC -target $TARGET" ;;
     esac ;;
esac
echo "  [libasound 桩] CC=$CC"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/tools/guest_shim/alsa_stub.c"
[ -f "$SRC" ] || { echo "!! 缺源文件 $SRC" >&2; exit 1; }

# ★ Windows 开发机：zig.exe 是**原生 Windows 程序**，不认 `/d/...` 这类 MSYS 路径。
#   实测踩坑（2026-09-19）：不给 → zig 报 `error: CacheCheckFailed`（症状与病因完全无关）。
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

# -nostdlib + hidden memset：零运行时依赖（见 alsa_stub.c 顶部说明）
# -fno-unwind-tables：否则 .ARM.exidx 会引用 `__aeabi_unwind_cpp_pr0/pr1` ⇒ 留下未定义符号
# -Wl,-soname：必须与 driver.so 的 DT_NEEDED 完全一致（libasound.so.2）
# shellcheck disable=SC2086
$CC -shared -fPIC -nostdlib -O1 -w \
    -fno-unwind-tables -fno-asynchronous-unwind-tables \
    -Wl,-soname,libasound.so.2 \
    "$(winpath "$SRC")" -o "$(winpath "$OUT/libasound.so.2")"

echo "  已生成 $OUT/libasound.so.2（$(wc -c < "$OUT/libasound.so.2") B）"

# ---- 自证：导出符号必须覆盖 driver.so 实测引用的 20 个 snd_* ----
if command -v arm-linux-gnueabihf-nm >/dev/null 2>&1; then
    NM=arm-linux-gnueabihf-nm
elif command -v nm >/dev/null 2>&1; then
    NM=nm
else
    NM=""
fi
NEED="snd_pcm_avail snd_pcm_close snd_pcm_drop snd_pcm_hw_params \
snd_pcm_hw_params_any snd_pcm_hw_params_get_buffer_size snd_pcm_hw_params_get_channels \
snd_pcm_hw_params_get_period_size snd_pcm_hw_params_set_access \
snd_pcm_hw_params_set_buffer_size_near snd_pcm_hw_params_set_channels \
snd_pcm_hw_params_set_format snd_pcm_hw_params_set_period_size_near \
snd_pcm_hw_params_set_rate_near snd_pcm_hw_params_sizeof snd_pcm_open \
snd_pcm_prepare snd_pcm_recover snd_pcm_start snd_pcm_writei"
if [ -n "$NM" ]; then
    got="$($NM -D --defined-only "$OUT/libasound.so.2" 2>/dev/null | awk '{print $NF}' | sort)"
    miss=""
    for s in $NEED; do
        echo "$got" | grep -qx "$s" || miss="$miss $s"
    done
    if [ -n "$miss" ]; then
        echo "  ★ 缺失符号:$miss" >&2
        exit 1
    fi
    echo "  自证：20 个 snd_* 全部导出 ✓"
fi
