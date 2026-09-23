#!/bin/sh
# ============================================================
# build_probe4.sh —— 构建**探针 v4**：v3 的现场抓取 + 栈回溯/指令字节（修 v3 的 maps 截断）
#
# v4 = v3 的能力 + 修掉 v3 两个**探针自身**的缺陷（见 src/probe/probe4.c 头注释）。
# v3 新增：ptrace 当 tracer ⇒ ① exec 成功后停在第一条指令，dump **完整映射**；
#   ② 崩溃时拿 **si_addr / PC / LR / SP**；③ 子进程 stdout/stderr 落盘；
#   ④ 传 LD_DEBUG=libs,init 让 ld.so 自己写步骤日志。
#
# 仍然保持"最小"纪律：`-nostdlib -static -no-pie`
#   ⇒ 无 `.interp`、无 NEEDED、无 DT_INIT、无构造器；只经 `svc #0`。
#   ⇒ 它能在设备上跑起来这件事**已经被 v1 实测证明**（同一套技术路线）。
#
# 用法: CC="<zig> cc" sh tools/build_probe4.sh [输出路径]
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CC="${CC:-arm-linux-gnueabihf-gcc}"
PY="${PY:-python}"
OUT="${1:-$ROOT/build/rkgame.probe4}"

winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
D="$ROOT/build/probe4_obj"
mkdir -p "$D"

case "$CC" in
  *zig*) ARCH="-target arm-linux-gnueabihf -mfloat-abi=hard -mfpu=neon" ;;
  *)     ARCH="-march=armv7-a -mfloat-abi=hard -mfpu=neon" ;;
esac

echo "== [1/3] 编译探针 v4（-nostdlib，无 libc）=="
$CC $ARCH -c -Os -w -ffreestanding -fno-stack-protector -fno-builtin \
    "$(winpath "$ROOT/src/probe/probe4.c")" -o "$(winpath "$D/probe4.o")" \
  || { echo "!! probe4.c 编译失败" >&2; exit 5; }
$CC $ARCH -c -w "$(winpath "$ROOT/src/probe/start.S")" -o "$(winpath "$D/start.o")" \
  || { echo "!! start.S 汇编失败" >&2; exit 6; }
echo "    probe4.o $(wc -c < "$D/probe4.o") B / start.o $(wc -c < "$D/start.o") B"

echo "== [2/3] 链接（静态、无 interp、入口 _start）=="
$CC $ARCH -nostdlib -static -no-pie \
    -Wl,-e,_start -Wl,--build-id=none \
    "$(winpath "$D/start.o")" "$(winpath "$D/probe4.o")" -o "$(winpath "$OUT")" \
  || { echo "!! 链接失败" >&2; exit 7; }
echo "    产物 $(wc -c < "$OUT") B"

echo "== [3/3] 几何门禁 + 属性自证 =="
"$PY" "$(winpath "$ROOT/tools/elf_load_audit.py")" "$(winpath "$OUT")" > "$D/audit.txt" 2>&1
rc=$?
tail -6 "$D/audit.txt"
if [ "$rc" != "0" ]; then echo "!! 探针自身几何不过门禁 —— 它的结果不可信" >&2; exit 8; fi

# 自证 ①：必须**没有** PT_INTERP / NEEDED
# 自证 ②：syscall 号必须与 ARM EABI 一致（fork=2 / execve=11 / wait4=114 / kill=37）
#          —— 用反汇编找 `mov r7, #N` 立即数，逐个核对（写错号会静默变成另一个系统调用！）
"$PY" - "$(winpath "$OUT")" <<'PYEOF'
import struct, sys, collections
d = open(sys.argv[1], 'rb').read()

# ---- ① 无 interp / 无 NEEDED ----
ph = struct.unpack_from('<I', d, 28)[0]; pn = struct.unpack_from('<H', d, 44)[0]
P = [struct.unpack_from('<8I', d, ph + i * 32) for i in range(pn)]
types = [p[0] for p in P]
need = []
for p in P:
    if p[0] == 2:
        off = p[1]; j = 0
        while True:
            t, v = struct.unpack_from('<iI', d, off + j); j += 8
            if t == 0: break
            if t == 1: need.append(v)
bad = (3 in types) or bool(need)
print('   PT_INTERP 存在 = %s ；DT_NEEDED 条数 = %d  %s' %
      (3 in types, len(need), '✗' if bad else '✓'))

# ---- ② svc 指令旁的 r7 立即数 ----
# 从 .text 段读指令：mov/movw r7,#imm  (E3A07xxx / E3077xxx+E3477xxx)
shoff = struct.unpack_from('<I', d, 32)[0]
shentsize = struct.unpack_from('<H', d, 46)[0]
shnum = struct.unpack_from('<H', d, 48)[0]
shstrndx = struct.unpack_from('<H', d, 50)[0]
S = [struct.unpack_from('<10I', d, shoff + i * shentsize) for i in range(shnum)]
st = S[shstrndx][4]
text = None
for s in S:
    k = d.index(b'\x00', st + s[0])
    if d[st + s[0]:k] == b'.text':
        text = (s[4], s[5]); break
imm_found = collections.Counter()
if text:
    off, sz = text
    words = [struct.unpack_from('<I', d, off + i)[0] for i in range(0, sz - 3, 4)]
    for i, w in enumerate(words):
        # mov r7, #imm   : 0xE3A07000 | (imm & 0xff) | rot
        if (w & 0xFFFFF000) == 0xE3A07000:
            imm = w & 0xff
            rot = ((w >> 8) & 0xf) * 2
            val = ((imm >> rot) | (imm << (32 - rot))) & 0xFFFFFFFF if rot else imm
            if val < 512:
                imm_found[val] += 1
        # movw r7, #imm16 : 0xE3007000 | (imm4<<16) | imm12
        #   ★ imm4 在 bits 19-16，imm12 在 bits 11-0（Rd 占 bits 15-12）——
        #     第一版我把 bits 15-12 当 imm4，把 322 解码成 327 而误报"缺号"。
        #     判据报错时**先确认判据本身对不对**（这是本项目的纪律）。
        if (w & 0xFFF0F000) == 0xE3007000:
            imm4 = (w >> 16) & 0xf
            imm12 = w & 0xfff
            imm_found[(imm4 << 12) | imm12] += 1
want = {2: 'fork', 3: 'read', 4: 'write', 6: 'close', 11: 'execve', 19: 'lseek',
        20: 'getpid', 26: 'ptrace', 37: 'kill', 114: 'wait4', 120: 'clone',
        162: 'nanosleep', 248: 'exit_group', 322: 'openat', 5: 'open'}
print('   反汇编里出现的 r7 立即数 -> 系统调用名：')
ok = True
for v, n in sorted(imm_found.items()):
    nm = want.get(v)
    print('      %-4d %s' % (v, nm if nm else '(其它)'))
for must in (2, 11, 114, 37, 248, 322):
    if must not in imm_found:
        print('   ★ 缺少必需的系统调用号 %d（%s）—— 号写错会静默变成别的调用！' % (must, want[must]))
        ok = False
print('   %s' % ('✓ 无 interp/无 NEEDED，必需系统调用号齐备' if (not bad and ok)
                else '✗ 自证未通过'))
sys.exit(0 if (not bad and ok) else 1)
PYEOF
[ $? = 0 ] || exit 9
echo "== 完成: $OUT =="
