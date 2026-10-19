#!/usr/bin/env sh
# ============================================================
# run_gates.sh —— rkgame 复刻机械门禁统一入口（R200）
#
# 为什么需要：R195–R199 新建了 4 个本机可跑的判据工具，但**没有统一入口**
#   ⇒ 每轮"跑哪些门禁"靠记忆 ⇒ 必然漏跑（本项目已因这类事多次吃亏）。
#   本脚本把"本机可执行的全部判据"固化为**一条命令**，每轮结束跑一次。
#
# 覆盖（全部本机可跑，**不占云开发额度**，遵守纪律 173）：
#   1. `core_dlsym_gate.py`     —— core 加载器 dlsym 清单（18/18）+ 三腿自证
#   2. `test_core_selector.py`   —— core 选择器三层判据（23 用例）
#   3. `_r195_symdiff.py`        —— driver.so 符号族 diff + 调用图（强 UNDEF 零缺口）
#
# 用法:
#   sh tools/run_gates.sh            # 跑全部
#   sh tools/run_gates.sh --quiet    # 只打摘要
#
# 退出码：0 = 全过；1 = 有失败（并列出失败项）
# ============================================================
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-}"
# 优先用带 pyelftools/capstone 的 managed venv（本机系统 python 没有这两个包）
if [ -z "$PY" ]; then
    for cand in \
        "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
        "/c/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
        python3 python; do
        if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
    done
fi
[ -n "$PY" ] || { echo "!! 找不到 python" >&2; exit 9; }

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

FAILED=""
run_one() {
    _name="$1"; _script="$2"; shift 2
    if [ "$QUIET" = "1" ]; then
        if "$PY" "$ROOT/tools/$_script" "$@" >/dev/null 2>&1; then
            echo "  ✅ $_name"
        else
            echo "  ❌ $_name"
            FAILED="$FAILED $_name"
        fi
    else
        echo "======== $name ========"
        if "$PY" "$ROOT/tools/$_script" "$@"; then
            :
        else
            FAILED="$FAILED $_name"
        fi
        echo
    fi
}

echo "=== rkgame 机械门禁（R200 统一入口） PY=$PY ==="
run_one "core_dlsym 清单门禁"   core_dlsym_gate.py
run_one "core 选择器三层判据"   test_core_selector.py
run_one "driver.so 符号族 diff" _r195_symdiff.py

echo "=== 汇总 ==="
if [ -n "$FAILED" ]; then
    echo "  ❌ 失败:$FAILED" >&2
    exit 1
fi
echo "  ✅ 全部门禁通过（本机可跑部分，未含需云开发的项）"
exit 0
