#!/bin/sh
# ============================================================================
# bootchain.sh —— 在 CNB 云开发环境（或任意 Linux）里，用 qemu **跑通原厂启动链**。
#
# 目标（用户口径）：不靠真机反复插卡，就把
#   U-Boot → kernel → busybox init → rcS → S80icube → icube → driver.so → rkgame
# 整条链跑起来，并可**无限重跑**（一次全链路 ≈ 1 秒，启动到 rkgame 只要 0.8 s）。
#
# 用法（在仓库 1to1/ 目录下）：
#     sh tools/bootchain.sh [秒数]        # 默认 60 秒
#
# ★★ 关键结论（都已在本脚本里固化，不要再踩）★★
# 1) **U-Boot 层跳过、而不是绕开**：U-Boot 的唯一职责是「把 kernel/rootfs/DTB 搬到内存
#    并按 cmdline 交接」，qemu 的 -kernel/-initrd/-append 正是**同一职责的等价实现**。
#    真机上 U-Boot 直接操作 RK3036 寄存器，在 qemu 上必挂 —— 所以跳过它不损失保真度。
# 2) **不要用 -nodefaults**：ARM virt 的串口 (pl011) 依赖 -serial 参数实例化，
#    -nodefaults 会让内核完全无输出，看起来像"内核没启动"，极难排查。
# 3) **efi-virtio.rom 缺失** ⇒ 用 `-net none` 绕开（qemu 的 virtio-net option ROM）。
#    不要为了它去装 qemu-system-data（Ubuntu 的该包并不含 efi-virtio.rom）。
# 4) **cpio 必须用系统 cpio 工具**：newc header 是 110 字节（110 % 4 == 2），
#    name 的 padding 必须**相对整个流**对齐。自己手写 padding 会差 2 字节，
#    内核报 `rootfs image is not initramfs (broken padding)` 并 fallback 成旧式 initrd
#    ⇒ 写入 4 MB 的 /dev/ram0 ⇒ `RAMDISK: incomplete write` ⇒ `VFS: Unable to mount root`。
# 5) **内核不能是原厂的**：原厂 zImage 是 RK3036 专用（无 dummy-virt/pl011/arch_timer 串），
#    在 qemu 上无任何输出。用通用 ARMv7 内核（Alpine armv7 netboot **vmlinuz-lts**，
#    注意不是 vmlinuz-virt）。
# 6) **原厂 SoC 外设**由此仓库既有 shim 补：fake_mem.so 经 /etc/ld.so.preload 注入；
#    libdrm.so.2 / libasound.so.2 桩放进 /sdcard/cubegm/lib（**原厂 S80icube 已把该目录
#    排在 LD_LIBRARY_PATH 最前** ⇒ 零改动生效，不动任何原厂文件）。
# 7) CNB 云开发环境**会被自动回收（闲置约 3–5 分钟）** ⇒ 本脚本设计成**一次 ssh 跑完**，
#    不要"setsid 后台跑 + 反复 ssh 轮询"（轮询间隙就会被回收）。
# ============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="${CGM_BOOTCHAIN_DIR:-/tmp/cgm}"
SECS="${1:-60}"
A="$ROOT/bootchain/assets"
KERNEL_URL="https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/armv7/netboot/vmlinuz-lts"

mkdir -p "$V"

echo "########## 1) 依赖 ##########"
if ! command -v qemu-system-arm >/dev/null 2>&1 || ! command -v unsquashfs >/dev/null 2>&1; then
  apt-get update -qq > "$V/apt.log" 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    qemu-system-arm squashfs-tools cpio >> "$V/apt.log" 2>&1
  echo "  apt rc=$?"
fi
for c in qemu-system-arm unsquashfs cpio gzip; do
  printf "  %-18s %s\n" "$c" "$(command -v $c 2>/dev/null || echo 缺)"
done

echo "########## 2) 通用 ARMv7 内核 ##########"
if [ ! -s "$V/vmlinuz" ]; then
  echo "  取 $KERNEL_URL"
  if timeout 120 curl -sfL -o "$V/vmlinuz" "$KERNEL_URL"; then
    echo "  OK $(stat -c%s "$V/vmlinuz") B  [0x24]=$(od -An -tx1 -j36 -N4 "$V/vmlinuz"|tr -d ' ')  (期望 18286f01)"
  else
    echo "  ★ 下载失败"; exit 11
  fi
fi

echo "########## 3) 解原厂 rootfs（squashfs）##########"
if [ ! -d "$V/rootfs/bin" ]; then
  rm -rf "$V/rootfs"
  unsquashfs -q -no-xattrs -d "$V/rootfs" "$A/rootfs.sqsh" > "$V/unsq.log" 2>&1
  echo "  rc=$?  条目=$(find "$V/rootfs" 2>/dev/null | wc -l)（dev/console 建不出是正常的，devtmpfs 会补）"
fi

echo "########## 4) 铺 SD（真实挂载点 /sdcard -> mnt/sdcard）##########"
mkdir -p "$V/rootfs/proc" "$V/rootfs/sys" "$V/rootfs/tmp" "$V/rootfs/run" \
         "$V/rootfs/dev/pts" "$V/rootfs/dev/shm" \
         "$V/rootfs/mnt/sdcard/cubegm/lib"
cp -a "$A/sdcard/." "$V/rootfs/mnt/sdcard/cubegm/" 2>/dev/null
chmod +x "$V/rootfs/mnt/sdcard/cubegm/icube" "$V/rootfs/mnt/sdcard/cubegm/rkgame" 2>/dev/null

# 桩（若已构建）：drm / alsa → /sdcard/cubegm/lib（原厂已排最前）
if [ -d "$ROOT/build/bootchain/lib" ]; then
  cp -a "$ROOT/build/bootchain/lib/." "$V/rootfs/mnt/sdcard/cubegm/lib/" 2>/dev/null
fi
# shim（fake_mem）→ /etc/ld.so.preload（glibc 系统级；rcS 各脚本是子进程，export 传不过去）
if [ -f "$V/rootfs/mnt/sdcard/cubegm/lib/guest_shim.so" ]; then
  printf '/mnt/sdcard/cubegm/lib/guest_shim.so\n' > "$V/rootfs/etc/ld.so.preload"
fi
echo "  /sdcard/cubegm 文件数 = $(find "$V/rootfs/mnt/sdcard/cubegm" -type f 2>/dev/null | wc -l)"
echo "  lib/: $(ls "$V/rootfs/mnt/sdcard/cubegm/lib" 2>/dev/null | tr '\n' ' ')"
echo "  ld.so.preload: $(cat "$V/rootfs/etc/ld.so.preload" 2>/dev/null || echo '(无)')"

echo "########## 5) 组 initramfs（★必须用系统 cpio）##########"
( cd "$V/rootfs" && find . -print0 | cpio --null -o -H newc --quiet 2>/dev/null | gzip -9 > "$V/initramfs.cpio.gz" )
echo "  initramfs.gz = $(stat -c%s "$V/initramfs.cpio.gz") B"

echo "########## 6) 启动（${SECS}s）##########"
set +e
timeout "$SECS" qemu-system-arm -M virt -cpu cortex-a7 -m 1024 \
  -display none -serial stdio -monitor none -no-reboot -net none \
  -kernel "$V/vmlinuz" -initrd "$V/initramfs.cpio.gz" \
  -append "console=ttyAMA0 rdinit=/sbin/init loglevel=7" > "$V/boot.log" 2>&1
echo "  qemu rc=$?（124=超时未退，正常）  行数=$(wc -l < "$V/boot.log")"

echo "########## 7) 启动链判定 ##########"
hit() { c=$(grep -acE "$2" "$V/boot.log" 2>/dev/null); [ "$c" -gt 0 ] && printf "  ✓ [%2d] %s\n" "$c" "$1" || printf "  · [ 0] %s\n" "$1"; }
hit "内核起来"            "Linux version [0-9]"
hit "initramfs 解包成功"  "Unpacking initramfs|Run /sbin/init"
hit "busybox init 运行"   "Run /sbin/init as init process"
hit "rcS 跑起来"          "Starting logging|Starting network"
hit "S80icube 被拉起"     "Starting icube"
hit "icube dlopen 成功"   "open driver.so sucess"
hit "rkgame 在跑"         "rkgame v[0-9]"
hit "shim 生效"           "\[shim\]"
hit "崩溃/异常"           "SIGSEGV|SIGBUS|Segmentation|assertion|Aborted|真崩溃"
echo
echo "  --- 去重后的 rkgame/shims 相关行（前 40）---"
grep -aE "open driver.so|video_driver|open drm|rkgame v|config.xml|MemTotal|\[shim\]|Starting icube" "$V/boot.log" 2>/dev/null | awk '!seen[$0]++' | head -40 | sed 's/^/    /'
echo "  --- 末 15 行 ---"
tail -15 "$V/boot.log" | sed 's/^/    /'
echo "########## DONE ##########"
