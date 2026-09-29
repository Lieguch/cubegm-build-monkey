#!/bin/sh
# =============================================================================
# ca_judge.sh —— 「编译器对齐」实验的**本机判据**（行为尺）。
#
# ## 为什么这里才判
# 云开发（Linux）只承担**只有它能做的那一段**：用 bootlin63 的 GCC 6.3 交叉编译 + 用 ld.lld 链接，
# 产出 `build/ab/gcc63.elf`。行为尺（`diff_exec.py`，Unicorn 纯用户态模拟）**在本机 Windows 一样能跑**，
# 且单跑一次约 5 分钟 —— 放在云上只会白占会话时间、放大超时风险。
# ⇒ 云上跑 `CA_SKIP_RULER=1 sh tools/_ca_all.sh`，再用本脚本判。
#
# ## 判据（纪律 43 + 50）
#   · 唯一判据 = 行为尺 **DIVERGE**；
#   · 基线**不硬编码** —— 由 `tools/ruler_baseline.py` 从「**当前交付产物自己的权威报告**」取，
#     随产物 sha 自失效；取不到 ⇒ **fail-closed**。
#   · DIVERGE < 基线 ⇒ ADOPT（GCC 6.3 采纳）；否则 REJECT（回退编译器）。
#
# 退出码: 0 = ADOPT / 1 = REJECT / 6 = 解析失败 / 7 = 取不到基线 / 9 = 前置缺失
# 用法:   sh tools/ca_judge.sh
# =============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 9

# ★ 解释器自证（2026-09-29 踩到）：系统 `python` 上没有 unicorn ⇒ 尺子静默不产出报告。
#   统一解析口径：显式 PY > 隔离 venv（本机）> PATH。解析不到就 fail-closed 并指名。
_find_py() {
    if [ -n "${PY:-}" ]; then printf '%s' "$PY"; return; fi
    for c in \
        "C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
        "$HOME/.workbuddy/binaries/python/envs/default/bin/python3" \
        python3 python; do
        command -v "$c" >/dev/null 2>&1 || [ -x "$c" ] || continue
        if "$c" -c 'import unicorn,capstone,elftools' >/dev/null 2>&1; then printf '%s' "$c"; return; fi
    done
}
PY="$(_find_py)"
[ -n "${PY:-}" ] || {
    echo "!! 找不到带 unicorn/capstone/pyelftools 的解释器 ⇒ fail-closed（不得静默退出）" >&2
    echo "   修：PY=<python> sh tools/ca_judge.sh，或 pip install unicorn capstone pyelftools" >&2
    exit 8
}
echo "   解释器 = $PY"

ART="${ART:-build/ab/gcc63.elf}"
[ -s "$ART" ] || { echo "!! 缺实验产物 $ART（先在云开发里跑 CA_SKIP_RULER=1 sh tools/_ca_all.sh 并取回）" >&2; exit 9; }
echo "   实验产物 $ART  sha256=$(sha256sum "$ART" | cut -d' ' -f1)"

echo "== 基线自证（纪律 50）=="
BASE_LINE=$("$PY" tools/ruler_baseline.py) || { echo "★★ 取不到行为尺基线 ⇒ fail-closed" >&2; exit 7; }
BASE_DV=$(printf '%s\n' "$BASE_LINE" | awk '{print $5}')
echo "   $BASE_LINE"
export BASE_DV BASE_LINE

echo "== 行为尺（唯一判据）=="
"$PY" tools/diff_exec.py --batch --steps 3000 --ours "$ART" \
    --out report/_ca_diff.txt > report/_ca_diff_stdout.txt 2>&1
grep -a '共有函数\|汇总：PASS\|自洽校验' report/_ca_diff.txt

echo "== 判决 =="
"$PY" - <<'PYE'
import io, os, re, sys
t = io.open('report/_ca_diff.txt', encoding='utf-8', errors='replace').read()
m = re.search(r'汇总：PASS\s+(\d+)\s*｜\s*DIVERGE\s+(\d+)', t)
n = re.search(r'共有函数\s+(\d+)', t)
if not m:
    print('   !! 解析失败'); sys.exit(6)
pa, dv = int(m.group(1)), int(m.group(2))
base = int(os.environ['BASE_DV'])
print('   共有 %s ｜ PASS %d ｜ DIVERGE %d ｜ 基线 %d' % (n.group(1) if n else '?', pa, dv, base))
print('   基线出处：%s' % os.environ.get('BASE_LINE', '').strip())
v = 'ADOPT' if dv < base else 'REJECT'
print('   ★ 判决：%s（DIVERGE %d vs 基线 %d）' % (v, dv, base))
io.open('report/compiler_align_verdict.txt', 'w', encoding='utf-8').write(
    '%s gcc63: PASS %d DIVERGE %d (baseline %d)\n' % (v, pa, dv, base))
sys.exit(0 if v == 'ADOPT' else 1)
PYE
