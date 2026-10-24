#!/bin/sh
# ============================================================
# local_precheck.sh —— 本地「门禁全集」预检（R286）
#
# 为什么存在（真实代价）：
#   R268 的完工判据只有一层「214/214 编译零错误」⇒ 宣布 terminal state；
#   而同一批改动里 3 处调用点偏离了工厂调用表达式（scan_call_args 能抓）、
#   22 处类型错（严格类型轨能抓）、3 个上游符号被内联（s48 能抓）。
#   ⇒ 单层通过被当成"全绿"，把 CI 当第一道验证，白烧 5 轮 Actions。
#
# 本脚本把 CI 的四层判据搬到本地一次跑完（零带宽、不产出正式物）：
#   L1 arity          编译一致性（check_arity_compile.sh）
#   L2 严格类型轨       -Werror=int-conversion/incompatible-pointer-types（复刻 CI s20）
#   L3 上游补丁在场      3 处 noinline + SVG API 应 absent（复刻 CI s48/s26 的符号面）
#   L4 单侧符号/导入表    bcmp 等"工厂没有、我们有"的导入（构建口径污染探针）
#
# 用法：sh tools/local_precheck.sh [--fast]
#   退出码 0 = 四层全过；非 0 = 该层编号
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ZIG="${ZIG:-C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Lib/site-packages/ziglang/zig.exe}"
PY="${PY:-python}"
ELF="$ROOT/build/rkgame.rebuilt.elf"

echo "================ L1 arity（编译一致性）================"
L1LOG="$ROOT/report/_precheck_L1.txt"
sh "$ROOT/tools/check_arity_compile.sh" > "$L1LOG" 2>&1
L1RC=$?
tail -2 "$L1LOG"
[ "$L1RC" = "0" ] || { echo "L1 FAIL (rc=$L1RC)"; exit 1; }

echo "================ L2 严格类型轨（CI s20 同口径）================"
L2LOG="$ROOT/report/_precheck_L2.txt"
sh "$ROOT/tools/_r284_strict_werror_scan.sh" > "$L2LOG" 2>&1
tail -2 "$L2LOG"
n_err=$(grep -cE "error:" "$ROOT/report/_r284_strict_werror.txt" 2>/dev/null)
n_err=${n_err:-0}
echo "  严格类型轨 error 行数 = $n_err"
[ "$n_err" -eq 0 ] || { echo "L2 FAIL"; exit 2; }

echo "================ L3 上游补丁在场（s48/s26 符号面）================"
"$PY" - "$ELF" <<'PYEOF' || exit 3
import sys
from elftools.elf.elffile import ELFFile
e = ELFFile(open(sys.argv[1], 'rb'))
sym = {s.name: s['st_size'] for s in e.get_section_by_name('.symtab').iter_symbols() if s.name}
need = ['stbtt__csctx_rline_to', 'stbtt__cuberoot', 'stbtt__rasterize_sorted_edges']
bad = [n for n in need if n not in sym]
if bad:
    print('  FAIL 缺 noinline 符号:', bad); sys.exit(3)
print('  OK noinline 符号在场:', {n: sym[n] for n in need})
gone = [n for n in ('stbtt_FindSVGDoc', 'stbtt_GetCodepointSVG', 'stbtt_GetGlyphSVG') if n in sym]
if gone:
    print('  FAIL v1.22 不应有 SVG API:', gone); sys.exit(3)
print('  OK SVG API 均 absent（v1.22 形态）')
PYEOF

echo "================ L4 导入表污染探针（bcmp 等单侧符号）================"
"$PY" - "$ELF" "$ROOT/golden/factory.rkgame.bin" <<'PYEOF' || exit 4
import sys
from elftools.elf.elffile import ELFFile
def imports(p):
    e = ELFFile(open(p, 'rb'))
    return set(s.name for s in e.get_section_by_name('.dynsym').iter_symbols() if s.name)
ours, fac = imports(sys.argv[1]), imports(sys.argv[2])
# bcmp：clang 把 strcmp(x,"lit")==0 变成 bcmp；工厂 GCC 不做 ⇒ 出现即口径污染
suspect = ['bcmp']
bad = [s for s in suspect if s in ours and s not in fac]
if bad:
    print('  FAIL 我方导入工厂没有的符号（口径污染，常见于旧 build/obj）:', bad)
    print('       修法：用 link_audit 口径重编（带 -fno-builtin-strcmp）后重链')
    sys.exit(4)
print('  OK 无单侧污染符号（bcmp: %s）' % ('absent' if 'bcmp' not in ours else 'present-both'))
PYEOF

echo "================ LOCAL PRECHECK: ALL 4 LAYERS PASS ================"
