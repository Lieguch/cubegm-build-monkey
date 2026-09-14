#!/bin/sh
# ============================================================
# ci_qemu_env.sh — 在 CI(Linux) 内建立 ARM32 hard-float 运行环境（qemu-user）
#
# 依据：本仓库已有先例（cnb-rkgame-final 的 GitHub workflow `Setup qemu` +
#       `.cnb.yml` 的 `test-emu` 阶段）：ubuntu-22.04 + apt qemu-user-static +
#       一个 armhf sysroot，用 `qemu-arm-static -L <sysroot>` 跑 ARM32 二进制。
#
# ★ 关键选型 1：sysroot 必须与被测二进制的 glibc 要求匹配
#   · 重建产物由 CI 的 arm-linux-gnueabihf-gcc(Ubuntu 22.04, glibc 2.35) 链接
#     ⇒ sysroot 必须是 **Ubuntu 22.04 armhf**（同版本 glibc）
#   · 工厂 rkgame 只要求 glibc ≥2.7 + libstdc++ ⇒ 高版本向下兼容
#   先例用 Debian 9(glibc 2.24) sysroot，是因为它重建的目标就是旧 glibc；沿用会让
#   重建产物直接 `version GLIBC_2.35 not found` 起不来。
#
# ★ 关键选型 2：**sysroot 绝不用 apt 取**
#   实测踩坑：`dpkg --add-architecture armhf` 之后任何全局 `apt-get update` 都会让 apt
#   去 `security.ubuntu.com` 拉 `binary-armhf/Packages` —— Ubuntu 的 security 源**没有 armhf**，
#   于是 404、`apt-get update` 返回 100、`set -e` 直接中断：
#       E: Failed to fetch https://security.ubuntu.com/ubuntu/dists/jammy/main/binary-armhf/Packages  404
#   ⇒ 改用 tools/fetch_armhf_sysroot.py：只读 ports.ubuntu.com 的 Packages 索引、
#     解析 Filename、直接下载 .deb + `dpkg-deb -x`。**不碰任何 apt 状态**。
#
# 用法: sudo sh tools/ci_qemu_env.sh [sysroot]      （默认 /arm-root）
# ============================================================
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SYSROOT="${1:-/arm-root}"

echo "== 1/3 安装 qemu-user-static =="
if ! command -v qemu-arm-static >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y --no-install-recommends qemu-user-static python3 ca-certificates
fi
qemu-arm-static --version | head -2

echo "== 2/3 准备 armhf sysroot（直接抓 .deb，不走 apt）=="
python3 "$ROOT/tools/fetch_armhf_sysroot.py" "$SYSROOT" jammy

echo "== 3/3 校验运行时元件 =="
# ★ 布局不可假设：Ubuntu 22.04 armhf 上 glibc/zlib 落在 `lib/arm-linux-gnueabihf/`，
#   而 libstdc++/libdrm/libasound 落在 `usr/lib/arm-linux-gnueabihf/`（实测）。
#   故作**动态查找**，避免把"布局不同"误判成"缺失"。
missing=0
check_lib() {
    hit=$(find "$SYSROOT/lib" "$SYSROOT/usr/lib" -name "$1" 2>/dev/null | head -1)
    if [ -n "$hit" ]; then
        echo "   [ok]   $1  ->  ${hit#$SYSROOT}"
    else
        echo "   [miss] $1"
        missing=$((missing + 1))
    fi
}
for f in ld-linux-armhf.so.3 libc.so.6 libm.so.6 libz.so.1 libstdc++.so.6 \
         libgcc_s.so.1 libdl.so.2 libpthread.so.0 libdrm.so.2 libasound.so.2 ; do
    check_lib "$f"
done
echo "   --- lib/arm-linux-gnueabihf ---"
ls "$SYSROOT/lib/arm-linux-gnueabihf/" 2>/dev/null | head -12 || true
echo "   --- usr/lib/arm-linux-gnueabihf ---"
ls "$SYSROOT/usr/lib/arm-linux-gnueabihf/" 2>/dev/null | head -12 || true
echo "sysroot 大小: $(du -sh "$SYSROOT" 2>/dev/null | cut -f1)"
if [ "$missing" != "0" ]; then
    echo "FATAL 运行时元件缺失 $missing 项"
    exit 1
fi
echo "== qemu 环境就绪（LD_LIBRARY_PATH 需同时含 lib/ 与 usr/lib/ 两个 gnueabihf 目录）=="
