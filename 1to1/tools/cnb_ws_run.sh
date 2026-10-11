#!/bin/sh
# =============================================================================
# cnb_ws_run.sh —— 在 CNB 云开发工作区里跑**一条命令**（第 163 轮新增）。
#
# 与 cnb_ws_gates.sh 的区别：
#   · 不上传任何文件（工作区里已有从远端 clone 的仓库），省掉 5MB+ 的产物上传；
#   · 执行前先 `git fetch + reset --hard origin/main` ⇒ 保证工作区是最新主干；
#   · 命令由参数指定，不限于门禁清单（可跑任意"纯计算"的活：构建实验、门禁复跑）。
#
# 为什么需要它（第 163 轮）
#   假桩产物级门禁（driver_stub_elf_gate.sh）需要 armhf 交叉编译器 + objcopy，
#   本机 Windows 没有；CNB 云开发是唯一能在 CI 之外跑它的平台。
#   而它不需要 build/rkgame.rebuilt.elf，用 cnb_ws_gates.sh 会被它的"必须先有产物"
#   前置挡掉，且白白上传一遍 tools/。
#
# 用法:
#   sh tools/cnb_ws_run.sh 'sh tools/driver_stub_elf_gate.sh'
#   WS_SSH=user@host sh tools/cnb_ws_run.sh '...'      # 复用已开的工作区
#   WS_SN=cnb-xxx sh tools/cnb_ws_run.sh '...'         # 指定 sn，自动取 ssh
# =============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CNB_DIR="/c/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/cnb"
export PATH="$PATH:$CNB_DIR"
REPO="lieguch/cubeGM"
CMD="${1:?usage: cnb_ws_run.sh '<remote shell command>'}"

A="${WS_SSH:-}"
SN="${WS_SN:-}"

if [ -z "$A" ] && [ -z "$SN" ]; then
    echo "== 1) 开工作区 =="
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
    echo "   sn=${SN:-?}"
    if [ -z "$SN" ]; then
        echo "   原始输出（供排查）："; printf '%s\n' "$OUT" | sed 's/^/     /' | head -20
        echo "!! 未取到 sn（可用 WS_SN=<cnb-...> 或 WS_SSH=<user@host> 直接指定）" >&2
        exit 13
    fi
fi

if [ -z "$A" ]; then
    echo "== 2) 等 SSH 就绪 =="
    i=0
    while [ "$i" -lt 20 ]; do
        D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
        A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
        i=$((i + 1)); [ -n "$A" ] || sleep 12
    done
fi
[ -n "$A" ] || { echo "!! 未取到 ssh 地址" >&2; exit 13; }
echo "   ssh=$A"

echo "== 3) 同步到最新主干并执行 =="
timeout 1700 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    -o BatchMode=yes -o ConnectTimeout=25 "$A" \
    "set -u
     for d in /workspace/1to1 /workspace/1to1/* /workspace; do
         [ -d \"\$d/tools\" ] && PROJ=\$d && break
     done
     echo \"PROJ=\${PROJ:-未找到}\"
     cd \"\$PROJ\" || exit 9
     git fetch -q origin main 2>/dev/null || echo '   (fetch 失败，用工作区现有内容)'
     git reset --hard -q origin/main && echo \"   HEAD=\$(git rev-parse --short HEAD)\"
     echo '--- 执行 ---'
     $CMD
     echo REMOTE-DONE" 2>&1 | tail -70
echo "== 完成（工作区 $SN 约 15 分钟后自动关闭）=="
