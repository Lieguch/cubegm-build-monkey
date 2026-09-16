#!/bin/sh
# ============================================================
# behav_capture.sh — 行为指纹采集器 v2（P5 主门禁的采集端）
#
# 在原厂二进制与重建产物上各跑一次，产出可比对的 JSON 行为指纹。
# 可运行于：① 真机  ② CI 内 qemu-arm  ③ 任意 Linux arm 环境
#
# 用法:
#   sh behav_capture.sh <binary|wrapper> <label> <out.json> [args...]
#
# 采集维度（均与「100% 原厂功能」直接对应）:
#   1. exit_code        退出码（被信号杀死 = 128+signo）
#   2. events           语义事件序列 = stdout(O|) + stderr(E|) + 设备日志(L|)
#   3. log              menu.log 的 sha256 + 行数（真机日志名是 menu.log，**不是** rkgame.log）
#   4. new_files        work 目录下新增文件（相对路径|sha256 前16）
#   5. changed_files    已有文件但内容变了
#   6. shm              icube 共享内存心跳可读性
#   7. frames           帧缓冲采样哈希（若可读 /dev/fb0）
#
# ★ v2 相对 v1 的三处关键更正（每一处都会让差分**假失败/假空洞**）：
#   a) 日志文件名：工厂用 `sprintf("%s/menu.log", work_path)`（LoadMenuLog/SaveMenuLog），
#      仓库里从来没有 rkgame.log ⇒ v1 永远采到 0 行 ⇒ B0 非空洞检查永远 INCONCLUSIVE。
#   b) stdout 必须在 **pty** 下采集：管道 ⇒ glibc 全缓冲 ⇒ 被信号杀死时缓冲区不 flush，
#      崩溃现场输出全部丢失（实测 0 字节）。v2 用 tools/pty_exec.py（只接管 fd0/1，
#      stderr 仍独立）。
#   c) 快照范围：v1 只看 saves/ states/；v2 看整个 work 目录，这样 menu.log /
#      *.dat / settings 的写入都能被看见。
# ============================================================
set -u

BIN="${1:?usage: behav_capture.sh <binary> <label> <out.json> [args...]}"
LABEL="${2:?label required}"
OUT="${3:?out.json required}"
shift 3
ARGS="$*"

WORK="${CGM_WORK:-/sdcard/cubegm}"
RUNDIR="${CGM_RUNDIR:-/tmp/behav_$LABEL}"
TIMEOUT="${CGM_TIMEOUT:-20}"
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="${PY:-python3}"

rm -rf "$RUNDIR"; mkdir -p "$RUNDIR"

# --- 假硬件 shim（可选，由 CGM_GUEST_PRELOAD 指定；两侧必须指向**同一绝对路径**）---
#   见 tools/guest_shim/fake_mem.c：把「物理寄存器映射」换成匿名零页，
#   让 sunxi_gpio_init 能成功返回 0，从而使 guest 走得更深（可观测窗口更大）。
PRELOAD="${CGM_GUEST_PRELOAD:-}"
if [ -n "$PRELOAD" ]; then
    if [ ! -f "$PRELOAD" ]; then
        echo "FATAL 指定的 guest shim 不存在：$PRELOAD"
        exit 5
    fi
    # ★★ 绝不能 `export LD_PRELOAD`：那会让**宿主** ld.so 去加载一个 armhf 的 .so
    #   （qemu-arm-static 是 x86_64 宿主程序）⇒ 立刻崩、零输出、零事件
    #   ⇒ 差分被判 INCONCLUSIVE（本地空跑实测 exit=129）。
    #   正确做法：由**包装脚本**用 qemu 的 `-E LD_PRELOAD=<path>` 注入 **guest** 环境。
    #   这里只做存在性校验 + 记录（便于溯源），不改变宿主环境。
    echo "[capture] guest shim = $PRELOAD（经 qemu -E 注入 guest；宿主环境不变）"
fi

# --- 运行器：优先 pty_exec（行缓冲），否则退回 timeout ---
#   ★ 用函数而不是 "$RUNNER" 多词变量：多词变量在路径含空格时会被拆词
#     （「把多词命令塞进变量再展开」是本项目记录在案的坑）。
HAVE_PTY=0
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
if command -v "$PY" >/dev/null 2>&1 && "$PY" -c 'import termios' >/dev/null 2>&1; then
    HAVE_PTY=1
    echo "[capture] 使用 pty_exec（stdout 行缓冲；stderr 独立）"
else
    echo "[capture] 无 pty 可用（非 POSIX / 无 termios）⇒ 降级为普通执行；崩溃现场 stdout 可能丢失"
fi

run_guest() {
    out="$1"; err="$2"
    # stdin 固定为 /dev/null：让"被测程序读 stdin"立刻得到 EOF（确定性），
    # 否则它会读到一个永不产生输入的 pty，永久阻塞到超时。
    if [ "$HAVE_PTY" = "1" ]; then
        "$PY" "$(winpath "$HERE/pty_exec.py")" --timeout "$TIMEOUT" "$BIN" $ARGS < /dev/null > "$out" 2> "$err"
        return $?
    fi
    if command -v timeout >/dev/null 2>&1; then
        timeout -s TERM "$TIMEOUT" "$BIN" $ARGS < /dev/null > "$out" 2> "$err"
        return $?
    fi
    "$BIN" $ARGS < /dev/null > "$out" 2> "$err" &
    p=$!; sleep "$TIMEOUT"; kill -TERM "$p" 2>/dev/null; wait "$p"; return $?
}

# shellcheck disable=SC2086

# --- 基线快照：整个 work 目录（路径统一转为相对路径 ⇒ 两侧绝对路径不同也仍可比）---
snap() {
    d="$1"
    [ -d "$d" ] || return 0
    find "$d" -type f 2>/dev/null | LC_ALL=C sort | while read -r f; do
        h=$(sha256sum "$f" 2>/dev/null | cut -c1-16)
        s=$(wc -c < "$f" 2>/dev/null | tr -d ' ')
        echo "${f#"$d"/}|$h|${s:-0}"
    done
}
snap "$WORK" > "$RUNDIR/pre_all.txt"

# --- 运行 ---
run_guest "$RUNDIR/stdout.txt" "$RUNDIR/stderr.txt"
RC=$?
echo "[capture] $LABEL 退出码 = $RC"

# --- 后置快照 ---
snap "$WORK" > "$RUNDIR/post_all.txt"

# --- 语义归一：剥掉 ANSI / CR / 十六进制地址 / 长数字 / **对齐空白**（保留可读语义）---
# ★★ 血泪（2026-09-16，一次**假 PASS**）：原实现只把 `[0-9]{3,}` 换成 N，**没有折叠空白**。
#    而 `/proc/meminfo` 的 `MemFree:` 是**右对齐**的：数值位数一变（如 9xxxxxx → 11xxxxxx），
#    冒号后的空格数就变 ⇒ 参考实现**自身两遍不一致** ⇒ 确定性前缀从 41 行**塌到 6 行**
#    ⇒ 门禁只判前 6 行，而两侧真正的分歧在第 18 行 ⇒ **判 PASS（假绿）**。
#    ⇒ 必须把连续空白折叠成单个空格，并去掉行首尾空白。
norm() {
    LC_ALL=C sed -e 's/\x1b\[[0-9;]*[A-Za-z]//g' \
        -e 's/\r//g' \
        -e 's/0x[0-9a-fA-F]\{2,\}/ADDR/g' \
        -e 's/[0-9]\{3,\}/N/g' \
        -e 's/[[:space:]]\{1,\}/ /g' \
        -e 's/^ //' -e 's/ $//'
}

# --- 事件序列：O| stdout，E| stderr，L| menu.log ---
: > "$RUNDIR/events.txt"
if [ -s "$RUNDIR/stdout.txt" ]; then
    norm < "$RUNDIR/stdout.txt" | LC_ALL=C grep -a '[^[:space:]]' | head -400 | sed 's/^/O|/' >> "$RUNDIR/events.txt"
fi
if [ -s "$RUNDIR/stderr.txt" ]; then
    norm < "$RUNDIR/stderr.txt" | LC_ALL=C grep -a '[^[:space:]]' | head -200 | sed 's/^/E|/' >> "$RUNDIR/events.txt"
fi

# --- 设备日志（真机日志名 = menu.log；rkgame.log 仅作兼容兜底）---
LOGNAME="none"; LOGLINES=0; LOGSHA="none"
for cand in menu.log rkgame.log; do
    if [ -f "$WORK/$cand" ]; then LOGNAME="$cand"; break; fi
done
if [ "$LOGNAME" != "none" ]; then
    LOGLINES=$(wc -l < "$WORK/$LOGNAME" 2>/dev/null | tr -d ' '); LOGLINES=${LOGLINES:-0}
    LOGSHA=$(sha256sum "$WORK/$LOGNAME" 2>/dev/null | cut -c1-16); LOGSHA=${LOGSHA:-none}
    # 二进制日志里可打印的行（若有）也纳入事件，带 L| 前缀
    if LC_ALL=C grep -aq '[[:print:]]\{8,\}' "$WORK/$LOGNAME" 2>/dev/null; then
        LC_ALL=C grep -a '[[:print:]]\{8,\}' "$WORK/$LOGNAME" 2>/dev/null | head -200 | \
            norm | sed 's/^/L|/' >> "$RUNDIR/events.txt"
    fi
fi
EVENTS=$(wc -l < "$RUNDIR/events.txt" | tr -d ' '); EVENTS=${EVENTS:-0}

# --- 新增/变更文件（相对路径）---
: > "$RUNDIR/new_files.txt"; : > "$RUNDIR/changed_files.txt"
LC_ALL=C awk -F'|' 'NR==FNR{p[$1]=$2; next}
    { if (!($1 in p)) print $1"|"$2; else if (p[$1] != $2) print $1"|"$2 }' \
    "$RUNDIR/pre_all.txt" "$RUNDIR/post_all.txt" > "$RUNDIR/all_diff.txt"
LC_ALL=C awk -F'|' 'NR==FNR{p[$1]=1; next} !($1 in p){print}' \
    "$RUNDIR/pre_all.txt" "$RUNDIR/all_diff.txt" > "$RUNDIR/new_files.txt"
LC_ALL=C awk -F'|' 'NR==FNR{p[$1]=1; next} ($1 in p){print}' \
    "$RUNDIR/pre_all.txt" "$RUNDIR/all_diff.txt" > "$RUNDIR/changed_files.txt"
NEWN=$(wc -l < "$RUNDIR/new_files.txt" | tr -d ' '); NEWN=${NEWN:-0}
CHGN=$(wc -l < "$RUNDIR/changed_files.txt" | tr -d ' '); CHGN=${CHGN:-0}

# ★ 深窗口保护：观测窗口推到菜单之后，guest 在超时前可能刷大量输出 ⇒ 给**落盘的原始输出**
#   加上限（两侧同一规则 ⇒ 差分仍公平；events 本来就有 400/200 行上限，这里只约束制品体积）。
CAPL="${CGM_CAP_LINES:-20000}"
for _f in "$RUNDIR/stdout.txt" "$RUNDIR/stderr.txt"; do
    [ -f "$_f" ] || continue
    _n=$(wc -l < "$_f" 2>/dev/null | tr -d ' '); _n=${_n:-0}
    if [ "$_n" -gt "$CAPL" ]; then
        head -n "$CAPL" "$_f" > "$_f.cap" 2>/dev/null && mv "$_f.cap" "$_f"
        echo "[capture] $(basename "$_f") 行数 $_n 超过 $CAPL → 已截断（保留前 $CAPL 行）"
    fi
done
unset _f _n

STDOUTN=$(wc -l < "$RUNDIR/stdout.txt" 2>/dev/null | tr -d ' '); STDOUTN=${STDOUTN:-0}

# --- 过滤「宿主 loader 的噪音」---
#   ★ 来历：为了让 guest 加载假硬件 shim，我们把 LD_PRELOAD 放进环境；但**宿主**的 ld.so 同样会读它，
#     于是会打印 "object '<shim>' from LD_PRELOAD cannot be preloaded (wrong ELF class)" ——
#     那是宿主侧噪音（ARM 库喂给 x86_64 的 qemu 进程），不是 guest 的输出。
#     两侧都会出现同样一行，对差分无影响，但会污染 stderr 语义 ⇒ 定向过滤并记录条数。
if [ -n "${LD_PRELOAD:-}" ]; then
    NOISE=$(grep -c 'cannot be preloaded' "$RUNDIR/stderr.txt" 2>/dev/null || true)
    case "$NOISE" in ''|*[!0-9]*) NOISE=0 ;; esac
    if [ "$NOISE" != "0" ]; then
        grep -v 'cannot be preloaded' "$RUNDIR/stderr.txt" > "$RUNDIR/stderr.txt.f" 2>/dev/null || true
        mv "$RUNDIR/stderr.txt.f" "$RUNDIR/stderr.txt"
        echo "[capture] 已过滤宿主 loader 噪音 ${NOISE} 行（LD_PRELOAD 导致的 wrong-ELF-class 警告）"
    fi
fi

STDERRLN=$(wc -l < "$RUNDIR/stderr.txt" 2>/dev/null | tr -d ' '); STDERRLN=${STDERRLN:-0}

# --- 帧缓冲采样（尽力而为）---
FBHASH="none"
if [ -r /dev/fb0 ]; then
    FBHASH=$(dd if=/dev/fb0 bs=4096 count=64 2>/dev/null | sha256sum | cut -c1-16)
fi

# --- shm 心跳 ---
SHM="0"
if command -v ipcs >/dev/null 2>&1; then
    # ★ 踩坑：`grep -c` 在 0 命中时返回 1 且**已经**打印了 "0"，再加 `|| echo 0` 会输出两行
    #   （"0\n0"）→ 拼出的 JSON 里出现裸 `0` → json.load 直接崩。
    SHM=$(ipcs -m 2>/dev/null | grep -c '0x000004d2' || true)
    case "$SHM" in ''|*[!0-9]*) SHM=0 ;; esac
fi

# --- 被测对象身份（溯源用：两侧二进制不同，但环境必须相同）---
BINSHA="none"
REAL="${CGM_BIN_REAL:-$BIN}"
if [ -f "$REAL" ]; then BINSHA=$(sha256sum "$REAL" 2>/dev/null | cut -c1-16); fi

# --- 「本侧是否真的产生了可观测行为」 ---
# ★ 只看 log_lines 是不行的：运行目录里**预置**了 menu.log（444 B，2 行），
#   于是 log_lines 恒 ≥1，B0 非空洞检查永远不触发 ⇒ 假通过。
#   真正算「行为」的只有：stdout / stderr / 新增文件 / 变更文件。
OBSERVED=false
if [ "$STDOUTN" -gt 0 ] || [ "$STDERRLN" -gt 0 ] || [ "$NEWN" -gt 0 ] || [ "$CHGN" -gt 0 ]; then
    OBSERVED=true
fi

# --- ★ 设备访问计数（SFC 有状态仿真的"轨迹形状"，是一项独立可观测指标）---
# 来历（P5 第四个真实分歧）：读循环里的设备寄存器读被 LLVM 提升出循环并向量化
#   （`vdup.32 q8,r2` + `vst1.32 {d16,d17},[r4]!` = **一次读、4 字广播**）
#   ⇒ 设备访问次数 **180 → 57**；而这一差异**在 stdout 事件里看不出来**
#   （前 17 行仍逐字相等），只有随后的校验和失败导致分支不同才暴露。
#   ⇒ 把 shim 在撤防时报出的计数显式记进指纹，比对端直接判等：
#     "同一份假设备，两侧访问它的次数必须一致"——这是 1:1 保真的直接证据。
SFC_FAULTS=0; SFC_CMDS=0
if [ -f "$RUNDIR/stderr.txt" ]; then
    _ff=$(grep -ao 'faults=[0-9]*' "$RUNDIR/stderr.txt" | tail -1 | cut -d= -f2)
    _cc=$(grep -ao 'cmds=[0-9]*'   "$RUNDIR/stderr.txt" | tail -1 | cut -d= -f2)
    case "$_ff" in ''|*[!0-9]*) SFC_FAULTS=0 ;; *) SFC_FAULTS=$_ff ;; esac
    case "$_cc" in ''|*[!0-9]*) SFC_CMDS=0   ;; *) SFC_CMDS=$_cc   ;; esac
fi

# --- JSON 输出（所有值先落变量，避免 shell 拼接产生非法 JSON）---
json_quote() { sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
TMO=false
[ "$RC" = "124" ] && TMO=true

{
    printf '{\n'
    printf '  "label": "%s",\n' "$(printf '%s' "$LABEL" | json_quote)"
    printf '  "binary": "%s",\n' "$(printf '%s' "$REAL" | json_quote)"
    printf '  "binary_sha256_16": "%s",\n' "$BINSHA"
    printf '  "wrapper": "%s",\n' "$(printf '%s' "$BIN" | json_quote)"
    printf '  "args": "%s",\n' "$(printf '%s' "$ARGS" | json_quote)"
    printf '  "workdir": "%s",\n' "$(printf '%s' "$WORK" | json_quote)"
    printf '  "exit_code": %s,\n' "$RC"
    printf '  "timed_out": %s,\n' "$TMO"
    printf '  "preload": "%s",\n' "${PRELOAD:-}"
    printf '  "observed": %s,\n' "$OBSERVED"
    printf '  "log_file": "%s",\n' "$LOGNAME"
    printf '  "log_lines": %s,\n' "$LOGLINES"
    printf '  "log_sha256_16": "%s",\n' "$LOGSHA"
    printf '  "stdout_lines": %s,\n' "$STDOUTN"
    printf '  "stderr_lines": %s,\n' "$STDERRLN"
    printf '  "shm_heartbeat": %s,\n' "$SHM"
    printf '  "sfc_faults": %s,\n' "$SFC_FAULTS"
    printf '  "sfc_cmds": %s,\n' "$SFC_CMDS"
    printf '  "frame_hash": "%s",\n' "$FBHASH"
    printf '  "events": [\n'
    LC_ALL=C awk '{gsub(/\\/,"\\\\"); gsub(/"/,"\\\""); printf "    \"%s\"%s\n", $0, (NR==n?"":",")}' \
        n="$EVENTS" "$RUNDIR/events.txt"
    printf '  ],\n'
    printf '  "new_files": [\n'
    LC_ALL=C awk '{gsub(/"/,"\\\""); printf "    \"%s\"%s\n", $0, (NR==n?"":",")}' \
        n="$NEWN" "$RUNDIR/new_files.txt"
    printf '  ],\n'
    printf '  "changed_files": [\n'
    LC_ALL=C awk '{gsub(/"/,"\\\""); printf "    \"%s\"%s\n", $0, (NR==n?"":",")}' \
        n="$CHGN" "$RUNDIR/changed_files.txt"
    printf '  ]\n'
    printf '}\n'
} > "$OUT" 2>/dev/null

# --- 自检：JSON 必须可解析（这类故障曾经静默了一整轮）---
# ★ 用 stdin 喂进去而不是把路径交给 python：这样在「bash 路径风格 ≠ python 路径风格」
#   的环境（如 Git Bash + Windows python）也不会误判成"JSON 非法"。
if command -v "$PY" >/dev/null 2>&1; then
    if [ ! -s "$OUT" ]; then
        echo "FATAL 采集未产出文件或为空：$OUT"
        exit 4
    fi
    if ! "$PY" -c 'import json,sys; json.loads(sys.stdin.read())' < "$OUT" 2>/dev/null; then
        echo "FATAL 采集出的 JSON 非法：$OUT"
        "$PY" -c 'import json,sys
try: json.loads(sys.stdin.read())
except Exception as e: print("   ", e)' < "$OUT" 2>/dev/null || true
        exit 4
    fi
fi

echo "captured: $OUT (exit=$RC, log=$LOGNAME/$LOGLINES 行, stdout=$STDOUTN 行, stderr=$STDERRLN 行, events=$EVENTS, new=$NEWN, changed=$CHGN)"
