#!/bin/sh
# ============================================================================
# bootchain.sh —— 在 CNB 云开发环境（或任意 Linux）里，用 qemu **跑通原厂启动链**。
#
# 目标：不靠真机反复插卡，就把
#   U-Boot → kernel → busybox init → rcS → S80icube → icube → driver.so → rkgame
# 整条链跑起来，可**无限重跑**（启动到 rkgame 约 1 秒）。
#
# 用法（在仓库 1to1/ 目录下）：
#     sh tools/bootchain.sh [秒数]        # 默认 60 秒
#
# ★★ 关键结论（都已固化，不要再踩）★★
# 【A】U-Boot 层**跳过**而非绕过：U-Boot 的唯一职责是「把 kernel/rootfs/DTB 搬到内存并按
#     cmdline 交接」，qemu 的 -kernel/-initrd/-append/-dtb 是同职责的等价实现。
#     真机上 U-Boot 直接操作 RK3036 寄存器，在 qemu 上必挂 —— 跳过它不损失保真度。
# 【B】不要用 -nodefaults：ARM virt 的 pl011 依赖 -serial 参数实例化，-nodefaults 会让内核无输出。
# 【C】efi-virtio.rom 缺失 ⇒ 用 `-net none` 绕开（Ubuntu 的 qemu-system-data 并不含它）。
# 【D】cpio 必须用系统 cpio：newc header 110 B（110%4=2），name 的 padding 必须**相对整个流**
#     对齐；手写 padding 差 2 字节 ⇒ 内核报 `broken padding` ⇒ 退回旧式 initrd ⇒ VFS panic。
# 【E】内核不能是原厂的：原厂 zImage 是 RK3036 专用（无 dummy-virt/pl011/arch_timer）。
#     用 Alpine armv7 netboot **vmlinuz-lts**（不是 vmlinuz-virt，后者 404）。
# 【F】★★ 真实设备（不是桩）：
#     · DRM：`-global virtio-mmio.force-legacy=false -device virtio-gpu-device`
#       —— force-legacy 默认 true 会导致 qemu 不加 VIRTIO_F_VERSION_1，
#          内核 virtgpu_kms.c 检查该 feature 失败 ⇒ 驱动不加载（且 release 时空指针）。
#       实测加上后：`[drm] Initialized virtio_gpu`、`/dev/dri/card0`(major 226) 真实出现。
#     · ALSA：内核 `snd-dummy` ⇒ /dev/snd/controlC0 + pcmC0D0p，真实声卡。
#     · 模块来源：`tools/fetch_kmods.sh`（Alpine modloop-lts，与内核同版本同构建）。
#     · 注入：新增 `/etc/init.d/S00cgmmod`（rcS 自动按 S?? 顺序执行，不改任何原厂文件）。
# 【G】CNB 云开发环境**闲置 3–5 分钟即回收** ⇒ 本脚本设计为**一次 ssh 跑完**。
# ============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="${CGM_BOOTCHAIN_DIR:-/tmp/cgm}"
SECS="${1:-60}"
A="$ROOT/bootchain/assets"
NB="https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/armv7/netboot"

mkdir -p "$V"

echo "########## 1) 依赖 ##########"
if ! command -v qemu-system-arm >/dev/null 2>&1 || ! command -v unsquashfs >/dev/null 2>&1; then
  apt-get update -qq > "$V/apt.log" 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    qemu-system-arm squashfs-tools cpio >> "$V/apt.log" 2>&1
  echo "  apt rc=$?"
fi
for c in qemu-system-arm unsquashfs cpio; do printf "  %-18s %s\n" "$c" "$(command -v $c 2>/dev/null || echo 缺)"; done

echo "########## 2) 通用 ARMv7 内核 ##########"
if [ ! -s "$V/vmlinuz" ]; then
  curl -sfL --max-time 150 -o "$V/vmlinuz" "$NB/vmlinuz-lts" || { echo "  ★ 内核下载失败"; exit 11; }
fi
echo "  vmlinuz = $(stat -c%s "$V/vmlinuz") B  [0x24]=$(od -An -tx1 -j36 -N4 "$V/vmlinuz"|tr -d ' ')（期望 18286f01）"

echo "########## 3) 真实内核模块（DRM/声卡/输入）##########"
sh "$ROOT/tools/fetch_kmods.sh" "$V/rootfs/lib/modules" 2>&1 | sed 's/^/  /'

echo "########## 4) 解原厂 rootfs ##########"
if [ ! -d "$V/rootfs/bin" ]; then
  rm -rf "$V/rootfs"
  unsquashfs -q -no-xattrs -d "$V/rootfs" "$A/rootfs.sqsh" > "$V/unsq.log" 2>&1
  echo "  rc=$? 条目=$(find "$V/rootfs" 2>/dev/null | wc -l)"
fi

echo "########## 5) 铺 SD + 新增 S00cgmmod ##########"
mkdir -p "$V/rootfs/proc" "$V/rootfs/sys" "$V/rootfs/tmp" "$V/rootfs/run" \
         "$V/rootfs/dev/pts" "$V/rootfs/dev/shm" \
         "$V/rootfs/mnt/sdcard/cubegm/lib"
cp -a "$A/sdcard/." "$V/rootfs/mnt/sdcard/cubegm/" 2>/dev/null
chmod +x "$V/rootfs/mnt/sdcard/cubegm/icube" "$V/rootfs/mnt/sdcard/cubegm/rkgame" 2>/dev/null
cat > "$V/rootfs/etc/init.d/S00cgmmod" <<'EOS'
#!/bin/sh
# ★ 本项目新增（不是原厂文件，红线遵守）。真机上这些驱动由内核 built-in 提供；
#   本沙箱加载**同版本内核的真实模块**，让 rkgame 面对真实的 DRM/声卡/输入设备。
log() { echo "cmdmod: $*"; }
ld() { modprobe "$1" 2>/dev/null; }
case "$1" in
  start)
    mount -t devtmpfs devtmpfs /dev 2>/dev/null
    mkdir -p /dev/dri /dev/snd /dev/input
    ld virtio_mmio          # qemu 的 virtio-mmio 总线（-device virtio-*-device 挂在这里）
    ld drm                  # DRM 核心
    ld drm_kms_helper
    ld drm_shmem_helper
    ld virtio_gpu           # ★ 真实 DRM 设备驱动（KMS）
    ld snd                  # ALSA 核心
    ld snd_pcm
    ld snd_dummy            # ★ 真实虚拟声卡（/dev/snd/controlC0 + pcmC0D0p）
    ld uinput
    ld joydev
    log "--- /dev/dri ---";  ls -l /dev/dri 2>/dev/null
    log "--- /dev/snd ---";  ls   /dev/snd 2>/dev/null
    log "--- /sys/class/drm ---"; ls /sys/class/drm 2>/dev/null
    ;;
esac
exit 0

EOS
chmod +x "$V/rootfs/etc/init.d/S00cgmmod"
echo "  /sdcard/cubegm 文件数 = $(find "$V/rootfs/mnt/sdcard/cubegm" -type f 2>/dev/null | wc -l)"

echo "########## 6) initramfs（★系统 cpio）##########"
( cd "$V/rootfs" && find . -print0 | cpio --null -o -H newc --quiet 2>/dev/null | gzip -6 > "$V/initramfs.cpio.gz" )
echo "  initramfs.gz = $(stat -c%s "$V/initramfs.cpio.gz") B"

echo "########## 7) 启动（${SECS}s，真实 virtio-gpu + snd-dummy）##########"
set +e
timeout "$SECS" qemu-system-arm -M virt -cpu cortex-a7 -m 2048 \
  -display none -serial stdio -monitor none -no-reboot -net none \
  -global virtio-mmio.force-legacy=false \
  -device virtio-gpu-device \
  -kernel "$V/vmlinuz" -initrd "$V/initramfs.cpio.gz" \
  -append "console=ttyAMA0 rdinit=/sbin/init loglevel=7" > "$V/boot.log" 2>&1
echo "  qemu rc=$?（124=超时未退，正常）  行数=$(wc -l < "$V/boot.log")"

echo "########## 8) 启动链判定 ##########"
hit() { c=$(grep -acE "$2" "$V/boot.log" 2>/dev/null); [ "$c" -gt 0 ] && printf "  ✓ [%2d] %s\n" "$c" "$1" || printf "  · [ 0] %s\n" "$1"; }
hit "内核起来"              "Linux version [0-9]"
hit "initramfs 解包成功"    "Run /sbin/init as init process"
hit "rcS 跑起来"            "Starting logging|Starting network"
hit "S80icube 被拉起"       "Starting icube"
hit "icube dlopen 成功"     "open driver.so sucess"
hit "★ 真实 DRM 设备"       "/dev/dri|Initialized virtio_gpu"
hit "★ rkgame 打开 DRM"     "open drm!"
hit "★ 真实 DRM 调用"       "DRM_IOCTL|drmMode"
hit "★ 真实声卡"            "controlC|pcmC0D0"
hit "rkgame 主循环"         "MemFree|MemTotal"
hit "仍存在失败点"           "failed ret=|cannot find|Segmentation|abort|corruption"
echo
echo "  --- 去重后的关键段 ---"
grep -aE "cmdmod: ---|Starting |open driver.so|video_driver|open drm|rkgame v|DRM_IOCTL|failed ret|Unknown format|corruption|Initialized virtio_gpu|MemTotal" \
  "$V/boot.log" 2>/dev/null | awk '!seen[$0]++' | head -30 | sed 's/^/    /'
echo
echo "  --- 末 15 行 ---"
tail -15 "$V/boot.log" | sed 's/^/    /'
echo "########## DONE ##########"
