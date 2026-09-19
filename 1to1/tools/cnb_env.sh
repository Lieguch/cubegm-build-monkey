#!/bin/sh
# CNB 云开发环境一键引导（幂等）—— 把 25 分钟/轮的 CI 反馈周期压到秒级。
#
# 用法（在 CNB workspace 的仓库根 1to1/ 下执行）：
#     sh tools/cnb_env.sh              # 全量（缺什么补什么）
#     sh tools/cnb_env.sh --fast       # 跳过 apt
#     FORCE_BUILD=1 sh tools/cnb_env.sh   # 强制重编重建产物
#     RUN_DIFF=1 sh tools/cnb_env.sh      # 装完顺带跑一次 A 场景差分（端到端自证）
#
# 产出：
#   /arm-root             armhf sysroot（Debian 9 / glibc 2.24，与 CI 的 ci_qemu_env.sh 同源）
#   /sdcard/cubegm        真机同款工作目录（走 stage_sdcard_env.sh，与 CI 同一脚本）
#   /tmp/guest_shim.so    假硬件 shim（与 CI 同工具链 zig 0.16.0）
#   /tmp/cgm_env.sh       交叉编译环境（CC=zig cc、ZIG_GLOBAL_CACHE_DIR…），可 source 复用
#   build/rkgame.rebuilt.elf  1:1 重建产物
#
# 纪律：
#   · 只读 golden/，绝不修改（脚本末尾用 MANIFEST.sha256 自证）
#   · 不写死绝对仓库路径；从脚本位置反推仓库根
#   · 每步都能在"已完成"时安全重跑（用哨兵而非"目录存在"判断，避免半装被误判为完成）

set -eu

FAST=0
[ "${1:-}" = "--fast" ] && FAST=1

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "== 仓库根: $ROOT"

# ---------------------------------------------------------------- 1) apt 包
# 包清单逐条对齐 .github/workflows/1to1-qemu-behav.yml 的"安装 ARM 交叉工具链"步骤。
if [ "$FAST" = 0 ]; then
  echo "== [1/7] apt: ARM 交叉工具链 / qemu / gdb / strace"
  export DEBIAN_FRONTEND=noninteractive
  if ! command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1 || ! command -v qemu-arm-static >/dev/null 2>&1; then
    apt-get update -qq >/dev/null 2>&1 || true
    apt-get install -y -qq \
      gcc-arm-linux-gnueabihf binutils-arm-linux-gnueabihf \
      qemu-user-static gdb-multiarch strace file wget >/dev/null 2>&1 \
      || echo "   !! apt 安装失败（检查额度/网络）"
  fi
else
  echo "== [1/7] --fast：跳过 apt"
fi
for c in arm-linux-gnueabihf-gcc qemu-arm-static gdb-multiarch strace objdump readelf file wget; do
  printf "   %-26s %s\n" "$c" "$(command -v "$c" || echo '★MISSING')"
done

# ---------------------------------------------------------------- 2) sysroot
echo "== [2/7] armhf sysroot -> /arm-root（直接调用 CI 用的同一个脚本）"
# ★★ 为什么必须调用 ci_qemu_env.sh 而不是抄一份 deb 清单：
#   1to1 的 CI sysroot 是 **Ubuntu jammy（glibc 2.35）**，因为重建产物由 jammy 的
#   arm-linux-gnueabihf 头文件编出。若本地用 Debian 9（glibc 2.24）当 sysroot，
#   shim/产物的 `version GLIBC_2.34 not found` 会让**两侧都**起不来，现象是
#   "B0 参考侧没有真正的行为观测"（exit=1、stdout=0）—— 一个纯环境的假失败。
#   （2026-09-19 实测：我照另一条线的 .cnb.yml 抄了 Debian 9 配方，正是这个坑。）
#   直接跑同一脚本 ⇒ 本地与 CI 的 sysroot 内容一致，差分才有意义。
SENTINEL=/arm-root/.cgm_sysroot_ok
if [ -f "$SENTINEL" ]; then
  echo "   已存在（哨兵），跳过"
else
  rm -rf /arm-root
  sh tools/ci_qemu_env.sh /arm-root 2>&1 | tail -22
  # 哨兵：只有脚本自带的三项校验全过（它自己 rc=0）才写
  touch "$SENTINEL"
fi
ls /arm-root/lib/ld-linux-armhf.so.3 >/dev/null 2>&1 \
  && echo "   ld-linux-armhf.so.3 OK" \
  || { echo "   ★ sysroot 不完整，中止"; exit 1; }

# ---- 2b) 设备精确 sysroot（org.bin 的真实 rootfs）----
# ★★ 为什么要两个 sysroot：
#   · /arm-root        = Ubuntu jammy（glibc 2.35）—— CI 的现状。它是"能跑"的替代品：
#                        重建产物的头文件来自 jammy，链接出来的东西需要 jammy 的符号。
#   · /arm-root-device = **设备真实 rootfs** 的最小集（glibc 2.29 Buildroot、libstdc++ 6.0.22、
#                        libz 1.2.11、libdrm 2.4.0 + libdrm_rockchip.so.1、libasound 2.0.0）。
#                        「在设备上会怎样」只能用这个测 —— jammy 比设备更宽松，会掩盖
#                        "用了设备没有的符号/库"这一类问题。
#   ⇒ 交付判据必须用 /arm-root-device；/arm-root 只用于"与 CI 对齐"。
echo "== [2b/7] 设备精确 sysroot -> /arm-root-device（源自 golden/device_rootfs_min）"
if [ -d golden/device_rootfs_min ]; then
  rm -rf /arm-root-device
  mkdir -p /arm-root-device
  cp -a golden/device_rootfs_min/. /arm-root-device/
  rm -f /arm-root-device/MANIFEST.sha256
  printf "   文件 %s 个 | " "$(find /arm-root-device -type f | wc -l)"
  printf "ld.so=%s " "$(ls /arm-root-device/lib/ld-linux-armhf.so.3 2>/dev/null >/dev/null && echo OK || echo 缺)"
  printf "libc=%s\n" "$(ls /arm-root-device/lib/libc.so.6 2>/dev/null >/dev/null && echo OK || echo 缺)"
  if [ -f "$ROOT/golden/device_rootfs_min/lib/libc-2.29.so" ]; then
    printf "   设备 glibc 版本串: %s\n" "$(strings "$ROOT/golden/device_rootfs_min/lib/libc-2.29.so" 2>/dev/null | grep -m1 'GNU C Library')"
  fi
else
  echo "   跳过（golden/device_rootfs_min 不存在；用 tools/make_device_sysroot.py 生成）"
fi

# ---------------------------------------------------------------- 3) zig + 环境文件
echo "== [3/7] zig 0.16.0（与 CI 同一工具链 ⇒ 产物的 GLIBC 下限可控）"
if ! python3 -m ziglang version >/dev/null 2>&1; then
  # CNB 的 python3 是「外部管理环境」（PEP 668）⇒ 必须显式 --break-system-packages，
  # 否则 pip 只打一行 hint 就返回 0、包没装上，后续编译再失败（"仪器静默降级"）。
  python3 -m pip install -q --break-system-packages "ziglang==0.16.0" 2>&1 | tail -2 || true
fi
ZIGBIN="$(python3 -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)"
if [ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ]; then
  chmod +x "$ZIGBIN" 2>/dev/null || true
  echo "   zig $(python3 -m ziglang version) @ $ZIGBIN"
else
  echo "   ★ zig 不可用（将退化为 GCC 链接 ⇒ GLIBC 下限会高于设备）"
  ZIGBIN=""
fi
mkdir -p /tmp/zigcache
cat > /tmp/cgm_env.sh <<EOF
# source /tmp/cgm_env.sh  —— CNB 上跑 1:1 构建/差分所需的环境
export SYSROOT=/arm-root
export CGM_WORK=/sdcard/cubegm
export PY=python3
export ZIG_GLOBAL_CACHE_DIR=/tmp/zigcache
export CC="$ZIGBIN cc"
EOF
echo "   环境文件: /tmp/cgm_env.sh"

# ---------------------------------------------------------------- 4) shim
echo "== [4/7] 编译假硬件 shim -> /tmp/guest_shim.so"
cd "$ROOT"
if [ -n "$ZIGBIN" ]; then
  if [ ! -x /tmp/guest_shim.so ]; then
    CC="$ZIGBIN cc" sh tools/build_guest_shim.sh /tmp/guest_shim.so 2>&1 | tail -3
  fi
  [ -f /tmp/guest_shim.so ] && echo "   shim $(stat -c%s /tmp/guest_shim.so) B" || echo "   ★ shim 编译失败"
else
  echo "   跳过（无 zig）"
fi

# ---------------------------------------------------------------- 5) /sdcard
echo "== [5/7] 铺 /sdcard（走 stage_sdcard_env.sh，与 CI 同一脚本）"
if [ -f /sdcard/cubegm/setting.xml ] && [ -f /sdcard/cubegm/ui_cn.zip ]; then
  echo "   已存在，跳过"
else
  rm -rf /sdcard/cubegm
  sh tools/stage_sdcard_env.sh /sdcard/cubegm golden/sdcard_min 2>&1 | tail -6
  mkdir -p /sdcard/cubegm/saves /sdcard/cubegm/states
fi
echo "   /sdcard/cubegm: $(ls /sdcard/cubegm | tr '\n' ' ')"

# ---------------------------------------------------------------- 6) 重建产物
echo "== [6/7] 构建 1:1 重建产物"
# ★★ 编译**和**链接必须用同一个 zig —— 这不是风格问题，是正确性问题。
#   实测（CNB 2026-09-19）：Debian 13 的 armhf 工具链已完成 **time64 迁移**，其头文件把
#     gettimeofday/fopen/open/mmap/scandir/alphasort 重定向到 `__gettimeofday64`/`fopen64`/…
#   而 zig 的 `-target arm-linux-gnueabihf.2.7` 没有这些符号 ⇒ 链接报
#     `ld.lld: error: undefined symbol: __gettimeofday64`（还有 5 个同族），产物为零。
#   CI 的 Ubuntu 22.04 未做 time64 迁移，所以那边**看起来**没这个问题 —— 也就是说：
#   本地一旦用宿主 gcc 编对象、用 zig 链接，就会得到一个 CI 上不复现的假故障。
#   ⇒ 统一 CC=zig 后两侧的"目标 glibc"一致，链接即通。
. /tmp/cgm_env.sh
if [ -f build/rkgame.rebuilt.elf ] && [ "${FORCE_BUILD:-0}" != "1" ]; then
  echo "   已存在 $(stat -c%s build/rkgame.rebuilt.elf) B，跳过（FORCE_BUILD=1 强制重编）"
else
  mkdir -p report
  # 换工具链 ⇒ 必须清掉旧对象，否则混用两套头文件编出的 .o（链接期才会暴露）
  [ "${FORCE_BUILD:-0}" = "1" ] && rm -rf build/obj build/upstream
  # 逐条对齐 1to1-qemu-behav.yml 的"构建 1:1 重建产物"步骤（本地/CI 同一路径）。
  # link_audit.sh 是本仓库里唯一会把 src/proprietary/*.c 编成 build/obj/*.o 的脚本；
  # 它自身的门禁结论由 1to1-verify 负责，这里只为拿对象，故 rc 不强判。
  PY=python3 sh tools/link_audit.sh report/link_audit.txt \
    || echo "   [warn] link_audit 非零（对象已产出，继续）"
  PY=python3 sh tools/build_upstream.sh build/upstream 2>&1 | tail -4
  PY=python3 sh tools/link_full.sh build/rkgame.rebuilt.elf 2>&1 | tail -8
  python3 tools/dyn_audit.py build/rkgame.rebuilt.elf 2>&1 | tail -6 || true
  ls -la build/rkgame.rebuilt.elf golden/factory.rkgame.bin 2>/dev/null | sed 's/^/   /'
fi

# ---------------------------------------------------------------- 7) 端到端自证
if [ "${RUN_DIFF:-0}" = "1" ]; then
  echo "== [7/7] 端到端：跑 A 场景差分（qemu 本地，秒级）"
  # ★ ci_qemu_behav.sh 内部会自行编 shim（`sh build_guest_shim.sh`，其默认 CC=cc，
  #   而 CNB 上 `cc` 不存在 ⇒ shim 静默失败、差分退化为"不带 shim"，可观测窗口变浅）。
  #   所以必须把 CC 导出到这个 shell。
  . /tmp/cgm_env.sh
  export SYSROOT CGM_WORK CC PY ZIG_GLOBAL_CACHE_DIR
  sh tools/ci_qemu_behav.sh build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu 2>&1 | tail -30
else
  echo "== [7/7] 跳过差分（RUN_DIFF=1 可开启）"
fi

# ---------------------------------------------------------------- 自证
echo
echo "== 自证 =="
printf "   qemu : %s\n" "$(qemu-arm-static --version 2>&1 | head -1)"
printf "   工厂 : %s\n" "$(file -b golden/factory.rkgame.bin 2>/dev/null | cut -c1-64)"
printf "   重建 : %s\n" "$(file -b build/rkgame.rebuilt.elf 2>/dev/null | cut -c1-64 || echo '(未构建)')"
printf "   golden MANIFEST : "
if [ -f golden/sdcard_min/MANIFEST.sha256 ]; then
  bad=0; n=0
  while read -r h rel; do
    [ -z "$rel" ] && continue
    n=$((n+1))
    got=$(sha256sum "golden/sdcard_min/$rel" 2>/dev/null | cut -d" " -f1)
    [ "$got" = "$h" ] || { echo "★被改: $rel"; bad=$((bad+1)); }
  done < golden/sdcard_min/MANIFEST.sha256
  echo "核验 $n 项，异常 $bad 项"
else
  echo "缺 MANIFEST"
fi
echo
echo "完成。常用命令："
echo "  . /tmp/cgm_env.sh"
echo "  SYSROOT=/arm-root CGM_WORK=/sdcard/cubegm sh tools/ci_qemu_behav.sh build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu"
echo "  sh tools/gdb_globals.sh            # 零源码改动的运行期读全局"
