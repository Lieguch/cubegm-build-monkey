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

# 3) 就地安装（CI 可联网）
# ★★ 2026-11-04：补 PEP 668（externally-managed-environment）口径 —— 原链只有
#   `--user` → 系统级 两档，在 **Debian 13 / 任意 PEP 668 发行版**上两档都被拒
#   （`error: externally-managed-environment`）⇒ 装不上 ⇒ fail-closed exit 5。
#   实测受害者：InstaBox（Debian 13 trixie）上 `link_full.sh` 直接失败 ⇒ **拿不到 ELF**
#   ⇒ 行为差分门禁无法起跑（同款坑此前在 CNB 云开发上踩过 pyyaml）。
#   ⇒ 根因修复：补 `--break-system-packages` 两档（优先 `--user`，不污染系统 site-packages），
#   再退到 venv（最干净）。**不改变"装不上就 fail-closed"的语义** —— 宁可红，不静默跳过。
echo "  [env] $PY 缺 pyelftools ⇒ 就地安装（幂等；CI 无预装）" >&2
_pkgs="pyelftools"
# 3.1 `--user`（CI Ubuntu 22.04 走这档）
"$PY" -m pip install --user --quiet "$_pkgs" >/dev/null 2>&1 || true
# 3.2 PEP 668：`--user --break-system-packages`（**Debian 13 实测走这档**）
#     ★ 关键：`--break-system-packages` 是 PEP 668 的开关；**只加 `--user` 不够**
#       （Debian 的 EXTERNALLY-MANAGED 标记连 `--user` 也拒）。
#     ★ 装进 `$PY` 自己的 user site ⇒ `$PY` 直接能 import ⇒ 满足本脚本契约
#       （"给到的 `$PY` 必须能用"）⇒ 调用方**无需**换解释器。
if ! "$PY" -c 'import elftools' >/dev/null 2>&1; then
    "$PY" -m pip install --user --break-system-packages --quiet "$_pkgs" >/dev/null 2>&1 || true
fi
# 3.3 PEP 668：系统级 + --break-system-packages（user site 不可写时的退路）
if ! "$PY" -c 'import elftools' >/dev/null 2>&1; then
    "$PY" -m pip install --break-system-packages --quiet "$_pkgs" >/dev/null 2>&1 || true
fi
# 3.4 老口径兜底（非 PEP 668 发行版的系统级安装）
if ! "$PY" -c 'import elftools' >/dev/null 2>&1; then
    "$PY" -m pip install --quiet "$_pkgs" >/dev/null 2>&1 || true
fi
# 3.5 venv（**仅当上面全失败**才用；装完用 .pth 把 venv 的 site-packages 挂进 `$PY` 的 user site，
#     这样 `$PY` 仍能 import ⇒ 不破坏本脚本契约。**不装就宣称成功** —— 那会让 $PY 依然缺依赖。）
if ! "$PY" -c 'import elftools' >/dev/null 2>&1 \
   && "$PY" -c 'import venv' >/dev/null 2>&1; then
    _VENV="${CGM_PYDEPS_VENV:-${TMPDIR:-/tmp}/rkgame-pydeps-venv}"
    rm -rf "$_VENV" >/dev/null 2>&1 || true
    if "$PY" -m venv "$_VENV" >/dev/null 2>&1 \
       && "$_VENV/bin/python" -m pip install --quiet "$_pkgs" >/dev/null 2>&1; then
        _VSP="$("$_VENV/bin/python" -c 'import sysconfig;print(sysconfig.get_paths()["purelib"])')"
        _USP="$("$PY" -c 'import site;print(site.getusersitepackages())')"
        if mkdir -p "$_USP" 2>/dev/null \
           && printf '%s\n' "$_VSP" > "$_USP/rkgame-pydeps.pth" 2>/dev/null \
           && "$PY" -c 'import elftools' >/dev/null 2>&1; then
            echo "  [env] pyelftools 经 venv 挂载到 \$PY 的 user site: $_VENV → $_USP/rkgame-pydeps.pth" >&2
        else
            rm -f "$_USP/rkgame-pydeps.pth" >/dev/null 2>&1 || true
            rm -rf "$_VENV" >/dev/null 2>&1 || true
        fi
    fi
fi

# 4) 装完仍缺 ⇒ **fail-closed**（绝不静默降级成"跳过门禁"）
if ! "$PY" -c 'import elftools' >/dev/null 2>&1; then
    echo "★★ 依赖仍缺失：$PY 无法 import elftools" >&2
    echo "   已试：--user / --user+--break-system-packages / --break-system-packages / 系统级 / venv+.pth" >&2
    echo "   ⇒ fail-closed（门禁不得静默跳过）" >&2
    exit 5
fi
echo "  [env] pyelftools 就绪（$PY）" >&2
exit 0
