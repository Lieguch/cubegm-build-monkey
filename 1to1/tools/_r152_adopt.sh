#!/bin/sh
# 第 152 轮：把 `-fno-builtin-malloc` 正式落进 link_audit.sh 的 per-TU 口径，并在**链上验收**。
#
# ★ 与 _r152_retest.sh 的区别：那条腿是"手工单点替换 .o"，本脚本走**真正的构建流水线**
#   （link_audit.sh 全量重编 213 个对象 + link_full.sh 重链），验证落进口径后产物可复现。
#
# ★ 验收判据（三条全过才算采纳）：
#   A. TestLibz0.o 在 .o 层就是 calloc=0 / malloc=3（机制生效，与 retest 腿一致）；
#   B. batch 的 DIVERGE 集合 **只减不增**（相对 /tmp/r152/base.txt 的同步基线 16 个）；
#   C. stale_artifact_gate 仍为 0（没把别的对象弄陈旧），diff_exec --self-test 仍过（判据没坏）。
set -u
cd /workspace/1to1 || exit 9
. /tmp/cgm_env.sh 2>/dev/null || { echo "!! 缺 /tmp/cgm_env.sh"; exit 10; }
ZIG=/root/.local/share/uv/python/cpython-3.12.15-linux-x86_64-gnu/lib/python3.12/site-packages/ziglang/zig
OBJDUMP=arm-linux-gnueabihf-objdump

echo "===== ① 前置：口径已更新 + 产物新鲜 ====="
sha256sum tools/link_audit.sh | cut -c1-16
grep -n "PER_TU_FLAGS=" tools/link_audit.sh | head -2
python3 tools/stale_artifact_gate.py >/dev/null 2>&1 && echo "  stale_gate=0(新鲜)" || { echo "  ★★ stale_gate 非 0，先修再跑"; exit 2; }
cp build/rkgame.rebuilt.elf /tmp/r152/adopt_base.elf
echo "  旧产物 sha = $(sha256sum build/rkgame.rebuilt.elf | cut -c1-16)"

echo ""
echo "===== ② link_audit.sh 全量重编（含 per-TU flag）====="
rm -f /tmp/r152/la.log
PY=python3 sh tools/link_audit.sh report/_r152_link_audit.txt > /tmp/r152/la.log 2>&1
echo "  link_audit rc=$?"
grep -m1 "== 编译" /tmp/r152/la.log
grep -m1 "XUnzip.o 已重编" /tmp/r152/la.log || echo "  ★ XUnzip 未重编？"

echo ""
echo "===== ③ A 判据：TestLibz0.o 的分配形态 ====="
TL=build/obj/FUN_0000b6b0_TestLibz0.o
dump() { $OBJDUMP -d "$1" 2>/dev/null | sed -n '/<TestLibz0>:/,/^\$/p'; }
echo "  新口径 calloc=$(dump $TL | grep -c calloc) malloc=$(dump $TL | grep -c '\bmalloc\b')  (期望 calloc=0 malloc=3)"
echo "  retest 腿 calloc=$(dump /tmp/r152/tl_flag.o | grep -c calloc) malloc=$(dump /tmp/r152/tl_flag.o | grep -c '\bmalloc\b')"
echo "  旧对象   calloc=$(dump /tmp/r152/tl_orig.o | grep -c calloc) malloc=$(dump /tmp/r152/tl_orig.o | grep -c '\bmalloc\b')"
echo "  新对象 sha = $(sha256sum $TL | cut -c1-16)"

echo ""
echo "===== ④ link_full.sh 重链 ====="
rm -f /tmp/r152/link2.log
CC="$ZIG cc" SYSROOT="" PY=python3 EXTRA_LDFLAGS="" \
    UPOBJD=build/upstream sh tools/link_full.sh build/rkgame.rebuilt.elf > /tmp/r152/link2.log 2>&1
echo "  link rc=$?  新产物 sha = $(sha256sum build/rkgame.rebuilt.elf | cut -c1-16)"
echo "  retest 腿 flag.elf sha = $(sha256sum /tmp/r152/flag.elf | cut -c1-16)"
echo "  与 retest 腿逐字节相同 = $(cmp -s build/rkgame.rebuilt.elf /tmp/r152/flag.elf && echo 是 || echo 否)"

echo ""
echo "===== ⑤ B 判据：batch + 与同步基线的精确差集 ====="
python3 tools/diff_exec.py --batch --steps 20000 > /tmp/r152/adopt.txt 2>&1
grep -m1 "汇总" /tmp/r152/adopt.txt
python3 - <<'PYEOF'
import re
def div(p):
    n=set(); on=False
    for ln in open(p, encoding="utf-8", errors="replace"):
        if "DIVERGE 明细" in ln: on=True; continue
        if on and ("--- TRUNC" in ln or "--- INFO" in ln): break
        if on:
            m=re.match(r"^  ([A-Za-z_][A-Za-z0-9_]*)\s+\[", ln)
            if m: n.add(m.group(1))
    return n
b=div("/tmp/r152/base.txt"); a=div("/tmp/r152/adopt.txt")
print("  同步基线 DIVERGE = %d" % len(b))
print("  新口径   DIVERGE = %d" % len(a))
print("  ★ 收敛 = %s" % sorted(b-a))
print("  ★ 新增 = %s" % sorted(a-b))
net = len(b) - len(a)
print("  ★ 净账 = %+d  %s" % (net, "达标(只减不增)" if net >= 0 else "★ 不达标(有新增)"))
PYEOF

echo ""
echo "===== ⑥ C 判据：新鲜度 + 判据自证 ====="
python3 tools/stale_artifact_gate.py >/dev/null 2>&1 && echo "  stale_gate=0(新鲜) ✓" || echo "  ★★ stale_gate 非 0!"
python3 tools/diff_exec.py --self-test > /tmp/r152/selftest.txt 2>&1
echo "  diff_exec --self-test rc=$?  $(grep -cE '✓|PASS' /tmp/r152/selftest.txt 2>/dev/null) 个通过标记"

echo ""
echo "===== ⑦ 记账 ====="
echo "  新产物 sha = $(sha256sum build/rkgame.rebuilt.elf | cut -c1-16)"
echo "DONE" > /tmp/r152/ADOPT_DONE
