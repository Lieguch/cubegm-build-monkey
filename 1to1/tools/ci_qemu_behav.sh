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
#     工厂 rkgame 里烧死的是 `/sdcard/...`，用真实路径才忠实。
#   · 采集/比对交给既有工具 behav_capture.sh / behav_diff.py。
#   · ★ 额外做**运行时探针**（strace 前 N 行 + 翻译级 in_asm 尾 N 行）：
#     只看"退出码 + 空 stderr"是没法定位 SIGILL 的，必须有执行轨迹。
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
PROBE_TIMEOUT="${CGM_PROBE_TIMEOUT:-3}"

QLIB="$SYSROOT/usr/lib/arm-linux-gnueabihf:$SYSROOT/lib/arm-linux-gnueabihf"

mkdir -p "$OUT" "$WORK/saves" "$WORK/states"
: > "$WORK/rkgame.log" 2>/dev/null || true

echo "============================================================"
echo "P5 行为差分（qemu-user）"
echo "  SYSROOT = $SYSROOT"
echo "  WORK    = $WORK"
echo "  TIMEOUT = ${TIMEOUT}s（探针 ${PROBE_TIMEOUT}s）"
echo "  rebuild = $REBUILD"
echo "  factory = $FACTORY"
echo "============================================================"

for b in "$REBUILD" "$FACTORY"; do
    if [ ! -f "$b" ]; then echo "FATAL 缺少二进制: $b"; exit 1; fi
done

# ---- 参考二进制"裸跑"诊断：不带 -strace/-E，看 qemu 自己报什么 ----
# 来历：工厂二进制在探针里 10ms 内 exit=1、stdout/stderr 全空、连 syscall 轨迹都没有
#       ⇒ 说明 qemu 在加载阶段就退出了，必须看它的**原始**报错（而不是 guest 的输出）。
# ★ 注意：脚本跑在 `sh`(dash) 下，**没有** `${PIPESTATUS[@]}` 这个 bash 数组；
#   要看管道左侧的退出码必须落临时文件，否则报 "Bad substitution" 直接中断整个脚本。
echo "--- 参考二进制裸跑（无 -strace / 无 -E）---"
ls -la "$FACTORY"
qemu-arm-static -L "$SYSROOT" -cpu cortex-a7 "$FACTORY" > "$OUT/bare_factory.txt" 2>&1
echo "裸跑 rc=$?"
head -15 "$OUT/bare_factory.txt" 2>/dev/null || true
echo "--- 对照：重建产物裸跑（同样无 -strace / 无 -E）---"
qemu-arm-static -L "$SYSROOT" -cpu cortex-a7 "$REBUILD" > "$OUT/bare_rebuild.txt" 2>&1
echo "裸跑 rc=$?"
head -15 "$OUT/bare_rebuild.txt" 2>/dev/null || true
echo

# ---- ★ 工厂侧 rc=1 且**零输出**（连 syscall 轨迹都没有）⇒ 问题在 qemu 自身而非 guest。
#     用宿主 strace 观察 qemu 进程自己的系统调用，直接看它卡在哪一步退的。
if command -v strace >/dev/null 2>&1; then
    echo "--- 宿主 strace：qemu 自身为何退出（工厂二进制）---"
    strace -f -e trace=openat,execve,mmap2,ioctl,readlink -o "$OUT/host_strace_factory.txt" \
        qemu-arm-static -L "$SYSROOT" -cpu cortex-a7 "$FACTORY" > /dev/null 2>&1
    echo "rc=$?"
    tail -25 "$OUT/host_strace_factory.txt" 2>/dev/null || true
    echo "--- 对照：qemu 自身系统调用（重建产物，应该能正常加载）---"
    strace -f -e trace=openat,execve,mmap2,ioctl,readlink -o "$OUT/host_strace_rebuild.txt" \
        qemu-arm-static -L "$SYSROOT" -cpu cortex-a7 "$REBUILD" > /dev/null 2>&1
    echo "rc=$?"
    tail -25 "$OUT/host_strace_rebuild.txt" 2>/dev/null || true
    echo
fi

# ---- 试探：是否只是"缺可执行位"或"-cpu 选择"的问题（两条一次问清）----
echo "--- 试探 A：给工厂二进制加可执行位后裸跑 ---"
cp "$FACTORY" "$OUT/factory_exec_test.bin" && chmod +x "$OUT/factory_exec_test.bin"
qemu-arm-static -L "$SYSROOT" -cpu cortex-a7 "$OUT/factory_exec_test.bin" > "$OUT/bare_factory_exec.txt" 2>&1
echo "rc=$?"; head -8 "$OUT/bare_factory_exec.txt" 2>/dev/null || true
echo "--- 试探 B：不带 -cpu（用 qemu 默认 cpu 模型）---"
qemu-arm-static -L "$SYSROOT" "$FACTORY" > "$OUT/bare_factory_nocpu.txt" 2>&1
echo "rc=$?"; head -8 "$OUT/bare_factory_nocpu.txt" 2>/dev/null || true
echo

# ---- 包装脚本：两侧仅「被测二进制」不同，其余全同；$3 为附加 qemu 参数 ----
mk_wrapper() {
    # $1 = 真实二进制   $2 = 包装脚本   $3 = 附加 qemu 参数（可空）
    extra="${3:-}"
    cat > "$2" <<EOF
#!/bin/sh
exec qemu-arm-static -L $SYSROOT -cpu cortex-a7 $extra \\
  -E LD_LIBRARY_PATH=$QLIB \\
  -E PATH=$SYSROOT/usr/bin:/usr/bin:/bin \\
  -E HOME=/tmp -E TMPDIR=/tmp \\
  "$1" "\$@"
EOF
    chmod +x "$2"
}

# ---- 探针：strace 头 + in_asm 尾（定位崩溃点）----
probe() {
    # $1 = label(factory|rebuild)  $2 = 附加 qemu 参数  $3 = tag（用于文件命名）
    label="$1"; extra="$2"; tag="$3"
    case "$label" in
      factory) bin="$FACTORY" ;;
      rebuild) bin="$REBUILD" ;;
      *) echo "unknown probe label $label"; return 1 ;;
    esac
    w="$OUT/probe_${label}_${tag}.sh"
    mk_wrapper "$bin" "$w" "$extra"

    echo ""
    echo "########## 探针 ${label}/${tag}（qemu 参数: ${extra:-无}）##########"
    : > "$WORK/rkgame.log" 2>/dev/null || true
    set +e
    timeout "$PROBE_TIMEOUT" "$w" > "$OUT/probe_stdout_${label}_${tag}.txt" \
        2> "$OUT/probe_stderr_${label}_${tag}.txt"
    prc=$?
    set -e
    echo "   探针退出码 = $prc  （124=超时仍在跑；132=SIGILL；139=SIGSEGV；其余为 guest 退出码）"
    echo "--- stderr 前 40 行（含 -strace 的 syscall 轨迹）---"
    head -40 "$OUT/probe_stderr_${label}_${tag}.txt" 2>/dev/null || true
    echo "--- stdout 前 15 行 ---"
    head -15 "$OUT/probe_stdout_${label}_${tag}.txt" 2>/dev/null || true
    echo "--- 设备日志 $WORK/rkgame.log（前 15 行）---"
    head -15 "$WORK/rkgame.log" 2>/dev/null || true
    echo "--- $WORK 目录 ---"
    ls -la "$WORK" 2>/dev/null || true
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
    : > "$WORK/rkgame.log" 2>/dev/null || true
}

mk_wrapper "$FACTORY" "$OUT/run_factory.sh" ""
mk_wrapper "$REBUILD" "$OUT/run_rebuild.sh" ""

# 先探针（短超时、带 syscall 轨迹），再正式采集
#   -strace：qemu 打印 guest syscall 轨迹 → 能看到"跑到哪一步断的"
#   -d in_asm -D：把 guest 翻译块写文件 → 拿尾部即可看到崩溃前最后执行的指令
probe factory "-strace" "strace"
probe rebuild "-strace" "strace"
probe rebuild "-d in_asm -D $OUT/in_asm_rebuild.log" "asm"

capture factory "$OUT/run_factory.sh"
capture rebuild "$OUT/run_rebuild.sh"

if [ -f "$OUT/in_asm_rebuild.log" ]; then
    # ★ in_asm 日志可能几十 MB —— 只保留尾部（崩溃前最后执行的指令），避免制品爆掉
    tail -300 "$OUT/in_asm_rebuild.log" > "$OUT/in_asm_rebuild_tail.txt"
    rm -f "$OUT/in_asm_rebuild.log"
    echo ""
    echo "--- rebuild 翻译级轨迹尾部（最后 50 行 → $OUT/in_asm_rebuild_tail.txt）---"
    tail -50 "$OUT/in_asm_rebuild_tail.txt" 2>/dev/null || true
fi

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
