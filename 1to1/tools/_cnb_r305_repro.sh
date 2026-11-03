#!/bin/sh
# =============================================================================
# build_r305_remote.sh —— R305 CNB 云开发复现段（随 tar 上传，workspace 内执行）
#
# 目标：与 .github/workflows/1to1-qemu-behav.yml step 12 **同口径**复现
#       「行为采集 + 差分 ★ 硬门禁」，产出 report/qemu/behav_diff.txt 等判据数据，
#       用于回答：本轮 qemu-behav 的失败是否与 R305 ZIPENTRY 修复相关
#       （判据行是否与前三轮基线同形）。
#
# 同口径复刻清单（逐条对齐 workflow）：
#   · SYSROOT=/arm-root-device（golden/device_rootfs_min，glibc 2.29）
#   · CGM_WORK=/sdcard/cubegm（saves/states 空目录，与 step 7 一致）
#   · CGM_TIMEOUT=30 / CGM_LIBKMS_STUB=1 / CGM_DRM_STUB=1 / CGM_ALSA_STUB=1
#   · CGM_KEY2_SEED=1 / CGM_KEY2_HOOK=1
#   · 三桩（build_libkms/drm/asound_stub.sh，与 step 11 同脚本）
#   · guest shim：CC=zig 0.16.0（workflow 同款 pip 版本），-target 钉 glibc 2.29
#     （★ 首轮教训：Debian13 的 gcc-14 cross 打的 shim 引用 GLIBC_2.38 ⇒ 侧载失败）
#   · 被测二进制 = 本机从 CI artifact 下载的 d34316b1…（无本地重编）
# 阳性对照：behav_diff 的 factory 侧必须 RAN；若装置故障 ⇒ 结论作废。
# =============================================================================
set -u
L=/tmp/r305_remote.log
say() { echo "$@"; echo "$@" >>"$L"; }

for d in /workspace/1to1 /workspace; do
  [ -d "$d/tools" ] && PROJ=$d && break
done
: "${PROJ:?PROJ 未找到}"
cd "$PROJ" || exit 9
say "== PROJ=$PROJ  $(date -u)"

# ---- 0) ELF 就位（本机上传的 CI artifact 产物） ------------------------------
mkdir -p build
if [ -f build/_r305_elf ]; then
  cp -f build/_r305_elf build/rkgame.rebuilt.elf
  say "ELF(CI artifact) $(wc -c <build/rkgame.rebuilt.elf) B  $(sha256sum build/rkgame.rebuilt.elf | cut -c1-16)"
fi
for f in build/rkgame.rebuilt.elf golden/factory.rkgame.bin golden/sdcard_min/MANIFEST.sha256; do
  [ -s "$f" ] || { say "★★ 缺 $f"; exit 11; }
done

# ---- 1) apt：qemu-user-static / 交叉 binutils / gdb / strace -----------------
# ★★ R305c 根因修复（首轮 INCONCLUSIVE 的真因）：首轮 shim/桩由 **Debian 13 自带的
#   gcc-14-arm-linux-gnueabihf（glibc 2.41）**构建 ⇒ guest_shim.so 引用
#   `GLIBC_2.38 / GLIBC_2.34` ⇒ 设备 rootfs（glibc 2.29）的 guest ld.so 拒绝加载
#   ⇒ LD_PRELOAD 失败 ⇒ 两侧 guest 启动即 exit=1、stdout=0（behav_factory.json
#   events 两行 version not found 为直接证据）。
#   CI 的口径：workflow step「安装 zig」pip 装 ziglang==0.16.0 并
#   `echo "CC=$ZIG cc" >> $GITHUB_ENV` ⇒ cgm_cc_probe 优先级①命中 zig ⇒
#   build_guest_shim.sh 按 `-target arm-linux-gnueabihf.2.29` 构建（钉死设备 glibc）。
#   ⇒ 本段照搬同口径；arm cross gcc 仅作 objdump/dump_analyze 用（CC 显式置 zig，
#     cgm_cc_probe ①优先，不会被误用）。
say "== [1/6] apt"
export DEBIAN_FRONTEND=noninteractive
(apt-get update -qq >/dev/null 2>&1 || true)
apt-get install -y -qq qemu-user-static gcc-arm-linux-gnueabihf \
  binutils-arm-linux-gnueabihf gdb-multiarch strace file python3 python3-pip python3-pyelftools \
  >>"$L" 2>&1 || say "   apt 部分失败（继续，后面见真章）"
for c in qemu-arm-static arm-linux-gnueabihf-gcc arm-linux-gnueabihf-objdump; do
  say "   $c = $(command -v $c || echo MISSING)"
done

# ---- 1b) zig 0.16.0 + 显式 CC（对齐 CI workflow「安装 zig」步骤） ---------------
# ★ 版本必须钉 0.16.0：CNB 镜像**预装的是 ziglang 0.17.0**（uv site-packages），
#   而 CI workflow 钉 `ziglang==0.16.0`。zig 版本会改变产物引用的 glibc 符号版本
#   ⇒ 版本不等即口径不等。且不能 `pip install` 覆盖预装路径（import 解析顺序不确定），
#   故装到**独立目录** --target，再用绝对路径调用 ⇒ 版本确定、可审计。
say "== [1b/6] zig 0.16.0 + CC（shim 必须 ≤ 设备 glibc 2.29）"
ZIGDIR=/tmp/r305_ziglang
rm -rf "$ZIGDIR"
python3 -m pip install --quiet --break-system-packages --target "$ZIGDIR" ziglang==0.16.0 >>"$L" 2>&1 \
  || python3 -m pip install --quiet --target "$ZIGDIR" ziglang==0.16.0 >>"$L" 2>&1 \
  || { say "★★ ziglang 0.16.0 安装失败"; exit 11; }
ZIG="$ZIGDIR/ziglang/zig"
[ -x "$ZIG" ] || chmod +x "$ZIG" 2>>"$L" || true
ZVER="$("$ZIG" version 2>>"$L")"
say "   ZIG=$ZIG  version=$ZVER"
[ "$ZVER" = "0.16.0" ] || { say "★★ zig 版本 $ZVER ≠ CI 的 0.16.0 ⇒ 口径不等，终止"; exit 11; }
export CC="$ZIG cc"
export ZIG_GLOBAL_CACHE_DIR="/tmp/r305_zigcache"
say "   CC=$CC  （cgm_cc_probe ①优先 ⇒ 全场 shim/桩同一把 zig）"

# ---- 1c) shim 预检（canary）：先建一份并断言其 GLIBC 需求 ≤ 2.29 ---------------
#    首轮崩点的机械门禁：objdump -T 抓 shim 引用的最高 GLIBC_2.x 次版本号。
#    >29 ⇒ 设备 2.29 加载必失败（正是首轮 2.38/2.34 事故）。fail-closed，不猜。
say "== [1c/6] shim 预检（glibc ≤ 2.29）"
SHIM_PRE=/tmp/r305_shim_preflight.so
rm -f "$SHIM_PRE"
CGM_SHIM_GLIBC="${CGM_SHIM_GLIBC:-2.29}" CC="$ZIG cc" sh tools/build_guest_shim.sh "$SHIM_PRE" >>"$L" 2>&1 \
  || { say "★★ shim 预检构建失败"; exit 12; }
say "   shim=$(wc -c <"$SHIM_PRE") B  $(file -b "$SHIM_PRE" | cut -c1-60)"
case "$(file -b "$SHIM_PRE")" in
  *ARM*|*arm*) ;;
  *) say "★★ shim 非 ARM ELF（zig -target 未生效？）"; exit 13 ;;
esac
MIN="$(arm-linux-gnueabihf-objdump -T "$SHIM_PRE" 2>/dev/null | grep -o 'GLIBC_2\.[0-9]\+' | cut -d. -f2 | sort -n | tail -1)"
say "   shim 最高 GLIBC 次版本 = ${MIN:-无}"
if [ -z "$MIN" ]; then
  say "!! （未抓到 GLIBC 符号版本——纯 -nostdlib? 记为观察项，继续）"
elif [ "$MIN" -gt 29 ]; then
  say "★★ shim 引用 GLIBC_2.$MIN > 设备 2.29 ⇒ 必加载失败（同首轮事故）"
  exit 13
fi

# ---- 2) 设备 sysroot + 工作目录（对齐 step 6/7） ------------------------------
say "== [2/6] /arm-root-device + /sdcard/cubegm"
mkdir -p /arm-root-device
cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>"$L" || sudo cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>"$L"
rm -f /arm-root-device/MANIFEST.sha256
mkdir -p /sdcard/cubegm/saves /sdcard/cubegm/states
say "   device_rootfs 文件数=$(find /arm-root-device -type f | wc -l)"
say "   ld.so=$(test -f /arm-root-device/lib/ld-linux-armhf.so.3 && echo OK || echo 缺)"

# ---- 3) 三桩（对齐 step 11） --------------------------------------------------
say "== [3/6] 三桩"
mkdir -p report/stublib report/drmstublib report/alsastublib
sh tools/build_libkms_stub.sh    report/stublib     >>"$L" 2>&1 || say "   [warn] libkms 桩失败"
sh tools/build_libdrm_stub.sh    report/drmstublib  >>"$L" 2>&1 || say "   [warn] libdrm 桩失败"
sh tools/build_libasound_stub.sh report/alsastublib >>"$L" 2>&1 || say "   [warn] libasound 桩失败"
for f in report/stublib/libkms.so.1 report/drmstublib/libdrm.so.2 report/alsastublib/libasound.so.2; do
  say "   $f = $(test -f "$f" && stat -c%s "$f" || echo 缺)"
done

# ---- 4) 行为采集 + 差分（step 12 同口径，硬门禁） -----------------------------
say "== [4/6] behav_capture + behav_diff"
rm -rf report/qemu
SYSROOT=/arm-root-device CGM_WORK=/sdcard/cubegm CGM_TIMEOUT=30 \
  CGM_LIBKMS_STUB=1 CGM_DRM_STUB=1 CGM_ALSA_STUB=1 CGM_KEY2_SEED=1 CGM_KEY2_HOOK=1 \
  sh tools/ci_qemu_behav.sh \
    build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu \
  > /tmp/r305_behav_stdout.log 2>&1
RC=$?
say "   ci_qemu_behav rc=$RC"
tail -20 /tmp/r305_behav_stdout.log >>"$L"

# ---- 5) 判据数据打包 ----------------------------------------------------------
say "== [5/6] 打包判据"
PKG=/tmp/r305_report.tgz
rm -f "$PKG"
if [ -f report/qemu/behav_diff.txt ]; then
  tar czf "$PKG" -C report/qemu \
    behav_diff.txt behav_factory.json behav_rebuild.json \
    $(ls report/qemu/*.log 2>/dev/null | xargs -r -n1 basename) 2>>"$L"
  say "   pkg=$(wc -c <"$PKG") B"
else
  say "★★ 无 behav_diff.txt ⇒ 判据未产出"
  exit 12
fi

# ---- 6) 自证摘要（供本机核对） -------------------------------------------------
say "== [6/6] 判据行摘要"
{
  sha256sum build/rkgame.rebuilt.elf golden/factory.rkgame.bin
  grep -E "behav_diff|B6|B6A|B6R|退出码" report/qemu/behav_diff.txt | head -20
} >>"$L" 2>&1
cat "$L"
