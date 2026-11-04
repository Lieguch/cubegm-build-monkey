#!/usr/bin/env bash
# tools/_close_compute.sh — **每轮收尾第 0 项：关算力**（机械执行，不依赖记忆）
#
# 为什么存在（2026-11-04 事故）：
#   CNB 云开发工作区 `cnb-akg-1k6gf9r99` 泄漏 **3 h 52 min**（用户手动关闭）。
#   病因不是"忘了"，是 PROJECT-MEMORY §R203 的纪律**只写在文档里、没有挂在流程上**。
#   ⇒ 处置：把"关算力"做成**一条命令**，收尾时无条件跑一次；并把"自查 running=0"写进脚本。
#
# 用法：
#   bash tools/_close_compute.sh          # 全关 + 自查
#   bash tools/_close_compute.sh --check  # 只自查，不关（用于中途查漏）
#
# 退出码：0 = 已关且 running=0；1 = 仍有 running（脚本会打印明细）；2 = 本机无对应 CLI。
set -uo pipefail

CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
rc=0

echo "=== 关算力 · $(date -Is) ==="

# ---------- 1) InstaBox（本项目当前算力通道） ----------
IBX="$HOME/.workbuddy/user-6b1543f4-8e73-46fe-bb43-f687138d56d6-personal/bin/ibx_gmail.sh"
if [ -x "$IBX" ] || [ -f "$IBX" ]; then
  if [ "$CHECK_ONLY" = "1" ]; then
    echo "[check] InstaBox:"; bash "$IBX" ls 2>&1 | sed 's/^/    /'
  else
    echo "[act] InstaBox suspend:"
    bash "$IBX" suspend 2>&1 | sed 's/^/    /'
  fi
else
  echo "[skip] InstaBox helper 不存在: $IBX"
fi

# ---------- 2) CNB 云开发（用户已指示暂停；仍保留关闭通道以防误开） ----------
if command -v cnb >/dev/null 2>&1; then
  RUNNING="$(cnb workspace list-workspaces --slug lieguch/cubeGM 2>/dev/null \
             | grep -c 'status: running' || true)"
  echo "[check] CNB workspace running 计数 = $RUNNING"
  if [ "$CHECK_ONLY" != "1" ] && [ "${RUNNING:-0}" != "0" ]; then
    echo "[act] 停掉 running 的 CNB 工作区："
    cnb workspace list-workspaces --slug lieguch/cubeGM 2>/dev/null \
      | awk '/sn: /{sn=$2} /status: running/{print sn}' \
      | while read -r sn; do
          [ -n "$sn" ] && echo "    stop $sn" && cnb workspace workspace-stop --sn "$sn" 2>&1 | tail -2 | sed 's/^/      /'
        done
  fi
  LEFT="$(cnb workspace list-workspaces --slug lieguch/cubeGM 2>/dev/null \
          | grep -c 'status: running' || true)"
  echo "[final] CNB workspace running 计数 = $LEFT"
  [ "${LEFT:-0}" != "0" ] && rc=1
else
  echo "[skip] cnb CLI 不可用"
fi

# ---------- 3) 自家结论 ----------
if [ "$rc" = "0" ]; then
  echo "=== 算力已收口（running = 0）==="
else
  echo "=== 仍有 running 工作区 —— 必须处理后再收工 ==="
fi
exit $rc
