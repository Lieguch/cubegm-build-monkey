#!/bin/sh
# ============================================================
# build_probe.sh —— 构建**最小探针** rkgame.probe
#
# 目的：把"真机上换成本产物后无法开机、零日志"这一个现象拆成两个互斥成因：
#   (甲) 内核/ld.so 根本没 exec 成功   → 探针也不会留下任何痕迹
#   (乙) 跑了但一个字节都写不出去      → 探针会在其它路径/通道留下痕迹
#
# 为了这个目的，探针刻意**极简**：
#   · `-nostdlib -static -no-pie` ⇒ 无 `.interp`、无 NEEDED、无 DT_INIT、无构造器
#   · 只有 2~3 个 PT_LOAD、体积 ~2 KB（对比被测对象的 5.7 MB）
#   · 一切外部交互只经 `svc #0`
#
# ★ 产物必须过 `tools/elf_load_audit.py`（和 rkgame 同一道几何门禁）——
#   探针本身也不能是畸形 ELF，否则它失败了也说明不了什么。
#
# 用法: CC="<zig> cc" sh tools/build_probe.sh [输出路径]
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CC="${CC:-arm-linux-gnueabihf-gcc}"
PY="${PY:-python}"
OUT="${1:-$ROOT/build/rkgame.probe}"

winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
D="$ROOT/build/probe_obj"
mkdir -p "$D"

case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon" ;;
esac

echo "== [1/3] 编译探针（-nostdlib，无 libc）=="
$CC $ARCH -c -Os -w -ffreestanding -fno-stack-protector -fno-builtin \
    "$(winpath "$ROOT/src/probe/probe.c")" -o "$(winpath "$D/probe.o")" \
  || { echo "!! probe.c 编译失败" >&2; exit 5; }
$CC $ARCH -c -w "$(winpath "$ROOT/src/probe/start.S")" -o "$(winpath "$D/start.o")" \
  || { echo "!! start.S 汇编失败" >&2; exit 6; }
echo "    probe.o $(wc -c < "$D/probe.o") B / start.o $(wc -c < "$D/start.o") B"

echo "== [2/3] 链接（静态、无 interp、入口 _start）=="
$CC $ARCH -nostdlib -static -no-pie \
    -Wl,-e,_start -Wl,--build-id=none \
    "$(winpath "$D/start.o")" "$(winpath "$D/probe.o")" -o "$(winpath "$OUT")" \
  || { echo "!! 链接失败" >&2; exit 7; }
echo "    产物 $(wc -c < "$OUT") B"

echo "== [3/3] 几何门禁（与 rkgame 同一道）=="
"$PY" "$(winpath "$ROOT/tools/elf_load_audit.py")" "$(winpath "$OUT")" | tail -10
rc=$?
if [ "$rc" != "0" ]; then echo "!! 探针自身几何不过门禁 —— 它的结果不可信" >&2; exit 8; fi

# 关键属性自证：必须**没有** PT_INTERP / NEEDED（否则"剥离复杂度"就没做到）
"$PY" - "$(winpath "$OUT")" <<'PYEOF'
import struct, sys
d = open(sys.argv[1], 'rb').read()
ph = struct.unpack_from('<I', d, 28)[0]; pn = struct.unpack_from('<H', d, 44)[0]
types = [struct.unpack_from('<8I', d, ph + i * 32)[0] for i in range(pn)]
need = []
if 2 in types or 3 in types:   # PT_DYNAMIC / PT_INTERP
    # 进一步看有没有 DT_NEEDED
    for i in range(pn):
        p = struct.unpack_from('<8I', d, ph + i * 32)
        if p[0] == 2:
            off = p[1]; j = 0
            while True:
                t, v = struct.unpack_from('<iI', d, off + j); j += 8
                if t == 0: break
                if t == 1: need.append(v)
print('   PT_INTERP 存在 = %s ；DT_NEEDED 条数 = %d' % (3 in types, len(need)))
bad = (3 in types) or bool(need)
print('   %s' % ('✗ 探针仍依赖动态加载 —— 没达到"最小"目标' if bad else '✓ 无 interp / 无 NEEDED（真正独立，内核可直载）'))
sys.exit(1 if bad else 0)
PYEOF
[ $? = 0 ] || exit 9
echo "== 完成: $OUT =="
