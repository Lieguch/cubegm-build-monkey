#!/bin/sh
# 第 152 轮 P0：在**同步基线**上重测 -fno-builtin-malloc 的净账
# ★ 第 151 轮教训：UPOBJD 默认指向 build/upstream，必须显式锁定，否则混用新旧对象。
set -u
cd /workspace/1to1 || exit 9
ZIG=/root/.local/share/uv/python/cpython-3.12.15-linux-x86_64-gnu/lib/python3.12/site-packages/ziglang/zig
TC=cache_tc/bootlin63
HDRS="-nostdinc -I$TC/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include -I$TC/lib/gcc/arm-buildroot-linux-gnueabihf/6.3.0/include-fixed -I$TC/arm-buildroot-linux-gnueabihf/sysroot/usr/include -Isrc/compat"
ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon"

echo "===== ① 锁定基线快照（build/obj + build/upstream 全量备份 sha）====="
mkdir -p /tmp/r152
tar czf /tmp/r152/obj_base.tgz build/obj 2>/dev/null
echo "  基线产物 sha = $(sha256sum build/rkgame.rebuilt.elf | cut -c1-16)"

echo ""
echo "===== ② 基线 batch（锁定的同步产物）====="
python3 tools/diff_exec.py --batch --steps 20000 > /tmp/r152/base.txt 2>&1
grep -m1 "汇总" /tmp/r152/base.txt

echo ""
echo "===== ③ 单点重编 TestLibz0.c（只加 -fno-builtin-malloc）====="
rm -f /tmp/r152/tl_flag.o
$ZIG cc $ARCH -c -Os -fno-builtin-malloc -w $HDRS \
    -fno-stack-protector -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0 \
    src/proprietary/core/FUN_0000b6b0_TestLibz0.c -o /tmp/r152/tl_flag.o 2>&1 | head -3
echo "  编译 rc=$?"
echo "  calloc=$(arm-linux-gnueabihf-objdump -d /tmp/r152/tl_flag.o 2>/dev/null | sed -n '/<TestLibz0>:/,/^\$/p' | grep -c calloc) malloc=$(arm-linux-gnueabihf-objdump -d /tmp/r152/tl_flag.o 2>/dev/null | sed -n '/<TestLibz0>:/,/^\$/p' | grep -c '\bmalloc\b')"

echo ""
echo "===== ④ 装入 flag 版 .o，重链（显式锁定 UPOBJD=build/upstream）====="
cp build/obj/FUN_0000b6b0_TestLibz0.o /tmp/r152/tl_orig.o
cp /tmp/r152/tl_flag.o build/obj/FUN_0000b6b0_TestLibz0.o
CC="$ZIG cc" SYSROOT="" PY=python3 EXTRA_LDFLAGS="" \
    UPOBJD=build/upstream sh tools/link_full.sh /tmp/r152/flag.elf > /tmp/r152/link.log 2>&1
echo "  link rc=$?  sha=$(sha256sum /tmp/r152/flag.elf 2>/dev/null | cut -c1-16)"

echo ""
echo "===== ⑤ flag 腿 batch ====="
python3 tools/diff_exec.py --batch --steps 20000 --ours /tmp/r152/flag.elf > /tmp/r152/flag.txt 2>&1
grep -m1 "汇总" /tmp/r152/flag.txt

echo ""
echo "===== ⑥ 精确差集 ====="
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
b=div("/tmp/r152/base.txt"); f=div("/tmp/r152/flag.txt")
print("  基线 DIVERGE = %d" % len(b))
print("  flag  DIVERGE = %d" % len(f))
print("  ★ flag 收敛 = %s" % sorted(b-f))
print("  ★ flag 新增 = %s" % sorted(f-b))
net = len(b) - len(f)
print("  ★ 净账 = %+d  %s" % (net, "可采纳(只减不增)" if net > 0 else ("持平,需权衡" if net==0 else "不可采纳")))
PYEOF

echo ""
echo "===== ⑦ 还原 build/obj + 复核基线 ====="
cp /tmp/r152/tl_orig.o build/obj/FUN_0000b6b0_TestLibz0.o
python3 tools/stale_artifact_gate.py >/dev/null 2>&1 && echo "  还原后 stale_gate=0(新鲜)" || echo "  还原后 stale_gate=2(异常!)"
echo "  还原后产物 sha = $(sha256sum build/rkgame.rebuilt.elf | cut -c1-16)"
echo "DONE" > /tmp/r152/DONE
