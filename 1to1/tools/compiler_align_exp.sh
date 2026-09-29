#!/bin/sh
# ============================================================
# compiler_align_exp.sh —— 单变量实验：**把编译器切到工厂同期 GCC 6.3**
#
# ## 为什么必须做（2026-09-28 已把根因定位到编译期头文件）
# 链接已对齐（`LINK_DRIVER=lld` + 工厂同期 sysroot + 静态 libgcc.a）后，`.dynsym`
# 还剩两个**方向相反**的差异，两者是**同一个根因**：
#
#   工厂有 / 我方无（8）：
#     `_IO_putc` `_IO_getc` `__strdup` `islower`  ← glibc 2.24 的 **extern-inline**
#                                                     （只在 真 glibc 头 + GCC 下生效）
#     `_ITM_deregisterTMCloneTable` `_ITM_registerTMCloneTable`
#     `_Jv_RegisterClasses` `__gmon_start__`      ← GCC 的 `crtbegin/crtend.o` 弱引用
#   我方有 / 工厂无（6）：
#     `putc` `getc` `strdup` `mbsinit` `gmtime` `bcmp`  ← 同一条（zig 自带 glibc 头把 extern-inline 裁掉了）
#
# ## 平台约束（**实测，不是推测**）
# `cache_tc/bootlin63/bin/*-gcc` 是 **x86-64 Linux ELF** ⇒ 在 Windows 上
# `cannot execute binary file: Exec format error`。**本实验只能在 Linux（CI / CNB 云开发）跑。**
#
# ## 判据（单变量：只换编译器；链接驱动、sysroot、库、优化档、源码全部不动）
#   1) 编译 213/213 成功；
#   2) 链接 rc=0，且 DT_NEEDED 仍为 7 项同序；
#   3) `.dynsym` 的"工厂有/我方无"必须从 8 降到 ≤4（extern-inline 那 4 项被补上）；
#   4) **行为尺 DIVERGE 必须 < 基线**（基线由 `tools/ruler_baseline.py` 从**当前交付产物自己
#      的权威报告**里取，★ 不硬编码 —— 纪律 50），否则**回退编译器**。
#   ★ 纪律 43：体积/相似度类指标不算数，只有行为尺能背书。
#
# 用法（Linux）:  sh tools/compiler_align_exp.sh
# 退出码: 0 = 采用（见判据）/ 3 = 环境不可用 / 4 = 非 Linux / 5 = 编译失败 / 6 = 判据不达标
#         7 = 取不到行为尺基线（fail-closed，纪律 50）
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 9
PY="${PY:-python3}"

if [ "$(uname -s 2>/dev/null)" != "Linux" ]; then
    echo "★★ 本实验需要 Linux 主机：bootlin 的 gcc 是 x86-64 Linux ELF，Windows 上无法执行。" >&2
    echo "   请在 CI（gcc-vs-clang-fidelity workflow）或 CNB 云开发里跑。" >&2
    exit 4
fi

sh tools/fetch_bootlin63.sh || exit 3
GCC="$ROOT/cache_tc/bootlin63/bin/arm-buildroot-linux-gnueabihf-gcc"
GXX="$ROOT/cache_tc/bootlin63/bin/arm-buildroot-linux-gnueabihf-g++"
[ -x "$GCC" ] || { echo "!! 缺 $GCC" >&2; exit 3; }

echo "== 0) 编译器自证 =="
"$GCC" --version | head -1
echo "   sysroot = $("$GCC" -print-sysroot 2>/dev/null)"

echo "== 1) 头文件事实探针（决定 extern-inline 方向）=="
mkdir -p build/_probe
printf '#include <stdio.h>\nint f(FILE *fp){ return putc(32, fp); }\n' > build/_probe/putc.c
if "$GCC" -c -Os build/_probe/putc.c -o build/_probe/putc.o 2>/dev/null; then
    "$PY" - <<'PYE'
from elftools.elf.elffile import ELFFile
e = ELFFile(open('build/_probe/putc.o', 'rb'))
st = e.get_section_by_name('.symtab')
und = sorted({s.name for s in st.iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF'})
pick = [n for n in und if 'putc' in n]
print('   工厂形态应为 _IO_putc；实测 =', pick)
PYE
else
    echo "   !! 探针编译失败（头文件/编译器不可用）"
fi

echo "== 2) 编译专有对象（OBJD=build/gcc_obj）=="
rm -rf build/gcc_obj build/gcc_upstream build/gcc_xunzip.o
mkdir -p build/gcc_obj
OPT="${OPT:--Os}" CC="$GCC" OBJD="$ROOT/build/gcc_obj" UPOUT="${UPOUT:-$ROOT/build/gcc_upstream}" \
    XUPOBJ="$ROOT/build/gcc_xunzip.o" \
    sh tools/link_audit.sh report/_ca_link_audit.txt > report/_ca_compile.txt 2>&1
n_obj=$(ls -1 build/gcc_obj/*.o 2>/dev/null | wc -l)
echo "   专有对象 $n_obj/213"
[ "$n_obj" -ge 213 ] || { echo "★★ 编译失败（少于 213）" >&2; tail -20 report/_ca_compile.txt >&2; exit 5; }

echo "== 3) 编译上游（build/gcc_upstream）=="
CC="$GCC" PY="$PY" sh tools/build_upstream.sh build/gcc_upstream >> report/_ca_compile.txt 2>&1
echo "   上游对象 $(ls -1 build/gcc_upstream/*.o 2>/dev/null | wc -l)"

echo "== 4) 链接（ld.lld，库/sysroot 与主链完全一致）=="
LINK_DRIVER=lld \
  CC="$(echo "$GCC" )" SYSROOT="" PY="$PY" \
  DIAG_OBJD="$ROOT/build/gcc_obj" \
  UPOBJD="$ROOT/build/gcc_upstream" \
  DIAG_XUNZIP="$ROOT/build/gcc_xunzip.o" \
  sh tools/link_full.sh build/ab/gcc63.elf > report/_ca_link.txt 2>&1
rc=$?
echo "   link rc=$rc"
[ "$rc" = "0" ] || { echo "★★ 链接失败" >&2; tail -20 report/link_full_err.txt >&2; exit 5; }
"$PY" tools/probe_link_binding.py build/ab/gcc63.elf

echo "== 5) 行为尺（唯一判据）=="
# ★ 基线自证：从当前交付产物自己的权威报告取，取不到就 fail-closed（纪律 50）
BASE_LINE=$("$PY" tools/ruler_baseline.py) || { echo "★★ 取不到行为尺基线（纪律 50 fail-closed）" >&2; exit 7; }
BASE_DV=$(printf '%s\n' "$BASE_LINE" | awk '{print $5}')
echo "   基线与产物绑定：$BASE_LINE"
export BASE_DV BASE_LINE
"$PY" tools/diff_exec.py --batch --steps 3000 --ours build/ab/gcc63.elf \
    --out report/_ca_diff.txt > report/_ca_diff_stdout.txt 2>&1
grep -a '汇总：PASS' report/_ca_diff.txt

echo "== 6) 判决 =="
"$PY" - <<'PYE'
import io, os, re, sys
t = io.open('report/_ca_diff.txt', encoding='utf-8', errors='replace').read()
m = re.search(r'汇总：PASS\s+(\d+)\s*｜\s*DIVERGE\s+(\d+)', t)
if not m:
    print('   !! 解析失败'); sys.exit(6)
pa, dv = int(m.group(1)), int(m.group(2))
base = int(os.environ['BASE_DV'])
print('   基线（当前交付产物，%s）' % os.environ['BASE_LINE'])
print('   共有 %s ｜ PASS %d ｜ DIVERGE %d' % (re.search(r'共有函数\s+(\d+)', t).group(1), pa, dv))
if dv < base:
    print('   ★ 判决：**采用**（GCC 6.3）—— DIVERGE %d < 基线 %d' % (dv, base))
    v = 'ADOPT'
else:
    print('   ★ 判决：**不采用**（DIVERGE 未下降：%d >= 基线 %d）⇒ 回退编译器，记录原因' % (dv, base))
    v = 'REJECT'
io.open('report/compiler_align_verdict.txt', 'w', encoding='utf-8').write(
    '%s gcc63: PASS %d DIVERGE %d (baseline %d, %s)\n'
    % (v, pa, dv, base, os.environ['BASE_LINE'].strip().split()[-1]))
PYE
echo "（判据文件：report/compiler_align_verdict.txt）"
