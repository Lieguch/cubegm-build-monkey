#!/bin/sh
# ============================================================
# ci_qemu_behav.sh — P5 行为差分（CI 内用 qemu-user 跑两侧，再比对指纹）
#
# 为什么必须两侧都在**同一环境、同一路径**跑：
#   ① 行为指纹含日志事件、退出码、新建文件；这些都与 libc/qemu/路径有关。
#      拿本地工厂指纹去比 CI 重建指纹 = 比的是环境差异，不是代码差异。
#   ② 工厂 rkgame 用 /proc/self/exe 的目录当 work_path，再用它拼出 setting.xml /
#      cores/config.xml / menu.log / joystick.zip / saves / states 等所有路径。
#      若两个二进制各放各自仓库目录，work_path 不同 ⇒ main() 打印的 `directory:`
#      行不同、能读到的资源也不同。⇒ **两侧必须从同一个绝对路径运行**
#      （真机就是 /sdcard/cubegm/rkgame）：先铺环境+放工厂二进制跑一次，再
#      重新铺环境+放重建产物跑第二次，路径逐字节相同，只有文件内容不同。
#
# 关键设计
#   · 最小真机环境 golden/sdcard_min/（原厂 SD 只读拷贝，含 MANIFEST.sha256 核验）
#   · 每次运行前 chmod +x（★ git 检出是 0644，qemu-user 对不可执行目标会静默 exit 1）
#   · 采集/比对交给 behav_capture.sh / behav_diff.py（stdout 经 pty 抓，避免全缓冲丢输出）
#   · 附加运行时探针（-strace / -d in_asm），只看"退出码+空 stderr"是定位不了崩溃的
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
GOLDEN="$ROOT/golden/sdcard_min"
PY="${PY:-python3}"
GUEST="$WORK/rkgame"
TIMEOUT="${CGM_TIMEOUT:-20}"
PROBE_TIMEOUT="${CGM_PROBE_TIMEOUT:-3}"

QLIB="$SYSROOT/usr/lib/arm-linux-gnueabihf:$SYSROOT/lib/arm-linux-gnueabihf"

mkdir -p "$OUT"

echo "============================================================"
echo "P5 行为差分（qemu-user）"
echo "  SYSROOT = $SYSROOT"
echo "  WORK    = $WORK   （两侧同一路径）"
echo "  GUEST   = $GUEST"
echo "  TIMEOUT = ${TIMEOUT}s（探针 ${PROBE_TIMEOUT}s）"
echo "  rebuild = $REBUILD"
echo "  factory = $FACTORY"
echo "============================================================"

for b in "$REBUILD" "$FACTORY"; do
    if [ ! -f "$b" ]; then echo "FATAL 缺少二进制: $b"; exit 1; fi
done
ls -la "$FACTORY" "$REBUILD"

# ---- 唯一的包装脚本：guest 路径恒为 $GUEST（两侧共用）----
WRAP="$OUT/run_guest.sh"
mk_wrap() {
    # $1 = 输出脚本   $2 = 附加 qemu 参数
    cat > "$1" <<EOF
#!/bin/sh
exec qemu-arm-static -L $SYSROOT -cpu cortex-a7 ${2:-} \\
  -E LD_LIBRARY_PATH=$QLIB \\
  -E PATH=$SYSROOT/usr/bin:/usr/bin:/bin \\
  -E HOME=/tmp -E TMPDIR=/tmp -E LC_ALL=C -E LANG=C \\
  "$GUEST" "\$@"
EOF
    chmod +x "$1"
}
mk_wrap "$WRAP" ""
WRAP_ST="$OUT/run_guest_strace.sh"; mk_wrap "$WRAP_ST" "-strace"
WRAP_ASM="$OUT/run_guest_asm.sh";    mk_wrap "$WRAP_ASM" "-d in_asm -D $OUT/in_asm.log"

# ---- 探针：短超时 + syscall 轨迹（定位"卡在哪一步"）----
probe() {
    label="$1"; wrap="$2"; tag="$3"
    echo ""
    echo "########## 探针 ${label}/${tag} ##########"
    set +e
    timeout "$PROBE_TIMEOUT" "$wrap" > "$OUT/probe_stdout_${label}_${tag}.txt" \
        2> "$OUT/probe_stderr_${label}_${tag}.txt"
    prc=$?
    set -e
    echo "   退出码 = $prc  （124=超时仍在跑；132=SIGILL；134=SIGABRT；139=SIGSEGV）"
    echo "--- stderr 前 30 行 ---"
    head -30 "$OUT/probe_stderr_${label}_${tag}.txt" 2>/dev/null || true
    echo "--- stdout 前 15 行 ---"
    head -15 "$OUT/probe_stdout_${label}_${tag}.txt" 2>/dev/null || true
}

# ---- 布置某一侧 + 采集 ----
#   ★ 探针必须跑在**独立的一遍**里，之后重新铺环境再采集：
#     探针本身会执行 guest（可能新建/改写 saves、states、menu.log），若直接接着采集，
#     采集的"前置快照"已经含有探针造成的改动 ⇒ new_files / changed_files 永远为空，
#     差分静默失去一个维度。（本地空跑实测抓到过。）
run_side() {
    label="$1"; src="$2"
    echo ""
    echo "########## 布置 ${label} 侧运行目录（两侧同一绝对路径 $GUEST）##########"
    sh "$ROOT/tools/stage_sdcard_env.sh" "$WORK" "$GOLDEN" || exit 1
    cp "$src" "$GUEST"
    # ★ 必须：git 检出的 golden/factory.rkgame.bin 是 0644；qemu-user 对不可执行
    #   目标会走 execve 回退 → EACCES → **静默 exit 1、零输出、零 syscall**（曾整轮误判）
    chmod +x "$GUEST"
    ls -la "$GUEST"

    probe "$label" "$WRAP_ST" "strace"

    echo ""
    echo "########## 重新铺环境（清掉探针留下的痕迹）后采集 ${label} ##########"
    sh "$ROOT/tools/stage_sdcard_env.sh" "$WORK" "$GOLDEN" >/dev/null || exit 1
    cp "$src" "$GUEST"; chmod +x "$GUEST"

    CGM_WORK="$WORK" CGM_RUNDIR="$OUT/rundir_$label" CGM_TIMEOUT="$TIMEOUT" \
        CGM_BIN_REAL="$GUEST" \
        sh "$ROOT/tools/behav_capture.sh" "$WRAP" "$label" "$OUT/behav_$label.json" \
        || echo "  [note] behav_capture 返回非零（超时/异常退出也照样产出指纹，继续）"

    echo "--- ${label} stdout（前 20 行）---"
    head -20 "$OUT/rundir_$label/stdout.txt" 2>/dev/null || true
    echo "--- ${label} stderr（前 20 行）---"
    head -20 "$OUT/rundir_$label/stderr.txt" 2>/dev/null || true
    echo "--- ${label} new/changed 文件 ---"
    cat "$OUT/rundir_$label/new_files.txt" "$OUT/rundir_$label/changed_files.txt" 2>/dev/null || true
}

run_side factory "$FACTORY"
run_side rebuild "$REBUILD"

# 重建侧额外做一次翻译级探针（崩溃现场的最后指令）
echo ""
echo "########## 探针 rebuild/asm（翻译级轨迹）##########"
WM="$OUT/run_guest_asm.sh"; chmod +x "$WM" 2>/dev/null || true
set +e
timeout "$PROBE_TIMEOUT" "$WM" > "$OUT/probe_stdout_rebuild_asm.txt" 2>&1
echo "   退出码 = $?"
set -e
if [ -f "$OUT/in_asm.log" ]; then
    tail -300 "$OUT/in_asm.log" > "$OUT/in_asm_tail.txt"
    rm -f "$OUT/in_asm.log"
    echo "--- 翻译级轨迹尾部（最后 40 行 → $OUT/in_asm_tail.txt）---"
    tail -40 "$OUT/in_asm_tail.txt" 2>/dev/null || true
fi

echo ""
echo "============================================================"
echo "behav_diff: factory vs rebuild"
echo "============================================================"
# ★ 不用管道 + $?：POSIX sh 没有 ${PIPESTATUS[@]}，`cmd | tee f; rc=$?` 拿到的是 **tee** 的退出码
#   ⇒ 门禁永远"成功"。落文件再 cat。
set +e
"${PY:-python3}" "$ROOT/tools/behav_diff.py" "$OUT/behav_factory.json" "$OUT/behav_rebuild.json" --detail \
    > "$OUT/behav_diff.txt" 2>&1
rc=$?
set -e
cat "$OUT/behav_diff.txt" 2>/dev/null || true
echo "behav_diff 退出码 = $rc"

# 供 CI 的 Step Summary 使用（不必下载制品就能看到每项门禁数值）
{
    echo "## P5 qemu 行为差分（factory vs rebuild）"
    echo ""
    echo "- 参考端：\`$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print("%s sha=%s exit=%s stdout=%s"%(d["binary"],d["binary_sha256_16"],d["exit_code"],d["stdout_lines"]))' "$OUT/behav_factory.json" 2>/dev/null || echo "n/a")\`"
    echo "- 重建端：\`$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print("%s sha=%s exit=%s stdout=%s"%(d["binary"],d["binary_sha256_16"],d["exit_code"],d["stdout_lines"]))' "$OUT/behav_rebuild.json" 2>/dev/null || echo "n/a")\`"
    echo ""
    echo '```'
    cat "$OUT/behav_diff.txt" 2>/dev/null | tail -30
    echo '```'
    echo ""
    echo "退出码：$rc（0=PASS，2=FAIL，3=INCONCLUSIVE）"
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}" 2>/dev/null || true

exit $rc
