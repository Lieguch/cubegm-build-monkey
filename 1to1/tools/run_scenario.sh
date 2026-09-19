#!/bin/sh
# ============================================================
# run_scenario.sh — 在本地（CNB 容器）跑一个行为场景，env **从 workflow 现解析**
#
# 为什么这样设计：
#   手工把 CI 的 env 抄到本地，必然漂移 —— 2026-09-19 实测：漏抄
#   `CGM_KEY2_SEED/HOOK/PROBE` + `CGM_IO_TRACE` 后，`ui_cn.zip` 根本打不开
#   （M6 从 ✓ 变 ✗），覆盖率 76→48，整条执行流在启动处就分叉，
#   得到的是"本地不复现"的假结论。所以本脚本**不维护自己的 env 表**，
#   而是用 python3 现场解析 .github/workflows/1to1-qemu-behav.yml 里对应步骤的
#   `SYSROOT=... \` 续行块，把开关原样喂给 tools/ci_qemu_behav.sh。
#   ⇒ CI 与本地**构造性一致**（CI 改了 env，本地立刻跟着变，无需同步）。
#
# 用法：
#   sh tools/run_scenario.sh <A|C|J|M|N|O|P>
#   sh tools/run_scenario.sh -l            # 列出 workflow 里所有场景及其 env
#   sh tools/run_scenario.sh -c J          # 只打印 J 的解析结果，不执行
#
# 前置：sh tools/cnb_env.sh
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
WF=".github/workflows/1to1-qemu-behav.yml"

extract() {   # $1 = 场景字母或 A
  python3 - "$WF" "$1" <<'PYEOF'
import io, re, sys
wf, sc = sys.argv[1], sys.argv[2]
NL = chr(10)
s = io.open(wf, encoding='utf-8').read().replace(chr(13)+NL, NL)
# 按步骤切块：以 "      - name:" 开头
blocks = re.split(r'\n(?=      - name:)', s)
hits = []
for b in blocks:
    m = re.match(r'      - name:\s*(.*)', b)
    if not m:
        continue
    name = m.group(1).strip()
    if sc == 'A':
        if '行为采集 + 差分' not in name:
            continue
    else:
        if ('场景 ' + sc) not in name:
            continue
    hits.append((name, b))
if not hits:
    print('__ERR__ 未在 workflow 里找到场景 %s 的步骤' % sc)
    sys.exit(1)
name, b = hits[0]
print('#STEP# ' + name)
# 抽取 run 块里所有 KEY=VAL 赋值（只取 CGM_* 与 SYSROOT），拼接续行
run = b.split('run:', 1)[1] if 'run:' in b else b
run = re.sub(r'\\\s*\n\s*', ' ', run)          # 合并 `\` 续行
toks = []
for m in re.finditer(r'\b(CGM_[A-Z0-9_]+|SYSROOT)=([^\s]+)', run):
    k, v = m.group(1), m.group(2).strip('"')
    if k == 'SYSROOT':
        continue                                # 本地固定为 /arm-root
    if (k, v) not in toks:
        toks.append((k, v))
print('#ENV# ' + ' '.join('%s=%s' % (k, v) for k, v in toks))
# 顺带把该步骤后面的判定性 grep 也列出来，方便本地照做
for m in re.finditer(r'grep -a[^\n]*', run):
    t = m.group(0).strip()[:110]
    if t not in (None, ''):
        print('#CHK# ' + t)
PYEOF
}

if [ "${1:-}" = "-l" ]; then
  echo "== workflow 里所有行为场景 =="
  for sc in A C J M N O P; do
    out="$(extract "$sc" 2>&1)" || { echo "  $sc: 未找到"; continue; }
    echo "  --- 场景 $sc"
    echo "$out" | sed 's/^/     /'
  done
  exit 0
fi

if [ "${1:-}" = "-c" ]; then
  extract "${2:?usage: run_scenario.sh -c <A|C|J|M|N|O|P>}" | sed 's/^/  /'
  exit 0
fi

SC="${1:?usage: run_scenario.sh <A|C|J|M|N|O|P> | -l | -c X}"
OUT="report/qemu_$(echo "$SC" | tr 'A-Z' 'a-z')"

PARSED="$(extract "$SC")" || { echo "★ 场景解析失败：$SC"; echo "$PARSED"; exit 2; }
STEP="$(printf '%s' "$PARSED" | sed -n 's/^#STEP# //p')"
ENVS="$(printf '%s' "$PARSED" | sed -n 's/^#ENV# //p')"

[ -f build/rkgame.rebuilt.elf ] || { echo "★ 缺 build/rkgame.rebuilt.elf —— 先跑 sh tools/cnb_env.sh"; exit 1; }
[ -d /sdcard/cubegm ] || { echo "★ 缺 /sdcard/cubegm —— 先跑 sh tools/cnb_env.sh"; exit 1; }
[ -f /tmp/cgm_env.sh ] && . /tmp/cgm_env.sh

echo "== 场景 $SC （解析自 workflow，零手抄）"
echo "   步骤: $STEP"
echo "   env : $ENVS"
echo "   输出: $OUT"
echo

# shellcheck disable=SC2086
env SYSROOT=/arm-root $ENVS \
  sh tools/ci_qemu_behav.sh build/rkgame.rebuilt.elf golden/factory.rkgame.bin "$OUT" 2>&1 | tail -30

echo
echo "== 覆盖率 =="
grep -aE "已执行" "$OUT/coverage_rebuild.txt" 2>/dev/null | head -1 | sed 's/^/   我们: /'
grep -aE "已执行" "$OUT/coverage_factory.txt" 2>/dev/null | head -1 | sed 's/^/   工厂: /'
echo
echo "== .dat 路径（单点可判定观测量）=="
for s in factory rebuild; do
  printf "   [%-7s] " "$s"
  grep -a "\.dat" "$OUT/rundir_$s/stdout.txt" 2>/dev/null | sort -u | head -3 | tr '\n' ' '
  echo
done
echo
echo "== 里程碑 =="
sed -n '/ID     里程碑/,/MX/p' "$OUT/milestones.txt" 2>/dev/null | sed 's/^/  /'
