#!/bin/sh
# ============================================================
# build_libkms_stub.sh —— 造一个**空**的 libkms.so.1（只为满足 driver.so 的 DT_NEEDED）
#
# 为什么可以"空"：
#   driver.so 的**未定义符号里没有任何 `kms_*`**（已实测，65 个未定义符号里只有
#   libc + libdrm 的 `drmGetCap/drmIoctl/drmMode*/drmSetClientCap` + libasound 的 `snd_*`）
#   ⇒ `libkms.so.1` 是**历史遗留依赖**，链接时写上但代码里不用。加载器只要求"该 SONAME 的文件存在"。
#
# 为什么必须造：
#   CI 沙箱里 `/arm-root` 有 libdrm.so.2 / libasound.so.2，**唯独缺 libkms.so.1**
#   ⇒ `dlopen("/sdcard/cubegm/driver.so")` 失败 ⇒ 两侧 stdout 第 11 行都是
#      `open driver.so fail, libkms.so.1: cannot open shared object file`
#   ⇒ `InitDisplay`/`InitSound`/`InitJoystick` 里所有 `dlsym` 出来的驱动函数调用**从未执行过**
#      （`video_driver_setting`/`video_driver_disp_frame`/`video_driver_setmode`/
#        `video_driver_get_size`/`sound_driver_init`/`sound_driver_playframe`）。
#   这是"硬件接口层 0% 动态验证"的直接原因（见 GAP.md G2）。
#
# ★ 公平性：两侧（工厂/重建/控制）注入**同一份**桩、同一目录 ⇒ 差分仍是"同环境比实现"。
# ★ 保守性：本桩只进 LD_LIBRARY_PATH（新场景 C 专用），默认场景 A 不受影响。
#
# 用法: CC_ARM=arm-linux-gnueabihf-gcc sh tools/build_libkms_stub.sh <outdir>
# ============================================================
set -eu

OUT="${1:?usage: build_libkms_stub.sh <outdir>}"
mkdir -p "$OUT"

# 交叉编译器选择：① 显式 CC_ARM ② 系统 arm gcc（CI 已 apt 安装）③ zig（本机/CI 都有）
if [ -n "${CC_ARM:-}" ]; then
    CC="$CC_ARM"
elif command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1; then
    CC="arm-linux-gnueabihf-gcc"
elif command -v zig >/dev/null 2>&1; then
    CC="zig cc -target arm-linux-gnueabihf"
else
    echo "!! 找不到 ARM 交叉编译器（CC_ARM / arm-linux-gnueabihf-gcc / zig）" >&2
    exit 1
fi

SRC="$OUT/_libkms_stub.c"
printf '/* 空 TU：只求产出合法 ARM 共享对象（无符号、无代码） */\n' > "$SRC"

# -nostdlib：不链任何运行时（空 .so 不需要）；-Wl,-soname：**必须**，否则加载器按文件名匹配虽可行，
#            但 SONAME 缺失会让 DT_NEEDED 的解析在某些 loader 上退化成不匹配。
# shellcheck disable=SC2086
$CC -shared -fPIC -nostdlib -Wl,-soname,libkms.so.1 "$SRC" -o "$OUT/libkms.so.1"
rm -f "$SRC"

echo "  已生成 $OUT/libkms.so.1（$(wc -c < "$OUT/libkms.so.1") B）"
