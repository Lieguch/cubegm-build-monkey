#!/bin/sh
# ============================================================================
# glibc_compat_probe.sh —— 对拍「我们 compat 头里的 __timezone_ptr_t 声明」
#                          vs「glibc 2.24 的原文」
#
# 存在的理由（第 65→66 轮的代价）：
#   第 65 轮我们的声明缺了 `__restrict`，真实 glibc 2.24 报
#     error: conflicting type qualifiers for '__timezone_ptr_t'
#   —— 这条错误在 CI 上**每轮只暴露一个比特**（推一次、等 8 分钟）。
#
# ★ 设计要点（都是被实测逼出来的）：
#   ① **不与包含顺序搏斗**：zig/clang 会把自己的内建 glibc 头强插在搜索路径最前，
#      `--sysroot` / `-nostdinc` / `-I` 都压不住它（实测 `generic-glibc` 仍被引用 61 次）。
#      ⇒ 本仪器直接把**双方声明原文**拼进一个自足 TU（不 include 任何头）编译，
#        测的就是我们真正关心的那个性质：「两段声明文本是否冲突」。
#   ② **前置条件必须断言**：若头来源不对，编译"成功"毫无意义（假绿）。
#      ⇒ 正例 TU 里带 `#error` 探针，确认走到了我们拼的那段文本。
#   ③ **双向**：正例（逐字复刻）必须过；缺陷态（缺 __restrict / 用 void *）必须**失败**。
#
# 用法：
#   sh tools/glibc_compat_probe.sh              # 对拍 compat 头 vs glibc 2.24 原文（默认）
#   sh tools/glibc_compat_probe.sh --selftest   # 只跑双向自证
#   SYSROOT=… sh tools/glibc_compat_probe.sh --real   # 若给了真实 sysroot，额外做真头编译
#
# exit: 0 = 兼容 / 1 = 冲突 / 2 = 无编译器
# ============================================================================
set -u
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 2
WORK="$ROOT/build/_tzprobe"
mkdir -p "$WORK"

# ---- 宿主编译器解析（★ 不可假设 `cc` 存在：本机 Windows 三者皆无）----------
pick_cc() {
    if [ -n "${CC:-}" ]; then printf '%s' "$CC"; return 0; fi
    for c in cc gcc clang; do
        command -v "$c" >/dev/null 2>&1 || continue
        printf 'int x;\n' | "$c" -x c -c - -o "$WORK/_probe_cc.o" 2>/dev/null && { printf '%s' "$c"; return 0; }
    done
    # 兜底 1：显式给的 zig（本机唯一能编译 C 的东西）
    if [ -n "${ZIG:-}" ] && [ -x "${ZIG%% *}" ]; then printf '%s cc' "$ZIG"; return 0; fi
    # 兜底 2：PATH 上的 zig
    if command -v zig >/dev/null 2>&1; then printf 'zig cc'; return 0; fi
    # 兜底 3：从 python 里取 ziglang（注意 `python3` 是**基座**解释器，可能没这个包）
    for py in python3 python; do
        command -v "$py" >/dev/null 2>&1 || continue
        z=$("$py" -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null)
        [ -n "$z" ] && [ -x "$z" ] && { printf '%s cc' "$z"; return 0; }
    done
    return 1
}
CC=$(pick_cc) || { echo "★ 无可用的宿主编译器 ⇒ 本仪器不可判（不得当作通过）"; exit 2; }
echo "  宿主编译器 = $CC"

# glibc 2.24 `time/sys/time.h` 原文。
# ★ 优先**从真实 sysroot 抽取**（唯一真源 = 产物本身）；抽不到才用下面这份逐字副本，
#   并且会打印"(literal)"提醒读者它不是来自产物。硬编字符串会与上游漂移 ⇒ 不许静默使用。
GLIBC224_DECL_LITERAL='#ifdef __USE_MISC
typedef struct timezone *__restrict __timezone_ptr_t;
#else
typedef void *__restrict __timezone_ptr_t;
#endif'

find_sysroot() {
    if [ -n "${SYSROOT:-}" ] && [ -d "$SYSROOT/usr/include" ]; then echo "$SYSROOT"; return 0; fi
    for d in cache_tc/bootlin*/arm-*/sysroot cache_tc/bootlin*/sysroot; do
        [ -d "$d/usr/include" ] && { echo "$d"; return 0; }
    done
    return 1
}

glibc_decl() {   # → 打印 glibc 原文里的声明块；来源标注写 stderr
    sr=$(find_sysroot 2>/dev/null) || { printf '%s\n' "$GLIBC224_DECL_LITERAL"; echo "  （声明来源：literal 副本 —— 未找到真实 sysroot）" >&2; return 0; }
    f="$sr/usr/include/sys/time.h"
    [ -f "$f" ] || { printf '%s\n' "$GLIBC224_DECL_LITERAL"; echo "  （声明来源：literal 副本 —— $f 不存在）" >&2; return 0; }
    blk=$(awk '
        /__timezone_ptr_t[[:space:]]*;/ { hit = NR }
        { line[NR] = $0 }
        END {
            if (!hit) exit 1
            s = 0; e = 0
            for (i = hit; i >= 1; i--) if (line[i] ~ /^#ifdef __USE_MISC/) { s = i; break }
            for (i = hit; i <= NR; i++) if (line[i] ~ /^#endif/) { e = i; break }
            if (!s || !e) exit 1
            for (i = s; i <= e; i++) print line[i]
        }' "$f" | grep -E '^#|^[[:space:]]*typedef') || { printf '%s\n' "$GLIBC224_DECL_LITERAL"; echo "  （声明来源：literal 副本 —— 抽取失败）" >&2; return 0; }
    # ★ fail-closed：抽出来的块必须真的含 __restrict，否则抽取逻辑坏了 ⇒ 报错而不是给个空块
    case "$blk" in
        *__restrict*__timezone_ptr_t*) echo "  （声明来源：真实 sysroot $f）" >&2; printf '%s\n' "$blk" ;;
        *) printf '%s\n' "$GLIBC224_DECL_LITERAL"; echo "  （★ 抽取出的块不含 __restrict ⇒ 拒绝使用，回落 literal）" >&2 ;;
    esac
}

# 我们 compat 头里的那段（**从文件里抽** ⇒ 头文件一改，这里就对不上，不得硬编）
our_decl() {
    sed -n '/^#ifndef __timezone_ptr_t/,/^#endif/p' src/compat/ghidra_compat.h
}

cc_alive() {
    # ★ 活性控制：编译器能用吗？不能 ⇒ 一切"必须失败"的锚点都会假通过。
    printf 'int alive(void){return 0;}\n' > "$WORK/_alive.c"
    # shellcheck disable=SC2086
    $CC -std=gnu11 -c "$WORK/_alive.c" -o "$WORK/_alive.o" >/dev/null 2>&1
}

run_cc() {  # $1=src → stdout 编译输出；返回源码返回码
    # ★ 不用 `-fsyntax-only`：zig cc 不认它（实测报 `unused argument '-c'` + `FileNotFound`）
    #   ⇒ 用 `-c -o`，GCC/clang/zig 三家通用。
    # shellcheck disable=SC2086
    $CC -std=gnu11 -nostdinc -c "$1" -o "$WORK/_out.o" 2>&1
}

probe_pair() {  # $1=标签 $2=第一段声明 $3=第二段声明 → 打印判定，返回 0=兼容/1=冲突
    lab=$1
    f="$WORK/$lab.c"
    {
        printf 'struct timeval { long tv_sec; long tv_usec; };\n'
        printf 'struct timezone { int tz_minuteswest; int tz_dsttime; };\n'
        printf '#define __USE_MISC 1\n'
        printf '%s\n' "$2"
        # ★ 前置条件断言：走到下一行说明**上面那段声明真的被编译过**
        #   （否则"编译通过"只说明 TU 是空的 ⇒ 假绿）
        printf '#define RKGAME_PROBE_MARK 1\n'
        printf '#ifndef RKGAME_PROBE_MARK\n#error "probe precondition failed: 声明文本未被编译"\n#endif\n'
        printf '%s\n' "$3"
        printf '__timezone_ptr_t f(void) { return (__timezone_ptr_t)0; }\n'
    } > "$f"
    out=$(run_cc "$f"); rc=$?
    if [ "$rc" -eq 0 ]; then echo "  兼容"; return 0; fi
    echo "$out" | grep -q 'RKGAME_PROBE_MARK' && { echo "  ★ 前置条件失败（声明文本未参与编译）⇒ 不可判"; return 2; }
    echo "$out" | head -3 | sed 's/^/    /'
    return 1
}

selftest() {
    ok=0; fail=0
    chk() { if [ "$2" = "$3" ]; then ok=$((ok+1)); printf '  ✓ %s\n' "$1";
            else fail=$((fail+1)); printf '  ✗ %s（得到 %s，期望 %s）\n' "$1" "$2" "$3"; fi; }
    printf '=== glibc_compat_probe 自证（双向）===\n'
    if ! cc_alive; then
        echo "  ★★ 宿主编译器 [$CC] 不能编译 ⇒ 自证不可判（退出 2）。"
        echo "     理由：三个缺陷态锚点**本来就期待编译失败**，编译器不存在时它们会**假通过**。"
        return 2
    fi
    printf '  活性控制  : 宿主编译器可编译 ✓  (%s)\n' "$CC"
    if sr=$(find_sysroot 2>/dev/null); then
        printf '  声明来源 = 真实 sysroot: %s\n' "$sr"
    else
        printf '  ★ 声明来源 = literal 副本（无真实 sysroot；自证仍有效，但不代表产物）\n'
    fi

    # ① 正例：glibc 原文 与 我们 compat 头的当前文本 ⇒ 兼容
    v=$(probe_pair ok "$(glibc_decl 2>/dev/null)" "$(our_decl)"; echo "rc=$?")
    chk "正例 我们 compat 头的声明 vs glibc 2.24 原文 ⇒ 兼容" \
        "$(echo "$v" | tail -1)" "rc=0"
    # ①b 仪器自检：抽到/抄来的 glibc 原文**必须**含 __restrict（两个分支各一次），
    #     否则本仪器就是在拿一个"没有限定符"的假原文做对拍 ⇒ 会永远报"兼容"。
    chk "仪器自检 glibc 原文含 __restrict ×2（防仪器自己骗人）" \
        "$(glibc_decl 2>/dev/null | grep -c '__restrict' | tr -d ' ')" "2"

    # ② 缺陷态：缺 __restrict ⇒ 必须冲突（第 65 轮真实故障复现）
    v=$(probe_pair bad_qual "$(glibc_decl 2>/dev/null)" 'typedef struct timezone *__timezone_ptr_t;'; echo "rc=$?")
    chk "缺陷态 缺 __restrict ⇒ 必须冲突（复现第 65 轮故障）" "$(echo "$v" | tail -1)" "rc=1"

    # ③ 缺陷态：第 65 轮那次「修法」（void *）同样冲突 ⇒ 证明那次没修好
    v=$(probe_pair bad_void "$(glibc_decl 2>/dev/null)" 'typedef void *__timezone_ptr_t;'; echo "rc=$?")
    chk "缺陷态 改用 void *（第 65 轮的修法）⇒ 必须冲突" "$(echo "$v" | tail -1)" "rc=1"

    # ④ 前置条件必须能报出来（防空 TU 假通过）
    v=$(probe_pair precond "$(glibc_decl 2>/dev/null)" '#error "forced"'; echo "rc=$?")
    chk "前置条件探针有效（#error 必被判为不可判/失败）" \
        "$([ "$(echo "$v" | tail -1)" != "rc=0" ] && echo yes || echo no)" "yes"

    printf '=== 合计 %d 条，失败 %d 条 ===\n' "$((ok + fail))" "$fail"
    [ "$fail" = "0" ]
}

# 真实 sysroot 模式：只有拿到真工具链（能在 Linux 跑）才可信；本机 zig 压不住内建头，
# 因此本模式**先断言前置条件**（__GLIBC_MINOR__ 必须是目标值），断言不过就报不可判。
real_check() {
    SR="${SYSROOT:-}"
    [ -n "$SR" ] || for d in cache_tc/bootlin*/arm-*/sysroot cache_tc/bootlin*/sysroot; do
        [ -d "$d/usr/include" ] && { SR="$d"; break; }; done
    if [ -z "$SR" ] || [ ! -d "$SR/usr/include" ]; then
        echo "  真实 sysroot 模式：无 sysroot（sh build/_dl_tc.sh 获取）⇒ 跳过（不可判，不算通过）"
        return 2
    fi
    echo "  sysroot = $SR"
    for f in "$SR/usr/include/bits/types/__timezone_ptr_t.h" "$SR/usr/include/sys/time.h"; do
        [ -f "$f" ] || continue
        grep -qs '__timezone_ptr_t' "$f" && { echo "  真实头原文（$f）："; grep -n '__timezone_ptr_t' "$f" | sed 's/^/    /'; }
    done
    printf '#include <sys/time.h>\n#if !defined(__GLIBC__) || __GLIBC_MINOR__ != 24\n#error "sysroot 前置条件失败：拿到的不是 glibc 2.24 头"\n#endif\n#include "ghidra_compat.h"\n__timezone_ptr_t tzp(void){ return (__timezone_ptr_t)0; }\n' > "$WORK/_real.c"
    # shellcheck disable=SC2086
    $CC --sysroot="$SR" -std=gnu11 -w -I src/compat -c "$WORK/_real.c" -o "$WORK/_real.o" 2>&1 | head -6
    rc=$?
    [ -s "$WORK/_real.o" ] && echo "  ✓ 真实 glibc 2.24 头 + 我们 compat 头：兼容"
    return $rc
}

if [ "${1:-}" = "--selftest" ]; then selftest; exit $?; fi

echo "=== ① 双向自证 ==="
selftest || exit 1
if [ "${1:-}" = "--real" ]; then
    echo
    echo "=== ② 真实 sysroot 对拍 ==="
    real_check; echo "  rc=$?"
fi
exit 0
