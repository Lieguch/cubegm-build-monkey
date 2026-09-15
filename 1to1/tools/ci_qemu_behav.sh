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
# ★ Windows 开发机：python.exe 也是原生程序，不认 `/d/...` ⇒ 把脚本路径按需转 Windows 形式。
#   （CI 是 Linux，cygpath 不存在 ⇒ 原样返回，无副作用。）
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
GUEST="$WORK/rkgame"
TIMEOUT="${CGM_TIMEOUT:-20}"
PROBE_TIMEOUT="${CGM_PROBE_TIMEOUT:-3}"
EXEC_TIMEOUT="${CGM_EXEC_TIMEOUT:-300}"   # -d exec 会显著拖慢 guest，给足时间

QLIB="$SYSROOT/usr/lib/arm-linux-gnueabihf:$SYSROOT/lib/arm-linux-gnueabihf"

mkdir -p "$OUT"

# ---- 假硬件 shim（两侧同一绝对路径 ⇒ 差分仍公平）----
#   见 tools/guest_shim/fake_mem.c。构建失败则**降级**为不带 shim 跑（并在报告里说明），
#   以便这一轮仍能产出可比较的指纹，而不是整轮失败。
# ★ shim **不能**放在 $WORK 里：stage_sdcard_env.sh 每轮都会重建 $WORK（rm -rf + 解包），
#   放在那里会被抹掉 ⇒ behav_capture 报 "FATAL 指定的 guest shim 不存在"（本地空跑实测抓到）。
#   构建到 "$OUT/guest_shim.so"，再由 run_side 在铺完环境之后 cp 进 $WORK。
SHIM="$OUT/guest_shim.so"
SHIM_ON=0
if [ "${CGM_GUEST_SHIM:-1}" = "1" ] && sh "$ROOT/tools/build_guest_shim.sh" "$SHIM" > "$OUT/shim_build.txt" 2>&1; then
    SHIM_ON=1
    echo "guest shim = $SHIM（已构建；两侧都加载它）"
else
    echo "!! guest shim 构建失败/被禁用 ⇒ 本轮**不带 shim**（可观测窗口较浅）；日志见 $OUT/shim_build.txt"
    SHIM=""
fi

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
# ★★ shim 必须用 qemu 的 `-E` 注入 **guest 环境**，绝不能 export 到宿主环境：
#   `qemu-arm-static` 自身是 **x86_64 宿主**程序，宿主 ld.so 见到 `LD_PRELOAD=<armhf .so>`
#   会直接崩/静默退出（实测两侧 exit=129、零输出、零事件 ⇒ 差分判 INCONCLUSIVE）。
PRELOAD_OPT=""
if [ -n "$SHIM" ]; then
    PRELOAD_OPT="-E LD_PRELOAD=$SHIM"
    # 让 shim 输出一行"投毒参数"证据（默认静默）；两侧一致 ⇒ 不影响差分有效性。
    if [ "${CGM_SHIM_VERBOSE:-1}" = "1" ]; then
        PRELOAD_OPT="$PRELOAD_OPT -E CGM_SHIM_VERBOSE=1"
    fi
fi

mk_wrap() {
    # $1 = 输出脚本   $2 = 附加 qemu 参数
    cat > "$1" <<EOF
#!/bin/sh
exec qemu-arm-static -L $SYSROOT -cpu cortex-a7 ${2:-} \\
  $PRELOAD_OPT \\
  -E LD_LIBRARY_PATH=$QLIB \\
  -E PATH=$SYSROOT/usr/bin:/usr/bin:/bin \\
  -E HOME=/tmp -E TMPDIR=/tmp -E LC_ALL=C -E LANG=C \\
  "$GUEST" "\$@"
EOF
    chmod +x "$1"
}

# ---- 回溯探针：qemu 的 gdbstub + gdb-multiarch ⇒ 取**真实崩溃点与调用栈** ----
#   来历：行为差分只剩 1 项时，`-strace` 只能说明"崩在哪个 syscall 之后"，
#   `-d in_asm` 的尾部只到"最后被翻译的块"（已翻译代码里的坏访存不会再记一行），
#   于是无法区分「已翻译代码里的坏访存」与「跳到了坏地址」。gdb 直接给 pc/lr/返回栈。
#   两侧都取 ⇒ 工厂侧（已知终止于 dlclose(NULL)）可作对照基线。
bt_probe() {
    label="$1"
    if ! command -v gdb-multiarch >/dev/null 2>&1; then
        echo "   [skip] 无 gdb-multiarch，跳过回溯探针（apt install gdb-multiarch 可启用）"
        return 0
    fi
    port=12345
    [ "$label" = "rebuild" ] && port=12346
    wrap="$OUT/run_guest_bt_${label}.sh"
    mk_wrap "$wrap" "-g $port"
    bs="$OUT/bt_${label}.txt"
    echo ""
    echo "########## 回溯探针 ${label}（qemu gdbstub :$port）##########"
    set +e
    "$wrap" >/dev/null 2>&1 &
    qpid=$!
    sleep 3
    timeout 240 gdb-multiarch -q -batch \
        -ex "set confirm off" \
        -ex "set pagination off" \
        -ex "set sysroot $SYSROOT" \
        -ex "file $GUEST" \
        -ex "target remote localhost:$port" \
        -ex "continue" \
        -ex "echo \n=== 崩溃现场 ===\n" \
        -ex "info registers pc sp lr r0 r1 r2 r3 r4" \
        -ex "bt" \
        -ex "x/6i \$pc-12" \
        -ex "x/8xw \$sp" \
        -ex "echo \n=== 关键全局（guest 非 PIE，地址即链接地址）===\n" \
        -ex "x/1xw 0x003b21c8" \
        -ex "x/1xw 0x003cfab8" \
        -ex "echo \n=== lr 指向的调用点 ===\n" \
        -ex "x/12i \$lr-40" \
        -ex "info symbol \$pc" \
        -ex "info symbol \$lr" \
        > "$bs" 2>&1
    grc=$?
    kill "$qpid" 2>/dev/null || true
    wait "$qpid" 2>/dev/null || true
    set -e
    echo "   gdb 退出码 = $grc（0 = 正常取到现场）→ $bs"
    sed -n '1,70p' "$bs" 2>/dev/null || true
}

# ---- 执行轨迹探针：`-d exec` 记录**每一个被执行的翻译块**（含已缓存块）----
#   为什么需要它：`-d in_asm` 只在"新翻译一个块"时写一行，所以**已缓存块里的坏访存/
#   坏跳转不会留下痕迹**（实测：日志尾部停在 spi_driver_init 的 `pop {…,pc}`，
#   之后跳到哪去了一无所知）。`-d exec` 每次执行都记一行 ⇒ 最后几行就是真实执行路径。
exec_probe() {
    label="$1"
    wrap="$OUT/run_guest_exec_${label}.sh"
    log="$OUT/exec_${label}.log"
    mk_wrap "$wrap" "-d exec -D $log"
    echo ""
    echo "########## 执行轨迹探针 ${label}（-d exec，上限 ${EXEC_TIMEOUT}s）##########"
    set +e
    timeout "$EXEC_TIMEOUT" "$wrap" >/dev/null 2>&1
    prc=$?
    set -e
    echo "   退出码 = $prc"
    if [ -f "$log" ]; then
        echo "   原始轨迹行数 = $(wc -l < "$log" 2>/dev/null)"
        # 只保留尾部（原始日志很大，不放进制品）
        tail -800 "$log" > "$OUT/exec_tail_${label}.txt"
        rm -f "$log"
        echo "--- 尾部 40 行（每行 = 一个被执行翻译块的入口 pc）---"
        tail -40 "$OUT/exec_tail_${label}.txt"
    else
        echo "   （未生成轨迹日志）"
    fi
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
    if [ -n "$SHIM" ] && [ -f "$SHIM" ]; then
        cp "$SHIM" "$WORK/guest_shim.so" || SHIM=""
    fi
    ls -la "$GUEST"

    probe "$label" "$WRAP_ST" "strace"
    bt_probe "$label"
    exec_probe "$label"

    echo ""
    echo "########## 重新铺环境（清掉探针留下的痕迹）后采集 ${label} ##########"
    sh "$ROOT/tools/stage_sdcard_env.sh" "$WORK" "$GOLDEN" >/dev/null || exit 1
    cp "$src" "$GUEST"; chmod +x "$GUEST"
    # shim 在每次铺环境之后都要重新放回（stage 会重建 $WORK）；两侧同一绝对路径 ⇒ 差分公平
    if [ -n "$SHIM" ] && [ -f "$SHIM" ]; then
        cp "$SHIM" "$WORK/guest_shim.so" || { echo "!! shim 拷贝失败"; SHIM=""; }
    fi

    CGM_WORK="$WORK" CGM_RUNDIR="$OUT/rundir_$label" CGM_TIMEOUT="$TIMEOUT" \
        CGM_BIN_REAL="$GUEST" CGM_GUEST_PRELOAD="$SHIM" \
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
# ★ 确定性控制组：**同一份参考二进制再跑一遍**（默认开启，CGM_CONTROL=0 可关）。
#   为什么要它：假硬件下若某次读失败，上层会打印**未初始化的栈缓冲** ⇒ 垃圾值取决于两份
#   二进制各自的栈布局 ⇒ 拿它当"实现差异"是假的。控制组给出「参考实现自身可复现的前缀」，
#   门禁只判这个前缀（详见 tools/behav_diff.py 的 B0c）。
CONTROL_ARGS=""
if [ "${CGM_CONTROL:-1}" = "1" ]; then
    run_side control "$FACTORY"
    CONTROL_ARGS="--control $OUT/behav_control.json"
else
    echo "!! CGM_CONTROL=0 ⇒ 本轮没有确定性控制组（门禁退化为全量严格比较）"
fi
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
# shellcheck disable=SC2086
"${PY:-python3}" "$(winpath "$ROOT/tools/behav_diff.py")" "$OUT/behav_factory.json" "$OUT/behav_rebuild.json" $CONTROL_ARGS --detail \
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
    if [ -f "$OUT/behav_control.json" ]; then
        echo "- 控制端（同一份参考二进制复跑）：\`$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print("sha=%s exit=%s events=%d"%(d["binary_sha256_16"],d["exit_code"],len(d["events"])))' "$OUT/behav_control.json" 2>/dev/null || echo "n/a")\`"
    else
        echo "- 控制端：**未运行**（CGM_CONTROL=0）⇒ 无法区分实现差异与参考实现自身不确定"
    fi
    echo ""
    echo '```'
    cat "$OUT/behav_diff.txt" 2>/dev/null | tail -30
    echo '```'
    echo ""
    echo "退出码：$rc（0=PASS，2=FAIL，3=INCONCLUSIVE）"
} >> "${GITHUB_STEP_SUMMARY:-/dev/null}" 2>/dev/null || true

exit $rc
