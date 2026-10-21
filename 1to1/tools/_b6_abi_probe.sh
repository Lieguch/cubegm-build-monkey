#!/bin/sh
# _b6_abi_probe.sh — B6 ABI 边界最小裁决（R221）
#
# 背景：B6 frame_hash 恒为全零基线 b5449dc5。R221 云上实测确认
#   ① shim 的 fb_lookup HIT **零行** ⇒ driver 的 mmap 不经 glibc（自封 SVC）；
#   ② 无 SetPlane/PageFlip/SetCrtc ⇒ 桩的呈现点从未被调用（note2/note6 无条件写 stderr，不受 verbose 门控）。
#   ⇒ 观测点必须上移到 ABI 边界 video_driver_disp_frame 的入参缓冲。
#
# 本脚本：只跑 **factory 单侧**（driver.so 是同一个，dumb 建立序列与主程序无关），
#   在**完整按键注入环境**（CGM_KEY2_SEED/HOOK，复刻 ci_qemu_behav）下跑 30 s，
#   用 abi_probe.so 打印每一帧入参的 FNV-1a 哈希与非零字节数。
#
# 判据：
#   hash != 全零 且 nz4k > 0  ⇒ rkgame 真的在出非零画面 ⇒ ABI 边界哈希可作 B6 真判据
#   hash == 全零 且 nz4k == 0 ⇒ qemu 里菜单本就黑屏 ⇒ B6 诚实红是环境天花板，停手观测点
#
# 用法（云开发 /workspace/1to1）：sh tools/_b6_abi_probe.sh
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 9

LOG="${B6LOG:-/tmp/b6_abi_probe.log}"
: > "$LOG"

say() { echo "$@" | tee -a "$LOG"; }

say "=== B6 ABI 边界裁决 $(date -u) ==="

# ---- 1) 环境铺设（与 _b6_adjudge.sh 同口径）----
rm -rf /arm-root-device; mkdir -p /arm-root-device
cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>"$LOG"
rm -f /arm-root-device/MANIFEST.sha256
[ -e /arm-root-device/lib/ld-linux-armhf.so.3 ] || ln -sf ld-2.29.so /arm-root-device/lib/ld-linux-armhf.so.3

mkdir -p /sdcard/cubegm; cp -a golden/sdcard_min/. /sdcard/cubegm/ 2>>"$LOG" || true

[ -e /dev/mem ] || { : > /dev/mem 2>/dev/null && chmod 666 /dev/mem 2>/dev/null; } || true
mkdir -p /dev/dri 2>/dev/null || true
for i in 0 1; do [ -e /dev/dri/card$i ] || : > /dev/dri/card$i 2>/dev/null || true; done

# ---- 2) 编译器（zig 优先，钉 glibc 2.29）----
if [ -z "${ZIG:-}" ]; then
    ZIG="$(ls /root/.local/share/uv/python/*/lib/python3*/site-packages/ziglang/zig 2>/dev/null | head -1 || true)"
fi
if [ -z "${ZIG:-}" ] || [ ! -x "$ZIG" ]; then
    say "★★ 找不到 zig，改用 arm-linux-gnueabihf-gcc（会引入较高 GLIBC 要求）"
    ZIG=""
    CC_ARM="arm-linux-gnueabihf-gcc"
    ARCH_FLAGS="-march=armv7-a -mfloat-abi=hard -mfpu=neon"
else
    CC_ARM="$ZIG cc"
    ARCH_FLAGS="-target arm-linux-gnueabihf.2.29 -mfloat-abi=hard -mfpu=neon"
fi
say "  CC_ARM=$CC_ARM"

# ---- 3) 建三桩 + guest_shim + abi_probe ----
say "--- 建桩 ---"
CC="$CC_ARM" sh tools/build_libkms_stub.sh   report/stublib      >>"$LOG" 2>&1 || say "  kms fail"
CC="$CC_ARM" sh tools/build_libdrm_stub.sh   report/drmstublib   >>"$LOG" 2>&1 || say "  drm fail"
CC="$CC_ARM" sh tools/build_libasound_stub.sh report/alsastublib >>"$LOG" 2>&1 || say "  alsa fail"

say "--- 建 guest_shim（含 ABI 探针，同一 DSO）---"
# ★ 必须同一 DSO：独立 .so 叠加会因 RTLD_NEXT 语义错位而无限递归（R221 实测 exit=139）。
CC="$CC_ARM" CGM_ABI_PROBE_BUILD=1 sh tools/build_guest_shim.sh report/guest_shim_probe.so >>"$LOG" 2>&1 \
    || { say "★★ guest_shim(含探针) 编译失败（见 $LOG）"; tail -20 "$LOG"; exit 11; }
ls -l report/guest_shim_probe.so report/drmstublib/libdrm.so.2 >>"$LOG" 2>&1

# 自证：必须导出 T dlsym（否则 wrap 根本没生效）
say "--- 自证：guest_shim_probe.so 是否导出 dlsym ---"
if command -v nm >/dev/null 2>&1; then
    nm -D report/guest_shim_probe.so 2>/dev/null | grep -E ' T (dlsym|probe_disp_frame)' | tee -a "$LOG" || say "  (未导出 dlsym!)"
elif command -v arm-linux-gnueabihf-nm >/dev/null 2>&1; then
    arm-linux-gnueabihf-nm -D report/guest_shim_probe.so 2>/dev/null | grep -E ' T (dlsym|probe_disp_frame)' | tee -a "$LOG" || say "  (未导出 dlsym!)"
else
    say "  (no nm)"
fi

# ---- 4) 跑 factory（完整按键注入环境）----
say "--- 跑 factory（30 s，含 CGM_KEY2_SEED/HOOK）---"
LIBPATH="$ROOT/report/alsastublib:$ROOT/report/drmstublib:/arm-root-device/usr/lib:/arm-root-device/lib"
Q=/usr/bin/qemu-arm-static

cp -f golden/factory.rkgame.bin /sdcard/cubegm/rkgame
chmod +x /sdcard/cubegm/rkgame
cp -f report/guest_shim_probe.so /sdcard/cubegm/guest_shim_probe.so

( cd /sdcard/cubegm && timeout 40 $Q -L /arm-root-device -cpu cortex-a7 \
    -E LD_PRELOAD=/sdcard/cubegm/guest_shim_probe.so \
    -E LD_LIBRARY_PATH="$LIBPATH" \
    -E CGM_SHIM_VERBOSE=0 \
    -E CGM_ABI_PROBE=1 \
    -E CGM_KEY2_SEED=1 -E CGM_KEY2_HOOK=1 \
    -E CGM_WORK=/sdcard/cubegm -E CGM_TIMEOUT=30 \
    -E HOME=/tmp -E TMPDIR=/tmp -E LC_ALL=C -E LANG=C \
    /sdcard/cubegm/rkgame > /tmp/b6p_stdout.txt 2> /tmp/b6p_stderr.txt )
say "  qemu exit=$?"

say ""
say "########## 判据 1：ABI 边界（abi_probe）##########"
grep -a 'abiprobe' /tmp/b6p_stderr.txt | head -20 | tee -a "$LOG" || say "  (无 abiprobe 行)"
say "  ---- abiprobe 行数 ----"
grep -a -c 'abiprobe' /tmp/b6p_stderr.txt | tee -a "$LOG" || true

say ""
say "########## 判据 2：桩侧呈现点（drm_stub）##########"
grep -aE 'frame#|SetPlane_geom|PageFlip_geom|SetCrtc_fb|SUMMARY' /tmp/b6p_stderr.txt | head -12 | tee -a "$LOG" || say "  (无呈现点行)"

say ""
say "########## 判据 3：driver 加载 / 里程碑（stdout）##########"
grep -a 'driver.so' /tmp/b6p_stdout.txt | head -3 | tee -a "$LOG" || true
say "  stdout 行数 = $(wc -l < /tmp/b6p_stdout.txt)"
say "  stderr 行数 = $(wc -l < /tmp/b6p_stderr.txt)"
say "  菜单日志 menu.log = $(wc -l < /sdcard/cubegm/menu.log 2>/dev/null || echo NA) 行"

say ""
say "########## 原文取回（供本地核对）##########"
cp -f /tmp/b6p_stderr.txt "$ROOT/report/_r221_abi_probe_stderr.txt" 2>/dev/null || true
cp -f /tmp/b6p_stdout.txt "$ROOT/report/_r221_abi_probe_stdout.txt" 2>/dev/null || true
say "  已存 report/_r221_abi_probe_stderr.txt ($(wc -c < /tmp/b6p_stderr.txt) B)"

say ""
say "REMOTE-DONE"
