#!/bin/sh
# ============================================================
# ensure_pydeps.sh —— 门禁依赖**自足引导**（幂等）。
#
# 为什么需要它
# ------------
# ★ 纪律 71：**CI 需要的输入必须在脚本内自足** —— 不能假设"workflow 已经装好依赖"。
#   本仓 `.github/workflows/` 因本机代理拦截**无法推送修改**，任何"靠 workflow 装依赖"
#   的假设都会变成**永远不满足的前置**。
# ★ 纪律 69：**同一规则只写一处** —— 依赖引导此前散落在 link_full.sh / link_audit.sh
#   各自的"兜底找 venv"逻辑里，两处都只找**本机路径**、都不装 ⇒ CI 上必然 exit 5。
#
# 病灶（CI 实测，commit `0e14448f`）
# ---------------------------------
#   `link_full.sh` 报「★★ 门禁依赖缺失：PY=python3 无法 import elftools」⇒ exit 5
#   ⇒ `1to1-verify` #233 / `1to1-qemu-behav` #201 连锁红。
#
# 用法
# ----
#   PY=python3 sh tools/ensure_pydeps.sh || exit $?
# 退出码：0 = 依赖就绪；5 = 装不上（**fail-closed**，不静默降级）
# ============================================================
set -u
PY="${PY:-python3}"

# 1) 已就绪 ⇒ 直接返回（幂等，本地零开销）
if "$PY" -c 'import elftools' >/dev/null 2>&1; then
    exit 0
fi

# 2) **解释器选择不归本脚本管** —— 调用方（如 `link_full.sh`）已负责"在本机可选解释器里
#    挑一个含 pyelftools 的"（那需要改它自己的 `$PY` 变量，只能由它做）。
#    本脚本只负责：**给到的 `$PY` 必须能用** —— 不能就装，装不上就 fail-closed。

# 3) 就地安装（CI 可联网；`--user` 优先，失败再试系统级）
echo "  [env] $PY 缺 pyelftools ⇒ 就地安装（幂等；CI 无预装）" >&2
"$PY" -m pip install --user --quiet pyelftools >/dev/null 2>&1 \
    || "$PY" -m pip install --quiet pyelftools >/dev/null 2>&1 \
    || true

# 4) 装完仍缺 ⇒ **fail-closed**（绝不静默降级成"跳过门禁"）
if ! "$PY" -c 'import elftools' >/dev/null 2>&1; then
    echo "★★ 依赖仍缺失：$PY 无法 import elftools（已试 --user 与系统级 pip）" >&2
    echo "   ⇒ fail-closed（门禁不得静默跳过）" >&2
    exit 5
fi
echo "  [env] pyelftools 就绪（$PY）" >&2
exit 0
