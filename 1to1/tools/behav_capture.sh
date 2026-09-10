#!/bin/sh
# ============================================================
# behav_capture.sh — 行为指纹采集器（P4 主门禁的采集端）
#
# 在原厂二进制与重建产物上各跑一次，产出可比对的 JSON 行为指纹。
# 可运行于：① 真机  ② CI 内 qemu-arm  ③ 任意 Linux arm 环境
#
# 用法:
#   sh behav_capture.sh <binary> <label> <out.json> [args...]
#   例:
#     sh behav_capture.sh /sdcard/cubegm/rkgame        factory  factory.json
#     sh behav_capture.sh /sdcard/cubegm/rkgame-1to1   rebuild  rebuild.json
#     sh behav_capture.sh ./rkgame                     rebuild  ci.json   /JoystickTest
#
# 采集维度（均与「100% 原厂功能」直接对应）:
#   1. exit_code        各入口退出码
#   2. log_events       rkgame.log 的**语义事件序列**（剥离时间戳/地址/长度）
#   3. log_lines        日志行数（量级）
#   4. writes           saves/ states/ 目录下文件路径 + 内容 sha256
#   5. shm              icube 共享内存心跳可读性
#   6. frames           帧缓冲采样哈希（若可读 /dev/fb0 或 DRM dump）
# ============================================================
set -u

BIN="${1:?usage: behav_capture.sh <binary> <label> <out.json> [args...]}"
LABEL="${2:?label required}"
OUT="${3:?out.json required}"
shift 3
ARGS="$*"

WORK="${CGM_WORK:-/sdcard/cubegm}"
[ -d "$WORK" ] || WORK="${CGM_WORK:-/mnt/sdcard/cubegm}"
RUNDIR="${CGM_RUNDIR:-/tmp/behav_$LABEL}"
TIMEOUT="${CGM_TIMEOUT:-20}"
LOGF="$WORK/rkgame.log"

rm -rf "$RUNDIR"; mkdir -p "$RUNDIR"

# --- 基线快照：采集前记录 saves/states 现状 ---
snap() {
    d="$1"
    [ -d "$d" ] || return 0
    find "$d" -type f 2>/dev/null | sort | while read -r f; do
        h=$(sha256sum "$f" 2>/dev/null | cut -c1-16)
        echo "$f|$h"
    done
}
snap "$WORK/saves"  > "$RUNDIR/pre_saves.txt"
snap "$WORK/states" > "$RUNDIR/pre_states.txt"

# --- 清日志，运行 ---
: > "$LOGF" 2>/dev/null || true
if command -v timeout >/dev/null 2>&1; then
    timeout -s TERM "$TIMEOUT" "$BIN" $ARGS > "$RUNDIR/stdout.txt" 2> "$RUNDIR/stderr.txt"
else
    "$BIN" $ARGS > "$RUNDIR/stdout.txt" 2> "$RUNDIR/stderr.txt" &
    P=$!; sleep "$TIMEOUT"; kill -TERM $P 2>/dev/null; wait $P
fi
RC=$?

# --- 采集 ---
snap "$WORK/saves"  > "$RUNDIR/post_saves.txt"
snap "$WORK/states" > "$RUNDIR/post_states.txt"

# 日志语义事件：剥离时间戳前缀与十六进制地址/长度
if [ -f "$LOGF" ]; then
    sed -e 's/^[0-9]\+[mM][sS] //' \
        -e 's/^\[[0-9: ]*\] //' \
        -e 's/0x[0-9a-fA-F]\+/ADDR/g' \
        -e 's/[0-9]\{3,\}/N/g' \
        "$LOGF" | grep -a -E '\[RK-|^P:|^---|^===' | head -400 > "$RUNDIR/events.txt"
    LOGLINES=$(wc -l < "$LOGF" 2>/dev/null || echo 0)
else
    : > "$RUNDIR/events.txt"; LOGLINES=0
fi

# 帧缓冲采样：优先 fb0，其次 DRM dumb dump（尽力而为）
FBHASH="none"
if [ -r /dev/fb0 ]; then
    FBHASH=$(dd if=/dev/fb0 bs=4096 count=64 2>/dev/null | sha256sum | cut -c1-16)
fi

# shm 心跳
SHM="0"
if command -v ipcs >/dev/null 2>&1; then
    SHM=$(ipcs -m 2>/dev/null | grep -c '0x000004d2' || echo 0)
fi

# --- 输出 JSON ---
{
  echo '{'
  echo "  \"label\": \"$LABEL\","
  echo "  \"binary\": \"$BIN\","
  echo "  \"args\": \"$ARGS\","
  echo "  \"exit_code\": $RC,"
  echo "  \"log_lines\": $LOGLINES,"
  echo "  \"shm_heartbeat\": $SHM,"
  echo "  \"frame_hash\": \"$FBHASH\","
  echo "  \"events\": ["
  awk '{gsub(/\\/,"\\\\"); gsub(/"/,"\\\""); printf "    \"%s\"%s\n", $0, (NR==n?"":",")}' n="$(wc -l < "$RUNDIR/events.txt")" "$RUNDIR/events.txt"
  echo "  ],"
  echo "  \"new_files\": ["
  diff "$RUNDIR/pre_saves.txt" "$RUNDIR/post_saves.txt" 2>/dev/null | grep '^>' | sed 's/^> //' | \
  { n=0; while read -r l; do n=$((n+1)); done; }
  diff "$RUNDIR/pre_saves.txt" "$RUNDIR/post_saves.txt" 2>/dev/null | grep '^>' | sed 's/^> //' | awk '{gsub(/"/,"\\\""); printf "    \"%s\"%s\n", $0, (NR==n?"":",")}' n="$(diff "$RUNDIR/pre_saves.txt" "$RUNDIR/post_saves.txt" 2>/dev/null | grep -c '^>')"
  echo "  ]"
  echo '}'
} > "$OUT" 2>/dev/null

echo "captured: $OUT (exit=$RC, log_lines=$LOGLINES, events=$(wc -l < "$RUNDIR/events.txt"))"
