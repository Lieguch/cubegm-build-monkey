#!/bin/sh
# strict_exp.sh —— 严格设备模式的双向判决实验（在 CNB 工作区里跑）
#
# 目的（回答"沙箱能不能替代真机判定"）：
#   A. 修复前产物 build/pre.elf 在 CGM_MMIO_STRICT=1 下**必须**出现 MMIO-STRICT VIOLATION
#      ⇒ 证明本装置真的复现了真机的总线约束（真机现象：SIGBUS @ sfc_init+0x6c）
#   B. 当前交付产物 build/cur.elf 在同样模式下**必须不出现** violation
#      ⇒ 证明宽度修复在沙箱里可验证
#   两条同时成立 = 这一"类"可以在本地判定完毕，不必再消耗真机往返。
set -u
cd /workspace/1to1 || exit 9
export SYSROOT="$PWD/golden/device_rootfs_min"
export CGM_MMIO_STRICT=1
export CGM_MMIO_TRACE=1
export CGM_TIMEOUT=20
# ★ 工作区没有 armhf 交叉编译器 ⇒ 用开发机预编译好的 shim（zig -target ...2.29）
export CGM_SHIM_SO="$PWD/build/shim_strict.so"
# ★ 过 driver.so 的图形/音频硬件后端：沙箱无真 DRM/ALSA ⇒ driver.so 必崩在 gr_init
#   （现场实测 pc=driver.so+0x3ca8 lr=libc+0x41e44，r3=NULL）。必须启用桩才能走到 SFC。
export CGM_DRM_STUB=1
export CGM_ALSA_STUB=1
mkdir -p report/_strict

run_arm() {   # $1 = 标签  $2 = 产物
    lab="$1"; elf="$2"
    echo "############ ARM $lab : $elf ############"
    sh tools/ci_qemu_behav.sh "$elf" golden/factory.rkgame.bin "report/_strict/$lab" \
        > "report/_strict/$lab.log" 2>&1
    echo "  脚本 rc=$?"
    echo "  --- MMIO-STRICT 命中 ---"
    grep -rl "MMIO-STRICT VIOLATION" "report/_strict/$lab" 2>/dev/null | head -20
    n=$(grep -rh "MMIO-STRICT VIOLATION" "report/_strict/$lab" 2>/dev/null | wc -l)
    echo "  violation 行数 = $n"
    grep -rh "MMIO-STRICT VIOLATION" "report/_strict/$lab" 2>/dev/null | head -5
    echo "  --- 是否真的走到 SFC（shim 是否生效）---"
    grep -rh "SFC 设备仿真已装配" "report/_strict/$lab" 2>/dev/null | head -2
    echo "  MMIO trace 行数 = $(grep -rh 'MMIO seq' "report/_strict/$lab" 2>/dev/null | wc -l)"
    echo "  --- 崩溃/信号 ---"
    grep -rhiE "signal=|SIGBUS|SIGSEGV|uncaught" "report/_strict/$lab" 2>/dev/null | head -8
    echo
}

run_arm pre build/pre.elf
run_arm cur build/cur.elf
echo "############ 汇总 ############"
for l in pre cur; do
    n=$(grep -rh "MMIO-STRICT VIOLATION" "report/_strict/$l" 2>/dev/null | wc -l)
    echo "$l : violation=$n"
done
echo DONE
