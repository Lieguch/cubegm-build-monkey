#!/bin/sh
# =============================================================================
# cnb_ws_fetch.sh —— 从 CNB 云开发工作区**可靠取回**文件（分块 + sha256 对账）。
#
# ## 为什么不能直接 `ssh A 'cat file' > local`
# 2026-09-29 实测（三次）：CNB 的 SSH 通道**会把较大的 stdout 流截断**——
#   · 同会话回传 tar：2,621,440 B / 3,407,872 B 处截断（且是整 MiB 边界）
#   · 独立连接 `cat` 一个 5,442,408 B 的文件：只取到 **3,670,016 B**
#   ⇒ 这不是 tar 的问题，是**通道对流大小有限制**。截断是**静默**的（ssh rc 仍为 0）。
#
# ## 做法（把不确定性从关键路径上摘掉）
#   ① 先 `stat` 拿远端真实大小；
#   ② 按 `CHUNK`（默认 1 MiB）逐块 `dd skip=/count=` 单独取，每块一次短连接；
#   ③ 本地拼接后 **sha256 必须与远端一致**，不一致 ⇒ 失败（fail-closed，不交出半截文件）。
#
# 用法:  sh tools/cnb_ws_fetch.sh <user@host> <远端路径> <本地路径> [远端期望 sha256]
# 退出码: 0 成功 / 12 SHA 不符 / 13 大小不符 / 9 参数缺失
# =============================================================================
set -u
A="${1:-}"; RP="${2:-}"; LP="${3:-}"; WANT="${4:-}"
[ -n "$A" ] && [ -n "$RP" ] && [ -n "$LP" ] || { echo "用法: $0 <user@host> <远端路径> <本地路径> [sha256]" >&2; exit 9; }
CHUNK="${CHUNK:-1048576}"

SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=30"

SZ=$(timeout 120 ssh $SSHOPT "$A" "stat -c%s '$RP'" 2>/dev/null | tr -d '\r\n ')
case "${SZ:-}" in
    ''|*[!0-9]*) echo "!! 取不到远端大小：$RP" >&2; exit 9 ;;
esac
echo "   远端 $RP = $SZ B"

# 空文件直接产出
if [ "$SZ" = "0" ]; then : > "$LP"; echo "   （空文件）"; return 0 2>/dev/null || exit 0; fi

N=$(( (SZ + CHUNK - 1) / CHUNK ))
echo "   分 $N 块（每块 $CHUNK B）"
: > "$LP"
i=0
while [ "$i" -lt "$N" ]; do
    timeout 180 ssh $SSHOPT "$A" "dd if='$RP' bs=$CHUNK skip=$i count=1 2>/dev/null" >> "$LP" 2>/dev/null
    GOT=$(stat -c%s "$LP")
    printf '\r   块 %d/%d  已收 %d/%d B' $((i + 1)) "$N" "$GOT" "$SZ"
    i=$((i + 1))
done
echo
GOT=$(stat -c%s "$LP")
[ "$GOT" = "$SZ" ] || { echo "!! 大小不符：本地 $GOT ≠ 远端 $SZ" >&2; exit 13; }
if [ -n "$WANT" ]; then
    MY=$(sha256sum "$LP" | cut -d' ' -f1)
    [ "$MY" = "$WANT" ] || { echo "!! sha256 不符：$MY ≠ $WANT" >&2; exit 12; }
    echo "   ✓ sha256 对账通过 $MY"
fi
echo "   ✓ $LP（$GOT B）"
