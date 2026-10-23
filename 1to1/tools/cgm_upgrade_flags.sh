#!/bin/sh
# ============================================================
# cgm_upgrade_flags.sh —— CGM_UPGRADE 解析规则的**唯一来源**（纪律 69：同一规则禁止写两处）
#
# 为什么抽出（R259）：此前规则只写在 tools/link_audit.sh 内联 case 里，而设备端诊断仪
#   build_diag.sh 需要同一套规则（诊断版也要能开 both 观测 evdev/sram）⇒ 再抄一份就会漂移
#   （本项目已因"抄两份"付过多次代价：zig 解析 4 处、编译口径 2 处）。
#
# 需要外部提供：
#   $CGM_UPGRADE  —— sram | evdev | both | 1(=both) | 空或 0(=全关)
#   $WINROOT      —— Windows 形式的仓库根（link_audit.sh 已算好；build_diag.sh 同）
# 产出：
#   CGM_DEFS  —— " -DCGM_ENABLE_SRAM -DCGM_ENABLE_EVDEV"（可能为空；**前导空格**）
#   CGM_HDR   —— "-I<WINROOT>/src/upgrade"（UP_ANY=1 时；否则空）
#   CGM_UP_ANY—— 0/1（1 = 需要额外编译 src/upgrade/*.c）
#
# 用法：
#   . tools/cgm_upgrade_flags.sh
#   CFLAGS="$CFLAGS$CGM_DEFS $CGM_HDR"      # 追加到既有 CFLAGS（UP_ANY=0 时原样不变）
# ============================================================

CGM_UP_ANY=0
CGM_DEFS=""
CGM_HDR=""

case ",${CGM_UPGRADE:-0}," in
    *,sram,*|*,both,*|*,1,*) CGM_DEFS="$CGM_DEFS -DCGM_ENABLE_SRAM"; CGM_UP_ANY=1 ;; esac
case ",${CGM_UPGRADE:-0}," in
    *,evdev,*|*,both,*|*,1,*) CGM_DEFS="$CGM_DEFS -DCGM_ENABLE_EVDEV"; CGM_UP_ANY=1 ;; esac
if [ "$CGM_UP_ANY" = "1" ]; then
    CGM_HDR="-I${WINROOT}/src/upgrade"
fi
