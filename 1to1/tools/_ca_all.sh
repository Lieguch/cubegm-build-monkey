#!/bin/sh
# ============================================================
# _ca_all.sh —— CNB 云开发环境里的「编译器对齐」一键实验（可在 workspace 里 nohup 跑）
#
# 目的（单变量）：把编译器从 clang/zig 换成 **GCC 族**，其余（链接驱动、sysroot、库、
#   优化档、源码）全部不动，看
#     ① `.dynsym` 的"工厂有/我方无"是否从 8 降到 ≤4（glibc extern-inline 那 4 项）
#     ② **行为尺 DIVERGE 是否 < 基线**。基线**不硬编码**（纪律 50）：
#        优先用环境变量 `BASE_DV`（由本机 `tools/ruler_baseline.py` 从**当前交付产物自己的
#        权威报告**里取，随产物 sha 自失效）；未给则就地调 `tools/ruler_baseline.py`；
#        **两者都取不到 ⇒ fail-closed（exit 7）**，绝不回退到抄来的数字。
#
# 编译器选择（**只准工厂同期，缺则 fail-closed**）：
#   · 若 `cache_tc/bootlin63/.ok` 不存在 ⇒ **就地** `sh tools/fetch_bootlin63.sh` 抓取；
#   · 抓不到 ⇒ **exit 3**（**不回落** apt 的 GCC —— 那会同时改编译器与 glibc 两个变量，
#     判决不可用；要用必须显式 `CA_ALLOW_CONFOUND=1`，并在结论里降级表述）。
#   · bootlin63 = GCC 6.3 / glibc 2.24 / binutils 2.27（工厂 = GCC 6.2.0 / gold 1.12 / glibc 2.24）
#
# 用法:  nohup sh tools/_ca_all.sh > /tmp/ca.log 2>&1 &
#       然后 tail -f /tmp/ca.log
# ============================================================
set -u
cd /workspace/1to1 2>/dev/null || cd "$(cd "$(dirname "$0")/.." && pwd)" || exit 9
ROOT="$PWD"
PY=python3
LOG="$ROOT/report/_ca_all.txt"
mkdir -p build/gcc_obj build/gcc_upstream build/ab report
: > "$LOG"
say() { echo "$@" | tee -a "$LOG"; }

say "############ 编译器对齐实验 $(date -u +%H:%M:%S) ############"

# ---- 0) 依赖自证 -------------------------------------------------------------
say "== 0) 依赖 =="
$PY - <<'PYE' | tee -a "$LOG"
import sys
ok = True
for m in ('elftools', 'capstone', 'unicorn'):
    try:
        __import__(m); print('   %-10s OK' % m)
    except Exception as e:
        ok = False; print('   %-10s **缺失** (%s)' % (m, e))
sys.exit(0 if ok else 7)
PYE
[ $? -eq 0 ] || { say "★★ python 依赖不全 ⇒ 先 apt/pip 装（pyelftools capstone unicorn）"; exit 7; }

# ---- 1) 选定编译器 -----------------------------------------------------------
# ★★ 铁律（2026-09-29 修正）：本实验的**全部价值** = 单变量。
#    工厂是 GCC 6.2.0 + gold 1.12 + glibc 2.24；只有 **bootlin63（GCC 6.3 / binutils 2.27 /
#    glibc 2.24）** 与它同族。若回落到 apt 的 arm-linux-gnueabihf-gcc（GCC 14 + glibc 2.41），
#    就**同时**改了两个变量 ⇒ 判决**不可用**。
#    ⇒ 旧代码的"回落 apt"是**静默混淆**：本轮实测就是它导致 `找不到 arm-linux-gnueabihf-gcc`
#      而空跑（`report/_ca_all.txt` 只有 326 B）。现在改成：**缺就自己抓；抓不到就 fail-closed**。
say "== 1) 选定编译器 =="
CONFOUND=""
if [ ! -f cache_tc/bootlin63/.ok ]; then
    say "   bootlin63 未就绪 ⇒ 就地抓取（工厂同期工具链；这是本实验的唯一合法变量）"
    sh tools/fetch_bootlin63.sh || {
        say "★★ 抓不到 bootlin63（网络/URL）⇒ **fail-closed**，不回落 apt 混淆臂。"
        say "   修：确认 workspace 能访问 toolchains.bootlin.com，或预先打包 cache_tc/bootlin63 上传。"
        exit 3
    }
fi
if [ -f cache_tc/bootlin63/.ok ]; then
    GCC="$ROOT/cache_tc/bootlin63/bin/arm-buildroot-linux-gnueabihf-gcc"
    say "   用 bootlin63（工厂同期：GCC 6.3 / glibc 2.24）"
elif [ "${CA_ALLOW_CONFOUND:-0}" = "1" ]; then
    GCC="$(command -v arm-linux-gnueabihf-gcc || true)"
    CONFOUND="★混淆项：apt 的 GCC + 非 2.24 glibc 头（**判决按混淆项降级表述**）"
    say "   显式开启 CA_ALLOW_CONFOUND=1 ⇒ 回落 apt 交叉编译器（$CONFOUND）"
else
    GCC=""
fi
[ -n "${GCC:-}" ] && [ -x "$GCC" ] || {
    say "★★ 无可用编译器（bootlin63 缺失且未显式允许混淆）⇒ fail-closed"
    exit 3
}
"$GCC" --version | head -1 | tee -a "$LOG"
say "   sysroot = $("$GCC" -print-sysroot 2>/dev/null)"
[ -n "$CONFOUND" ] && say "   $CONFOUND"

# ---- 2) zig（只当链接器的宿主）-----------------------------------------------
say "== 2) zig / ld.lld =="
ZIGBIN="$($PY -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null || true)"
if [ -n "$ZIGBIN" ] && [ -x "$ZIGBIN" ]; then
    say "   zig: $ZIGBIN ($($PY -m ziglang version 2>/dev/null))"
else
    say "   ★ zig 不可用：链接无法用本仓的 ld.lld 路径 ⇒ 中止（不要在缺链接器时硬跑）"
    exit 3
fi

# ---- 3) 头文件事实探针（决定 extern-inline 方向）-----------------------------
say "== 3) putc 头文件探针 =="
printf '#include <stdio.h>\nint f(FILE *fp){ return putc(32, fp); }\n' > build/_probe_putc.c
"$GCC" -c -Os build/_probe_putc.c -o build/_probe_putc.o 2>>"$LOG" \
  && $PY - <<'PYE' | tee -a "$LOG"
from elftools.elf.elffile import ELFFile
e = ELFFile(open('build/_probe_putc.o', 'rb'))
st = e.get_section_by_name('.symtab')
u = sorted({s.name for s in st.iter_symbols() if s.name and s['st_shndx'] == 'SHN_UNDEF'})
print('   putc →', [n for n in u if 'putc' in n], '（工厂形态应为 _IO_putc）')
PYE

# ---- 4) 并行编译 213 专有文件 -------------------------------------------------
say "== 4) 并行编译专有对象（-P 8）=="
ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon -fno-pic"
FID="-fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0"
CFLAGS="-c -Os -w -Wno-error=implicit-function-declaration -I$ROOT/src/compat $ARCH $FID"
rm -rf build/gcc_obj; mkdir -p build/gcc_obj; : > report/_ca_gcc_err.txt
export GCC CFLAGS ROOT
find "$ROOT/src/proprietary" -name '*.c' -print0 \
  | xargs -0 -P 8 -I{} sh -c 'b=$(basename "$1" .c); "$GCC" $CFLAGS "$1" -o "build/gcc_obj/$b.o" 2>>report/_ca_gcc_err.txt' _ {}
N=$(ls -1 build/gcc_obj/*.o 2>/dev/null | wc -l)
say "   专有对象 $N/213"
[ "$N" -ge 200 ] || { say "★★ 编译失败过多，看 report/_ca_gcc_err.txt"; tail -12 report/_ca_gcc_err.txt | tee -a "$LOG"; exit 5; }

# ---- 5) XUnzip（C++）--------------------------------------------------------
say "== 5) XUnzip（C++）=="
"$GCC" -x c++ $CFLAGS -std=gnu++98 -fno-exceptions \
    -I"$ROOT/src/upstream/xunzip/posix" "$ROOT/src/upstream/xunzip/unzip.cpp" \
    -o build/gcc_xunzip.o 2>>report/_ca_gcc_err.txt
say "   XUnzip $(stat -c%s build/gcc_xunzip.o 2>/dev/null || echo 0) B"

# ---- 6) 上游 ----------------------------------------------------------------
say "== 6) 上游（mxml / libiconv / stb / mp3）=="
CC="$GCC" PY="$PY" sh tools/build_upstream.sh build/gcc_upstream >> "$LOG" 2>&1
say "   上游对象 $(ls -1 build/gcc_upstream/*.o 2>/dev/null | wc -l)"

# ---- 7) 链接（ld.lld + 工厂同期 sysroot；编译器换了，链接器没换）--------------
say "== 7) 链接 =="
LINK_DRIVER=lld ZIG_BIN="$ZIGBIN" CC="$GCC" SYSROOT="" PY="$PY" \
  DIAG_OBJD="$ROOT/build/gcc_obj" UPOBJD="$ROOT/build/gcc_upstream" \
  DIAG_XUNZIP="$ROOT/build/gcc_xunzip.o" \
  sh tools/link_full.sh build/ab/gcc63.elf >> "$LOG" 2>&1
rc=$?
say "   link rc=$rc"
[ "$rc" = "0" ] && [ -s build/ab/gcc63.elf ] || { say "★★ 链接失败"; tail -15 report/link_full_err.txt | tee -a "$LOG"; exit 5; }
$PY tools/probe_link_binding.py build/ab/gcc63.elf 2>&1 | tee -a "$LOG"

# ---- 8) 行为尺（唯一判据）----------------------------------------------------
# ★ 平台分工（2026-09-29 定）：云开发只负责**只有 Linux 能做的那一段**（编译 + 链接）——
#   行为尺（diff_exec，unicorn）在本机 Windows 一样能跑。所以默认在云上**跳过**尺子，
#   把产物取回本机再测：云上单次会话只花 ~5-8 分钟，避开所有超时风险。
#   设 `CA_SKIP_RULER=1` 即跳过 8~9 步。判据由本机 `tools/ca_judge.sh` 完成。
if [ "${CA_SKIP_RULER:-0}" = "1" ]; then
    say "== 8) 行为尺：**按 CA_SKIP_RULER=1 跳过**（回本机测）=="
    say "   产物：$(pwd)/build/ab/gcc63.elf  sha256=$(sha256sum build/ab/gcc63.elf 2>/dev/null | cut -d' ' -f1)"
    say "   本机判据：sh tools/ca_judge.sh   （读 BASE_DV 自证，纪律 50）"
    say "############ DONE $(date -u +%H:%M:%S) ############"
    exit 0
fi
say "== 8) 行为尺 =="
# ★ 基线自证（纪律 50）：不硬编码。BASE_DV 由本机 ruler_baseline.py 从当前交付产物的权威报告取。
if [ -n "${BASE_DV:-}" ]; then
    say "   基线（外部注入，与产物 sha 绑定）：BASE_DV=$BASE_DV  ${BASE_LINE:-}"
else
    BASE_LINE=$($PY tools/ruler_baseline.py) || {
        say "★★ 取不到行为尺基线（纪律 50 fail-closed）。请在**本机**先跑："
        say "   python3 tools/ruler_baseline.py    # 需 report/ 下有与当前产物 sha 匹配的报告"
        say "   然后以 BASE_DV=<数字> 重新执行本脚本。"
        exit 7
    }
    BASE_DV=$(printf '%s\n' "$BASE_LINE" | awk '{print $5}')
    say "   基线（就地取值）：$BASE_LINE"
fi
[ -n "${BASE_DV:-}" ] || { say "★★ BASE_DV 为空 ⇒ fail-closed"; exit 7; }
export BASE_DV BASE_LINE
$PY tools/diff_exec.py --batch --steps 3000 --ours build/ab/gcc63.elf --out report/_ca_diff.txt >> "$LOG" 2>&1
grep -a '共有函数\|汇总：PASS\|自洽校验' report/_ca_diff.txt | tee -a "$LOG"

# ---- 9) 判决 ----------------------------------------------------------------
say "== 9) 判决 =="
$PY - <<'PYE' | tee -a "$LOG"
import io, os, re
t = io.open('report/_ca_diff.txt', encoding='utf-8', errors='replace').read()
m = re.search(r'汇总：PASS\s+(\d+)\s*｜\s*DIVERGE\s+(\d+)', t)
n = re.search(r'共有函数\s+(\d+)', t)
if not m:
    print('   !! 解析失败'); raise SystemExit(6)
pa, dv = int(m.group(1)), int(m.group(2))
base = int(os.environ['BASE_DV'])
print('   共有 %s ｜ PASS %d ｜ DIVERGE %d ｜ 基线 %d' % (n.group(1) if n else '?', pa, dv, base))
print('   基线出处：%s' % os.environ.get('BASE_LINE', '(外部注入)').strip())
verdict = 'ADOPT' if dv < base else 'REJECT'
print('   ★ 判决：%s（DIVERGE %d vs 基线 %d）' % (verdict, dv, base))
io.open('report/compiler_align_verdict.txt', 'w', encoding='utf-8').write(
    '%s gcc63: PASS %d DIVERGE %d (baseline %d)\n' % (verdict, pa, dv, base))
PYE
say "############ DONE $(date -u +%H:%M:%S) ############"
