#!/bin/sh
# ============================================================
# b6_struct_gate.sh —— B6 结构判据机械门禁（R190）
#
# 为什么换判据（R189/R190 实测定案）：
#   B6 原判据是「frame#1 hash 非全零」= 想拿到真实 UI 像素哈希。
#   但 R188/R189/R190 三轮铁证证明：driver 只用 `drmModeSetCrtc(fb=1)` 呈现，
#   **从不**调 SetPlane/PageFlip、**从不**发 MAP_SHARED mmap、画布走不经 shim 的私有路径
#   ⇒ 像素写在 driver 私有画布里，桩**结构上不可能**读到。
#   ⇒ "hash 非零"在 qemu-user 沙箱内**永不可能满足**，继续追它就是浪费算力。
#
# 本门禁判的是**桩是否正确复刻了 DRM 调用语义**（这才是沙箱内可证的部分）：
#   逐项 grep `_b6_adjudge.sh` 同一次运行的 stderr，任一项缺失/不符即 exit 1。
#
# ★ 纪律：这些判据证明「调用语义正确」，**不**证明「画面渲染正确」。
#   报告里必须分开陈述（见 PROGRESS R190 三.1 的注意事项）。
#
# 用法: sh tools/b6_struct_gate.sh          （需先跑过 _b6_adjudge.sh）
#        sh tools/b6_struct_gate.sh <log>   （指定 /tmp/b6_stderr.txt 的副本）
# ============================================================
set -u

LOG="${1:-/tmp/b6_stderr.txt}"
[ -f "$LOG" ] || { echo "!! 缺日志 $LOG（先跑 tools/_b6_adjudge.sh）" >&2; exit 9; }

FAIL=0
pass() { echo "  ✅ $1"; }
fail() { echo "  ❌ $1" >&2; FAIL=1; }

echo "=== B6 结构判据门禁（R190） 日志=$LOG ==="

# ---- 1) dumb buffer 实体数 = 4（RG16×3 + AR24×1）----
n_dumb=$(grep -a -c 'dumb#' "$LOG" || true)
case "$n_dumb" in ''|*[!0-9]*) n_dumb=0 ;; esac
if [ "$n_dumb" = "4" ]; then pass "dumb# 实体数 = 4"; else fail "dumb# 实体数 = $n_dumb（期望 4）"; fi

# ---- 2) bpp 序列 16/16/16/32 ----
b1=$(grep -a 'dumb#1 ' "$LOG" | grep -o 'bpp=00000010' | head -1)
b2=$(grep -a 'dumb#2 ' "$LOG" | grep -o 'bpp=00000010' | head -1)
b3=$(grep -a 'dumb#3 ' "$LOG" | grep -o 'bpp=00000010' | head -1)
b4=$(grep -a 'dumb#4 ' "$LOG" | grep -o 'bpp=00000020' | head -1)
if [ -n "$b1" ] && [ -n "$b2" ] && [ -n "$b3" ] && [ -n "$b4" ]; then
    pass "bpp 序列 16/16/16/32（RG16×3 + AR24×1）"
else
    fail "bpp 序列不符（$b1/$b2/$b3/$b4，期望 16/16/16/32）"
fi

# ---- 3) 尺寸全 1280x1280（16 进制 w=00000500 h=00000500）----
n_wh=$(grep -a 'dumb#' "$LOG" | grep -c 'w=00000500 h=00000500' || true)
case "$n_wh" in ''|*[!0-9]*) n_wh=0 ;; esac
if [ "$n_wh" = "4" ]; then pass "dumb#1..4 尺寸全 1280x1280"; else fail "1280x1280 命中 $n_wh/4"; fi

# ---- 4) MAP_DUMB handle 1..4 各自独立 offset（无撞号）----
m1=$(grep -a 'MAP_DUMB 00000001 ' "$LOG" | head -1)
m2=$(grep -a 'MAP_DUMB 00000002 ' "$LOG" | head -1)
m3=$(grep -a 'MAP_DUMB 00000003 ' "$LOG" | head -1)
m4=$(grep -a 'MAP_DUMB 00000004 ' "$LOG" | head -1)
if [ -n "$m1" ] && [ -n "$m2" ] && [ -n "$m3" ] && [ -n "$m4" ]; then
    o1=$(printf '%s' "$m1" | grep -o ' [0-9a-f]\{8\}$')
    o2=$(printf '%s' "$m2" | grep -o ' [0-9a-f]\{8\}$')
    o3=$(printf '%s' "$m3" | grep -o ' [0-9a-f]\{8\}$')
    o4=$(printf '%s' "$m4" | grep -o ' [0-9a-f]\{8\}$')
    if [ "$o1" != "$o2" ] && [ "$o2" != "$o3" ] && [ "$o3" != "$o4" ] && [ "$o1" != "$o4" ]; then
        pass "MAP_DUMB handle 1..4 offset 互异（$o1$o2$o3$o4）"
    else
        fail "MAP_DUMB offset 有撞号（$o1/$o2/$o3/$o4）"
    fi
else
    fail "MAP_DUMB handle 序列不全（期望 1/2/3/4 各一行）"
fi

# ---- 5) AddFB2 4 次按 bo_handle 精确引用（AddFB2_h 1/2/3/4）----
a1=$(grep -a 'AddFB2_h 00000001 ' "$LOG" | head -1)
a2=$(grep -a 'AddFB2_h 00000002 ' "$LOG" | head -1)
a3=$(grep -a 'AddFB2_h 00000003 ' "$LOG" | head -1)
a4=$(grep -a 'AddFB2_h 00000004 ' "$LOG" | head -1)
if [ -n "$a1" ] && [ -n "$a2" ] && [ -n "$a3" ] && [ -n "$a4" ]; then
    pass "AddFB2 按 bo_handle 1/2/3/4 精确引用（无 FAKE_FB_ID 撞号）"
else
    fail "AddFB2_h 序列不全（$a1|$a2|$a3|$a4）"
fi

# ---- 6) SetCrtc 呈现 fb=1（RG16 实体#1，不是最后一块 AR24）----
sc=$(grep -a 'SetCrtc_fb 00000001 ' "$LOG" | head -1)
if [ -n "$sc" ]; then
    pass "SetCrtc 呈现 fb=1（RG16 实体#1）"
else
    fail "未见到 SetCrtc_fb 00000001（呈现 fb 不是实体#1）"
fi

# ---- 7) 桩产物自证：0 未定义符号 ----
# ★ 注意：'drm 未定义=0' 是 **_b6_adjudge.sh 自己 echo 到 /tmp/b6_adjudge.log** 的
#   （不是 guest stderr）⇒ 必须查 adjudge 日志，查 stderr 会恒假阴性。
#   取不到该文件时**明确报错**，不静默跳过（否则门禁退化成"只查 7 项"的假绿）。
ADJ="${2:-/tmp/b6_adjudge.log}"
if [ -f "$ADJ" ] && grep -aq 'drm 未定义=0' "$ADJ"; then
    pass "drm 桩 0 未定义符号（源: $ADJ）"
elif [ -f "$ADJ" ]; then
    fail "adjudge 日志里未见 'drm 未定义=0'（桩带未定义符号，加载即崩）"
else
    fail "缺 adjudge 日志 $ADJ，无法验证桩自证项（不静默跳过）"
fi

# ---- 8) 呈现 API 边界固化（R190：这些必须是**零调用**，是观测边界不是缺陷）----
if grep -aq 'SetPlane_geom\|PageFlip_geom' "$LOG"; then
    echo "  ⚠️ 出现 SetPlane_geom/PageFlip_geom —— driver 行为已变，需重新评估观测边界" >&2
else
    pass "SetPlane/PageFlip 零调用（观测边界与 R190 一致）"
fi

echo "=== 结果 ==="
if [ "$FAIL" = "0" ]; then
    echo "  B6 结构判据全部通过 ✅"
    echo "  ★ 注意：通过 = DRM 调用语义复刻正确；**不**等于画面渲染保真（沙箱内不可观测）。"
    exit 0
else
    echo "  B6 结构判据存在失败项 ❌" >&2
    exit 1
fi
