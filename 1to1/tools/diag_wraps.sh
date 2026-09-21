#!/bin/sh
# ============================================================
# diag_wraps.sh —— wrap 符号列表 + 自检门禁（被 build_diag.sh 在最前面 source）
#
# 为什么单独一个文件：门禁要在**编译 213 个文件之前**就跑（失败要快）；
# 同时它必须能被**独立反证**（见 tools/_diag_gate_selftest.py）。
#
# 需要外部提供：$ROOT（仓库根）、$PY（python）、$CC
# 产出：WFLAG / WRAPS / LDF / cnt
# ============================================================

# ★★★ 2026-09-21（GAP 16.65）：**zig 的驱动层只认单横线 `-wrap=`，不认 `--wrap=`**。
#   实测七种写法，只有 `-Wl,-wrap=SYM` 通过 zig 的参数过滤（其余报
#   `error: unsupported linker arg: --wrap` / `unsupported linker arg: --defsym`）。
#   行为自证（不是只看参数被接受）：不加 wrap 时产物未定义符号含 `open`；
#   加 `-Wl,-wrap=open` 后 `open` 从产物未定义符号里消失 ⇒ 重定向真的发生了。
#   ⇒ 按编译器分派：zig/clang 走 `-Wl,-wrap=`，GCC 的 GNU ld 走 `-Wl,--wrap=`。
case "$CC" in
  *zig*) WFLAG="-Wl,-wrap=" ;;
  *)     WFLAG="-Wl,--wrap=" ;;
esac

# 覆盖优先级：启动 > 文件 > 设备 > 动态库 > 进程 > 线程 > 时间 > 信号
WRAPS="__libc_start_main \
open open64 openat fopen fopen64 fclose close read write fread fwrite \
lseek lseek64 fseek ftell fflush access stat lstat fstat mkdir unlink remove rename \
chdir getcwd readlink realpath opendir readdir closedir ftruncate statfs \
ioctl fcntl mmap munmap poll select \
dlopen dlsym dlclose dlerror \
fork vfork execve system popen \
pthread_create pthread_join pthread_mutex_lock pthread_cond_wait \
nanosleep usleep sleep gettimeofday clock_gettime \
signal sigaction raise alarm \
exit _exit abort"

LDF=""
cnt=0
for w in $WRAPS; do LDF="$LDF $WFLAG$w"; cnt=$((cnt + 1)); done

# ---------------- 自检门禁 ----------------
# 判据（唯一）：WRAPS 里每个符号，在 src/diag/cgm_wrap.c 里必须有 `__wrap_<sym>` 字样。
# 失败 ⇒ exit 11。
#
# ★★ 缺陷态怎么造（这条很重要，我第一次造错了）：
#   `-wrap=X` **只有在有东西引用 `X` 时**才会产生"未定义 `__wrap_X`"。
#   往列表里塞一个**无人引用**的假符号（如 `__no_such_symbol_at_all`）**不会**触发任何错误
#   —— 实测 exit 0、照常出产物。所以反证必须用一个**被引用**的符号
#   （例：把 `__wrap_fflush` 改名 ⇒ 门禁必须 exit 11，链接器也必须报 undefined）。
#   见 tools/_diag_gate_selftest.py。
#
# 与链接期报错的关系：链接器**确实**会硬失败（这点是对的），但报错在 200 行之后、
# 信息量低。本门禁把它提前成一句人话，并且**在编译之前**。
# ★★★ 2026-09-21：**门禁自己踩了本项目的已知坑** —— 传给**原生 Python** 的路径
#   必须是 Windows 形式（`D:/...`）：源生的 `ROOT`（由 `pwd` 得到）是 MSYS 形式
#   `/d/output/...`，原生 python.exe **打不开它** ⇒ `__READ_ERROR__`。
#   幸好门禁里有"读不到文件也必须 exit 11"的守卫，否则它会静默通过（= 门禁恒假）。
#   ★ 这正是"0 命中必须能区分两种原因"那条纪律在门禁自身上的应用。
if ! command -v winpath >/dev/null 2>&1; then
    winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
fi
GATE_SRC="$(winpath "$ROOT/src/diag/cgm_wrap.c")"

GATE_MISS=$("$PY" -c "
import io,sys
try:
    t=io.open(sys.argv[1],encoding='utf-8',errors='replace').read()
except Exception as e:
    print('__READ_ERROR__'); sys.exit(0)
print(' '.join(w for w in sys.argv[2:] if ('__wrap_'+w) not in t))
" "$GATE_SRC" $WRAPS 2>/dev/null)

if [ "$GATE_MISS" = "__READ_ERROR__" ]; then
    echo "   ✗ 门禁无法读取 src/diag/cgm_wrap.c（$GATE_SRC）" >&2
    echo "     路径不存在/权限/形式不对（原生 Python 只认 Windows 形式 D:/...）。" >&2
    echo "     这必须是硬失败，否则门禁恒假。" >&2
    exit 11
fi
if [ -n "$GATE_MISS" ]; then
    echo "   ✗ WRAPS 里这些符号在 src/diag/cgm_wrap.c 里没有实现：$GATE_MISS" >&2
    echo "     ⇒ 若其中有被引用的符号，链接必然 undefined symbol。先补实现（或从列表删掉）。" >&2
    exit 11
fi
echo "   ✓ 自检：$cnt 个 wrap 符号全部有实现（形式 $WFLAG<sym>）"
