#!/bin/sh
# ============================================================
# build_libdrm_stub.sh —— 造桩 `libdrm.so.2`（让厂商闭源 driver.so 的图形初始化能过）
#
# 和 build_libkms_stub.sh 是同一套机制（LD_LIBRARY_PATH 前置覆盖），但**不是空桩**：
# 它实现 driver.so 实际引用的 17 个 `drm*` 符号，并保证返回值**全部完整初始化**。
#
# 为什么需要：
#   设备真实 rootfs 里有 `libkms.so.1` ⇒ `dlopen(driver.so)` 成功
#   ⇒ 进 `video_drivers_init()` → `gr_init()`，而沙箱没有真 DRM 设备
#   ⇒ `gr_init` 拿到 NULL ⇒ `driver.so + 0x3ca8` 的 `ldr r3,[r3]`（r3=0）必崩。
#   ⇒ 只要 driver.so 加载成功，沙箱必死在厂商代码里，走不到 rkgame 的任何菜单逻辑。
#   本桩把 DRM 初始化"做成成功"，让执行流越过 `gr_init`。
#
# ★ 公平性：两侧（工厂/重建/控制）注入同一份桩、同一目录 ⇒ 仍是"同环境比实现"。
# ★ 保守性：只进 LD_LIBRARY_PATH，且由**显式开关**（`CGM_DRM_STUB=1`）启用；默认关，行为不变。
# ★ 位置必须**最前**：`LD_LIBRARY_PATH=<stub 目录>:<sysroot 库目录>`，否则真 libdrm 先生效。
#
# 用法: sh tools/build_libdrm_stub.sh <outdir>
# 例:   sh tools/build_libdrm_stub.sh report/stublib
# ============================================================
set -eu

OUT="${1:?usage: build_libdrm_stub.sh <outdir>}"
mkdir -p "$OUT"

# 交叉编译器选择：① 显式 CC_ARM ② 系统 arm gcc（CI 已 apt 安装）③ zig
TARGET="arm-linux-gnueabihf.2.29"     # 设备真实 glibc = 2.29（实测自 org.bin 的 rootfs）
# ★ 2026-10-04（第 138 轮）统一到**唯一权威探测** tools/cgm_cc_probe.sh。
#   本文件此前自带一份探测（用 CC_ARM），与 build_guest_shim/build_upstream 的那份
#   **同规则两处写**，且缺 `arm-buildroot-linux-gnueabihf-gcc` 分支
#   ⇒ CI（装 arm-gcc）与云开发（只有 ziglang）各只能命中一半。
#   cgm_cc_probe.sh 已把「① CC ② CC_ARM ③ arm-gcc ④ arm-buildroot-gcc ⑤ gcc
#   ⑥ zig ⑦ python 包 ziglang」收敛到一处，本文件只保留 source。
. "$(cd "$(dirname "$0")" && pwd)/cgm_cc_probe.sh" \
    || { echo "!! 编译器探测失败（见 cgm_cc_probe.sh 的说明）" >&2; exit 13; }

# ★★ 关键：zig **必须显式给 `-target`**，否则它按**本机宿主**编译。
#   实测（2026-09-19）：`CC_ARM="<zig> cc"` 不加 -target ⇒ 产出 Windows COFF，
#   报错 `lld-link: undefined symbol: _DllMainCRTStartup` —— 而这个错**看不出**是"目标架构错了"，
#   很容易被误读成"缺 memset"。凡是 zig 路径，这里统一补 `-target`。
case "$CC" in
  *zig*)
     case "$CC" in
       *-target*) ;;                                    # 调用方已指定，尊重
       *) CC="$CC -target $TARGET" ;;
     esac ;;
esac
echo "  [libdrm 桩] CC=$CC"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/tools/guest_shim/drm_stub.c"
[ -f "$SRC" ] || { echo "!! 缺源文件 $SRC" >&2; exit 1; }

# ★ Windows 开发机：zig.exe 是**原生 Windows 程序**，不认 `/d/...` 这类 MSYS 路径
#   （技能库第 24 条：入参与 -o 都要 cygpath -w）。
#   实测踩坑（2026-09-19）：不给 → zig 报 `error: CacheCheckFailed`（**症状与病因完全无关**，
#   极易被误读成缓存/源码问题；实际是路径无法解析）。
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

# -nostdlib：本桩不调用 libc（静态数据 + 纯指针写 + 自带 hidden memset）⇒ 无任何运行时依赖，
#            也就不会因为宿主/设备的 glibc 差异而引入新变量。
# -fno-unwind-tables / -fno-asynchronous-unwind-tables：不加会因 .ARM.exidx 引用
#            `__aeabi_unwind_cpp_pr0/pr1`，而 `-nostdlib` 不提供它们 ⇒ 留下 2 个未定义符号。
#            加上后产物**完全自洽（0 未定义符号）**，不依赖任何库。
# ★★ 优化级是「按编译器分支」的接口契约（2026-10-17 云端 GCC 14.2.0 实证，**纠正 R187 的
#   「-Oz 恒成立、不可改回 -O1」两条结论**）：
#     ① 诊断串根本不是优化级问题：云工作区里 `strings` 命令**不存在**（`strings not found`），
#        R187 用 `strings|grep|wc -l` 判「dumb# 被 -O1 折叠消除」是**假阴性**（报错被吞、
#        stdout 恒空 ⇒ 恒为 0）。改用 `grep -a -F` 直搜二进制：GCC 的 O1/Os/O2/O3 **全部**在
#        .rodata 留存 dumb#/frame#/SUMMARY/MAP_DUMB/AddFB2_h。
#     ② GCC **不认 -Oz**（无此优化级，静默当作 -Os）。而 -Os 在 `-nostdlib` 下会把多处
#        `v%10 + v/=10` 十进制转换合并成 `__aeabi_uidivmod`/`__aeabi_idivmod` libcall
#        ⇒ **2 个未定义符号**（zig/clang 的 -Oz 内联成乘法逆元 ⇒ 0 未定义，所以 R187 在本机
#        zig 下测得"0 未定义"是对的，但那结论不能推到 GCC 链）。设备侧这俩符号只在
#        `libgcc_s.so.1`（@@GCC_3.5），而 -nostdlib 桩不含它 ⇒ 桩加载即缺符号。
#     ③ 实测三档在 GCC 链下的未定义数：-O1=0、-O2=0、-Os(=GCC 的 -Oz)=2。
#        ⇒ **分支选择**：zig/clang 用 `-Oz`（8.5 KB、0 未定义、串存活）；
#           GCC 用 `-O2`（69.5 KB、0 未定义、17 导出、dumb# 存活，均已实证）。
case "$CC" in
  *zig*) OPT="-Oz" ;;
  *)     OPT="-O2" ;;   # GCC/其他：无 -Oz；-O2 内联常数除法 ⇒ 0 未定义
esac
echo "  [libdrm 桩] OPT=$OPT"
# -Wl,-soname：必须与 driver.so 的 DT_NEEDED 完全一致（libdrm.so.2）；
#            SONAME 缺失会让 DT_NEEDED 的解析在某些 loader 上退化成"按文件名匹配"。
# shellcheck disable=SC2086
$CC -shared -fPIC -nostdlib $OPT -w \
    -fno-unwind-tables -fno-asynchronous-unwind-tables \
    -Wl,-soname,libdrm.so.2 \
    "$(winpath "$SRC")" -o "$(winpath "$OUT/libdrm.so.2")"

echo "  已生成 $OUT/libdrm.so.2（$(wc -c < "$OUT/libdrm.so.2") B）"

# ---- 自证：导出符号必须覆盖 driver.so 引用的 drm* ----
# ★★ NEED 清单的**唯一权威** = tools/driver_stub_coverage.py（它解析 driver.so 的
#   .dynsym 得出需求，第 163 轮收敛）。本脚本不再写第二份清单（"同一规则禁止写两处"）；
#   拿不到 ⇒ fail-closed 退出，绝不退化成"不校验"（那会让桩漂移静默通过）。
PY="${PY:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
NEED="$("$PY" "$ROOT/tools/driver_stub_coverage.py" --print-need drm)" \
    || { echo "!! 取 NEED 清单失败：$PY $ROOT/tools/driver_stub_coverage.py --print-need drm" >&2; exit 13; }
[ -n "$NEED" ] || { echo "!! NEED 清单为空（driver.so 解析失败？查 golden/sdcard_min/driver.so）" >&2; exit 13; }

if command -v arm-linux-gnueabihf-nm >/dev/null 2>&1; then
    NM=arm-linux-gnueabihf-nm
elif command -v nm >/dev/null 2>&1; then
    NM=nm
else
    NM=""
fi
if [ -n "$NM" ]; then
    got="$($NM -D --defined-only "$OUT/libdrm.so.2" 2>/dev/null | awk '{print $NF}' | sort)"
    miss=""
    for s in $NEED; do
        echo "$got" | grep -qx "$s" || miss="$miss $s"
    done
    if [ -n "$miss" ]; then
        echo "  ★ 缺失符号:$miss" >&2
        exit 1
    fi
    echo "  自证：$(printf '%s' "$NEED" | wc -w) 个 drm* 全部导出 ✓"

    # ★★ R187/R188 根修落成**产物级 fail-closed 门禁**：未定义符号数必须为 0。
    #   事故（2026-10-17 云 GCC）：「-O1/-Oz 差异」被连栽两轮——先是 R187 用本机 zig 断言
    #   `-Oz ⇒ 0 未定义`，随后上云 GCC 发现 -Os(=它的 -Oz) 反而引入 __aeabi_uidivmod/idivmod
    #   2 个未定义（GCC 把 v%10+v/10 合并成 libcall，zig 内联成乘法逆元）。
    #   这条不变量此前**只写在注释里**，产物一旦悄悄多了未定义符号没有任何拦截 ⇒ 这就是
    #   「注释里的不变量必须配产物级验证」的兑现：解析 .dynsym 里 st_shndx==0 的条目数，
    #   非 0 立即响亮失败，不许带着缺符号的桩上云/真机（加载即崩，且症状与病因无关）。
    undef="$($NM -D "$OUT/libdrm.so.2" 2>/dev/null | grep -c ' U ' || true)"
    case "$undef" in ''|*[!0-9]*) undef=0 ;; esac
    if [ "$undef" != "0" ]; then
        echo "  ★ 未定义符号 $undef 个（-nostdlib 桩必须 0，否则加载即崩）：$($NM -D "$OUT/libdrm.so.2" 2>/dev/null | grep ' U ' | head -8)" >&2
        exit 1
    fi
    echo "  自证：0 未定义符号 ✓（完全自洽，不依赖 libgcc_s/libc）"
fi
