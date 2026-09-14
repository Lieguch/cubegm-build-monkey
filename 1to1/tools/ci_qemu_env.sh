#!/bin/sh
# ============================================================
# ci_qemu_env.sh — 在 CI(Linux) 内建立 ARM32 hard-float 运行环境（qemu-user）
#
# 依据：本仓库已有先在案例（cnb-rkgame-final 的 GitHub workflow `Setup qemu` +
#       `.cnb.yml` 的 `test-emu` 阶段）：ubuntu-22.04 + apt qemu-user-static +
#       一个 armhf sysroot，用 `qemu-arm-static -L <sysroot>` 跑 ARM32 二进制。
#
# ★ 关键选型：sysroot 必须与被测二进制的 glibc 要求匹配
#   · 重建产物由 CI 的 arm-linux-gnueabihf-gcc(Ubuntu 22.04, glibc 2.35) 链接
#     ⇒ sysroot 必须是 **Ubuntu 22.04 armhf**（同版本 glibc）
#   · 工厂 rkgame 只要求 glibc ≥2.7 + libstdc++ ⇒ 高版本完全向下兼容
#   已验证先例用的是 Debian 9(glibc 2.24) sysroot，那是因为它重建的目标就是旧 glibc；
#   若此处沿用，重建产物会直接 `version GLIBC_2.35 not found` 起不来。
#
# 用法: sudo sh tools/ci_qemu_env.sh [sysroot]      （默认 /arm-root）
# ============================================================
set -eu

SYSROOT="${1:-/arm-root}"
SUITE=jammy
MIRROR=http://ports.ubuntu.com/ubuntu-ports
# 运行时所需：libc / libgcc / libstdc++ / zlib / 设备侧 libdrm+alsa（工厂二进制 NEEDED）
PKGS="libc6 libgcc-s1 libstdc++6 zlib1g libdrm2 libasound2 libcrypt1"

echo "== 1/3 安装 qemu-user-static =="
if ! command -v qemu-arm-static >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y --no-install-recommends qemu-user-static python3 ca-certificates
fi
qemu-arm-static --version | head -2

echo "== 2/3 准备 armhf sysroot（$SUITE） =="
mkdir -p "$SYSROOT"
if [ -e "$SYSROOT/usr/lib/arm-linux-gnueabihf/libc.so.6" ] || \
   [ -e "$SYSROOT/lib/arm-linux-gnueabihf/libc.so.6" ]; then
    echo "  sysroot 已存在，跳过下载"
else
    echo "deb [arch=armhf] $MIRROR $SUITE main universe" > /etc/apt/sources.list.d/armhf.list
    dpkg --add-architecture armhf
    apt-get update -qq
    TMP="$(mktemp -d)"
    ( cd "$TMP"
      for p in $PKGS; do
          if apt-get download "${p}:armhf" >/dev/null 2>&1; then
              echo "   [ok]   $p:armhf"
          else
              echo "   [warn] 无法下载 $p:armhf"
          fi
      done
      n=0
      for d in *.deb; do
          [ -f "$d" ] || continue
          dpkg-deb -x "$d" "$SYSROOT" && n=$((n + 1))
      done
      echo "   解包 $n 个 deb" )
    rm -rf "$TMP"
fi

echo "== 3/3 校验运行时元件 =="
for f in \
  "$SYSROOT/lib/ld-linux-armhf.so.3" \
  "$SYSROOT/lib/arm-linux-gnueabihf/ld-linux-armhf.so.3" \
  "$SYSROOT/usr/lib/arm-linux-gnueabihf/libc.so.6" \
  "$SYSROOT/lib/arm-linux-gnueabihf/libc.so.6" \
  "$SYSROOT/usr/lib/arm-linux-gnueabihf/libstdc++.so.6" \
  "$SYSROOT/usr/lib/arm-linux-gnueabihf/libz.so.1" ; do
    if [ -e "$f" ]; then echo "   [ok]   $f"; else echo "   [miss] $f"; fi
done
echo "   --- /usr/lib/arm-linux-gnueabihf 摘要 ---"
ls "$SYSROOT/usr/lib/arm-linux-gnueabihf/" 2>/dev/null | head -20 || true
echo "sysroot 大小: $(du -sh "$SYSROOT" 2>/dev/null | cut -f1)"
echo "== qemu 环境就绪 =="
