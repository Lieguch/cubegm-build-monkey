#!/bin/sh
# ============================================================
# ci_qemu_behav.sh — P5 行为差分（在 CI 内用 qemu-user 跑两侧，再比对指纹）
#
# 为什么必须两侧都在**同一环境**跑：
#   行为指纹含日志事件、退出码、新建文件；这些都与 libc/qemu/路径有关。
#   拿本地工厂指纹去比 CI 重建指纹 = 比的是环境差异，不是代码差异。
#
# 关键设计
#   · 两侧用**完全相同的 qemu 参数与工作目录**，只有被测二进制不同。
#   · 工作目录固定为真机同款 `/sdcard/cubegm`（**不禁用**任何路径）：
#     工厂 rkgame 里烧死的是 `/sdcard/...`，用真实路径才忠实；
#     早期项目靠 `-E RKGAME_WORK_PATH=` 改路径，那只对它自己的重建有效。
#   · 采集/比对交给既有工具 behav_capture.sh / behav_diff.py（不在本脚本里重复实现）。
#
# 用法:
#   SYSROOT=/arm-root sh tools/ci_qemu_behav.sh <rebuild.elf> <factory.bin> [outdir]
# ============================================================
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SYSROOT="${SYSROOT:-/arm-root}"
REBUILD="${1:?usage: ci_qemu_behav.sh <rebuild.elf> <factory.bin> [outdir]}"
FACTORY="${2:?factory bin required}"
OUT="${3:-$ROOT/report/qemu}"
WORK="${CGM_WORK:-/sdcard/cubegm}"
TIMEOUT="${CGM_TIMEOUT:-20}"

QLIB="$SYSROOT/usr/lib/arm-linux-gnueabihf:$SYSROOT/lib/arm-linux-gnueabihf"

mkdir -p "$OUT" "$WORK/saves" "$WORK/states"
: > "$WORK/rkgame.log" 2>/dev/null || true

echo "============================================================"
echo "P5 行为差分（qemu-user）"
echo "  SYSROOT = $SYSROOT"
echo "  WORK    = $WORK"
echo "  TIMEOUT = ${TIMEOUT}s"
echo "  rebuild = $REBUILD"
echo "  factory = $FACTORY"
echo "============================================================"

for b in "$REBUILD" "$FACTORY"; do
    if [ ! -f "$b" ]; then echo "FATAL 缺少二进制: $b"; exit 1; fi
done

# ---- 包装脚本：两侧仅「被测二进制」不同，其余全同 ----
mk_wrapper() {
    # $1 = 真实二进制   $2 = 包装脚本
    cat > "$2" <<EOF
#!/bin/sh
exec qemu-arm-static -L $SYSROOT -cpu cortex-a7 \\
  -E LD_LIBRARY_PATH=$QLIB \\
  -E PATH=$SYSROOT/usr/bin:/usr/bin:/bin \\
  -E HOME=/tmp -E TMPDIR=/tmp \\
  "$1" "\$@"
EOF
    chmod +x "$2"
}

# ---- 采集一侧 ----
capture() {
    label="$1"; wrapper="$2"
    echo ""
    echo "########## 采集 $label ##########"
    CGM_WORK="$WORK" CGM_RUNDIR="$OUT/rundir_$label" CGM_TIMEOUT="$TIMEOUT" \
        sh "$ROOT/tools/behav_capture.sh" "$wrapper" "$label" "$OUT/behav_$label.json" \
        || echo "  [note] behav_capture 返回非零（超时/异常退出也照样产出指纹，继续）"

    echo "--- $label stderr（前 30 行）---"
    head -30 "$OUT/rundir_$label/stderr.txt" 2>/dev/null || true
    echo "--- $label stdout（前 15 行）---"
    head -15 "$OUT/rundir_$label/stdout.txt" 2>/dev/null || true
    echo "--- 设备日志 $WORK/rkgame.log（前 25 行）---"
    head -25 "$WORK/rkgame.log" 2>/dev/null || true
    echo "--- $WORK 目录 ---"
    ls -la "$WORK" 2>/dev/null || true
    # 每次采集后清日志，避免 O_APPEND 串味
    : > "$WORK/rkgame.log" 2>/dev/null || true
}

mk_wrapper "$FACTORY" "$OUT/run_factory.sh"
mk_wrapper "$REBUILD" "$OUT/run_rebuild.sh"

capture factory "$OUT/run_factory.sh"
capture rebuild "$OUT/run_rebuild.sh"

echo ""
echo "============================================================"
echo "behav_diff: factory vs rebuild"
echo "============================================================"
set +e
python3 "$ROOT/tools/behav_diff.py" "$OUT/behav_factory.json" "$OUT/behav_rebuild.json" --detail
rc=$?
set -e
echo "behav_diff 退出码 = $rc"
exit $rc
