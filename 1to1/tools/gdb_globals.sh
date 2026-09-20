#!/bin/sh
# ============================================================
# gdb_globals.sh — 零源码改动的运行期全局读取（替代源码内 printf 探针）
#
# 为什么需要它：
#   想在运行期看某个全局（列表闸门 / 当前选中项 / root.dat 载荷指针 /
#   file_info_list 的第 0 项）时，最省事的做法是往重建源码里插 printf ——
#   但那会把调试期代码混进"与出厂语义逐字节对齐"的目标里，而且容易忘记撤除
#   （本项目踩过一次）。qemu 的 gdbstub 让我们**完全不改源码**就看到同样的量。
#
# ★ 关键坑：`DAT_003af394` 这类名字是 **Ghidra 给无名数据起的**，ELF 符号表里
#   **没有** ⇒ gdb 必须**按地址读**（`p &DAT_003af394` 会报 No symbol）。
#   工厂 ELF 里真实存在的名字只有一部分（`file_info_list` / `m_menulog` /
#   `running` …）。所以本脚本用「地址 + info symbol 自证」的方式。
#
# 用法：
#   sh tools/gdb_globals.sh [binary] [断点符号] [端口]
# 例：
#   sh tools/gdb_globals.sh                                  # 默认为工厂二进制
#   sh tools/gdb_globals.sh build/rkgame.rebuilt.elf mui_do_file_list
#
# 前置：先跑 `sh tools/cnb_env.sh`（qemu / gdb / sysroot / /sdcard / shim 全好）
# ============================================================
set -u

BIN="${1:-golden/factory.rkgame.bin}"
BP="${2:-mui_DisplayThumbnail}"
PORT="${3:-12345}"
SYSROOT="${SYSROOT:-/arm-root}"
WORK="${CGM_WORK:-/sdcard/cubegm}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# 工厂 VMA（我们的 linker/factory.ld 复刻了同一布局 ⇒ 两侧同址）
A_RUNNING="${CGM_A_RUNNING:-0x3af018}"   # running
A_IDX="${CGM_A_IDX:-0x3af27c}"           # 当前选中项下标（Ghidra: DAT_003af27c）
A_ROOTDAT="${CGM_A_ROOTDAT:-0x3af2ac}"   # root.dat/fileinfo 载荷指针
A_GATE="${CGM_A_GATE:-0x3af394}"         # 列表循环上界 = GameList_count
A_FILIST="${CGM_A_FILIST:-0x3b2220}"     # file_info_list（每项 0x404 字节）
A_MENULOG="${CGM_A_MENULOG:-0x3c9830}"   # m_menulog（与 menu.log 头 4 字节同源）
A_PATH="${CGM_A_PATH:-0x3c99ec}"         # 全局 path[256]（scandir 的实参）
# ★ 2026-09-20 新增：屏幕缓冲描述符三件套 = dispFlip / mui_WaitNMI 的实参
#   为什么加：桩链打通后 rebuild 卡在 driver.so 的 `gr_blit: source has wrong format`
#   （30 s 里 1816 次）⇒ 必须看这三个量的**运行期真值**才能判断"格式哪里错"。
A_SCRBUF="${CGM_A_SCRBUF:-0x3af29c}"     # DAT_003af29c：屏幕缓冲**指针**（dispFlip 第 1 实参）
A_SCRW="${CGM_A_SCRW:-0x3af2a0}"         # DAT_003af2a0：width（第 2 实参；pitch = 它 << 1）
A_SCRH="${CGM_A_SCRH:-0x3af2a4}"         # DAT_003af2a4：height（第 3 实参）

[ -f "$BIN" ] || { echo "★ 找不到 $BIN"; exit 1; }
command -v qemu-arm-static >/dev/null 2>&1 || { echo "★ 缺 qemu-arm-static（先跑 cnb_env.sh）"; exit 1; }
command -v gdb-multiarch  >/dev/null 2>&1 || { echo "★ 缺 gdb-multiarch（先跑 cnb_env.sh）"; exit 1; }

cp "$BIN" "$WORK/rkgame"
chmod +x "$WORK/rkgame"

CMDF="$(mktemp /tmp/cgm_gdb.XXXXXX)"
LOG="$(mktemp /tmp/cgm_run.XXXXXX)"

# ---- 读值用 gdb 的 Python：单次读失败不会终止整个脚本（x/s 会）----
READPY="$ROOT/build/_gdbread.py"
cat > "$READPY" <<PYEOF
import gdb
def u32(a, n):
    try:    print('   %-24s = %10d   (0x%x)' % (n, int(gdb.parse_and_eval('*(unsigned*)%d' % a)), a))
    except Exception as e: print('   %-24s = <读不到 %s>' % (n, e))
def ptr(a, n):
    try:    print('   %-24s = %s' % (n, gdb.parse_and_eval('*(void**)%d' % a)))
    except Exception as e: print('   %-24s = <读不到 %s>' % (n, e))
def s(a, n):
    try:
        p = int(gdb.parse_and_eval('(unsigned)*(void**)%d' % a))
        if p == 0: print('   %-24s = <NULL>' % n); return
        print('   %-24s = %r' % (n, gdb.execute('x/s 0x%x' % p, to_string=True).strip()))
    except Exception as e: print('   %-24s = <读不到 %s>' % (n, e))
def strs(a, n, stride, k=6):
    for i in range(k):
        try:
            ad = a + i*stride
            print('   %-24s = %r' % ('%s[%d]' % (n, i), gdb.execute('x/s 0x%x' % ad, to_string=True).strip()))
        except Exception as e:
            print('   %-24s = <读不到 %s>' % ('%s[%d]' % (n, i), e)); break
def scr(a_buf, a_w, a_h):
    # ★ 屏幕缓冲三件套 + 派生量：bpp 由"格式约定"推断 ⇒ 一眼看出"格式对不对"
    #   依据：所有 dispFlip 调用点都传 `pitch = width << 1` ⇒ 每像素 2 字节（RGB565）
    try:
        p = int(gdb.parse_and_eval('*(unsigned*)%d' % a_buf))
        w = int(gdb.parse_and_eval('*(unsigned*)%d' % a_w))
        h = int(gdb.parse_and_eval('*(unsigned*)%d' % a_h))
    except Exception as e:
        print('   scr = <读不到 %s>' % e); return
    print('   %-24s = %s (%d)' % ('屏幕缓冲指针(dispFlip#1)', hex(p), p))
    print('   %-24s = %d' % ('width(dispFlip#2)', w))
    print('   %-24s = %d' % ('height(dispFlip#3)', h))
    if w:
        print('   %-24s = %d  (约定 pitch = width<<1)' % ('pitch(推定,dispFlip#4)', w * 2))
        print('   %-24s = %d  ⇒ %s' % ('每像素字节', 2, 'RGB565(16bpp)，与帧缓冲类型 gh_u2* 一致'))
    else:
        print('   ★ width == 0 ⇒ driver.so 判不出 source 格式 ⇒ 极可能就是 wrong format 的根因')
    if p == 0:
        print('   ★ 屏幕缓冲指针 == NULL ⇒ 同上（driver.so 拿到 NULL source）')

def dump(tag):
    print('\n===== %s =====' % tag)
    u32($A_RUNNING,  'running')
    u32($A_GATE,     '列表上界(闸门)')
    u32($A_IDX,      '当前选中项下标')
    ptr($A_ROOTDAT,  'root.dat 载荷指针')
    ptr($A_FILIST,   '&file_info_list')
    ptr($A_MENULOG,  '&m_menulog')
    ptr($A_PATH,     '&path(全局)')
    scr($A_SCRBUF, $A_SCRW, $A_SCRH)
    s($A_MENULOG,    'm_menulog[0..3]')
    strs($A_FILIST,  'file_info_list', 0x404)
dump('断点前的初始值')
PYEOF

cat > "$CMDF" <<EOF
set pagination off
set confirm off
set sysroot $SYSROOT
file $ROOT/$BIN
target remote :$PORT
echo \n===== 地址归属自证（info symbol；Ghidra 名不在符号表里 ⇒ 可能显示"无"）=====\n
info symbol $A_GATE
info symbol $A_FILIST
info symbol $A_MENULOG
source $READPY
echo \n===== 设断点 $BP =====\n
break $BP
continue
echo \n===== 命中 $BP 后 =====\n
python dump('命中 %s 后' % '$BP')
EOF

echo "== 启动 qemu（-g $PORT，ARM32 guest）+ 假硬件 shim =="
cd "$WORK" || exit 1
if [ -f "$ROOT/report/qemu/guest_shim.so" ]; then
  SHIM="$ROOT/report/qemu/guest_shim.so"
  echo "   shim = $SHIM"
  LD_PRELOAD="$SHIM" qemu-arm-static -g "$PORT" -L "$SYSROOT" "$WORK/rkgame" > "$LOG" 2>&1 &
else
  echo "   （无 shim；先跑一次 ci_qemu_behav.sh 或 cnb_env.sh 会生成）"
  qemu-arm-static -g "$PORT" -L "$SYSROOT" "$WORK/rkgame" > "$LOG" 2>&1 &
fi
QPID=$!
sleep 4

echo "== gdb =="
timeout 150 gdb-multiarch -q -batch -x "$CMDF" 2>&1 \
  | grep -avE "^warning: |^Reading |Remote debugging using|^0x[0-9a-f]+ in "

kill "$QPID" 2>/dev/null
wait "$QPID" 2>/dev/null

echo
echo "== 被测进程 stdout 前 25 行（完整日志 $LOG）=="
head -25 "$LOG" | sed 's/^/   /'
rm -f "$CMDF" "$READPY"
