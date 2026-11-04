#!/bin/sh
# fetch_kmods.sh —— 取「同版本内核」的真实模块集（DRM/声卡/输入），供沙箱使用。
#
# 为什么需要：真机 rootfs 里**没有** /lib/modules（原厂内核把这些驱动 built-in）。
# 本沙箱用 **与内核同版本同构建** 的 Alpine lts 模块，让 rkgame 面对的是
# **真实的内核驱动**（virtio-gpu / snd-dummy / joydev…），而不是被伪造成功。
#
# 用法（在 bootchain.sh 内部调用）: sh tools/fetch_kmods.sh <destdir>
set -u
DEST="${1:?usage: fetch_kmods.sh <destdir>}"
# ★★ R308 根修：内核版本**不得硬编码**。
#   事故：原写 `KV="6.12.110-0-lts"`，而 Alpine v3.21 netboot 在 2026-10-21 升级到
#   6.12.114-0-lts（官方目录 `config-6.12.114-0-lts` / `modloop-lts` 实测）。
#   硬编码的后果有两层：① `find -name "$KV"` 找不到 ⇒ exit 13，启动链根本起不来；
#   ② 就算手工建了空目录，guest 内核 `uname -r` = 6.12.114-0-lts，modprobe 按
#   `/lib/modules/$(uname -r)` 找模块 ⇒ 全落空 ⇒ bootchain.sh 的「真实 DRM/声卡」判据
#   永远为 0 ⇒ **启动链日志不完美且原因隐蔽**。
#   ⇒ 单一真源：模块目录名 = modloop 解出的 `*-lts` 目录 basename，与 vmlinuz-lts 同构建。
NB="https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/armv7/netboot"
mkdir -p "$DEST"
# 缓存命中判定：DEST 下已有任一 `*-lts` 且含 .ko ⇒ 直接复用（KV 从目录名反推）
EXIST=$(find "$DEST" -maxdepth 1 -type d -name '*-lts' 2>/dev/null | head -1)
if [ -n "$EXIST" ] && [ "$(find "$EXIST" -name '*.ko' 2>/dev/null | wc -l)" -gt 0 ]; then
  KV=$(basename "$EXIST")
  echo "  复用已缓存模块 $KV（$(find "$EXIST" -name '*.ko' | wc -l) 个 .ko）"
else
  echo "  下载 modloop-lts（Alpine 当前 LTS 内核模块全集）..."
  curl -sfL --max-time 300 -o /tmp/modloop-lts "$NB/modloop-lts" || { echo "  ★ modloop 下载失败"; exit 11; }
  echo "  modloop $(stat -c%s /tmp/modloop-lts) B"
  rm -rf /tmp/ml; mkdir -p /tmp/ml
  unsquashfs -q -no-xattrs -d /tmp/ml /tmp/modloop-lts >/dev/null 2>&1 || { echo "  ★ 解包失败"; exit 12; }
  SRC=$(find /tmp/ml -maxdepth 4 -type d -name '*-lts' 2>/dev/null | head -1)
  [ -n "$SRC" ] || { echo "  ★ modloop 里找不到 *-lts 模块目录"; exit 13; }
  KV=$(basename "$SRC")
  echo "  实测内核模块版本 = $KV（由 modloop 机械探测，非硬编码）"
  cp -a "$SRC" "$DEST/$KV"
  # modloop 的模块目录名是 modules/<ver>，Alpine 里 /lib/modules 指向它
  echo "  已放入 $DEST/$KV（$(find "$DEST/$KV" -name '*.ko' | wc -l) 个 .ko）"
fi
ls "$DEST/$KV" | head -6 | sed 's/^/    /'
