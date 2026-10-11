#!/bin/sh
# ============================================================
# build_libasound_stub.sh —— 造桩 `libasound.so.2`（让厂商闭源 driver.so 的音频初始化能过）
#
# 和 build_libdrm_stub.sh 是同一套机制（LD_LIBRARY_PATH 前置覆盖），实现 driver.so
# 实测引用的全部 20 个 `snd_*` 符号，返回值**全部完整初始化/语义自洽**。
#
# 为什么需要（见 GAP 16.23）：
#   桩 libdrm 打通图形后，两侧都止于
#     `pcm.c:3009: snd_pcm_avail: Assertion 'pcm' failed.`（该行来自真实 alsa-lib）
#   ⇒ `snd_pcm_open()` 在假硬件上失败，driver.so 未检查返回值就继续用 NULL 句柄 ⇒ abort()。
#   本桩把音频初始化也"做成成功"，让执行流越过这次 abort。
#
# ★ 全仓普查：**只有 driver.so 引用 `snd_*`**（工厂 rkgame / 重建 elf / icube 均为 0）
#   ⇒ 整体替换 `libasound.so.2` 不影响任何其它模块。
# ★ 公平性：两侧（工厂/重建/控制）注入同一份桩、同一目录 ⇒ 仍是"同环境比实现"。
# ★ 保守性：只进 LD_LIBRARY_PATH，且由**显式开关**（`CGM_ALSA_STUB=1`）启用；默认关。
# ★ 位置必须**最前**（与 drm 桩同区），否则真 libasound 先生效。
#
# 用法: sh tools/build_libasound_stub.sh <outdir>
# 例:   sh tools/build_libasound_stub.sh report/alsastublib
# ============================================================
set -eu

OUT="${1:?usage: build_libasound_stub.sh <outdir>}"
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
#   报错 `lld-link: undefined symbol: _DllMainCRTStartup` —— 这个错**看不出**是"目标架构错了"。
case "$CC" in
  *zig*)
     case "$CC" in
       *-target*) ;;
       *) CC="$CC -target $TARGET" ;;
     esac ;;
esac
echo "  [libasound 桩] CC=$CC"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/tools/guest_shim/alsa_stub.c"
[ -f "$SRC" ] || { echo "!! 缺源文件 $SRC" >&2; exit 1; }

# ★ Windows 开发机：zig.exe 是**原生 Windows 程序**，不认 `/d/...` 这类 MSYS 路径。
#   实测踩坑（2026-09-19）：不给 → zig 报 `error: CacheCheckFailed`（症状与病因完全无关）。
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else printf '%s' "$1"; fi; }

# -nostdlib + hidden memset：零运行时依赖（见 alsa_stub.c 顶部说明）
# -fno-unwind-tables：否则 .ARM.exidx 会引用 `__aeabi_unwind_cpp_pr0/pr1` ⇒ 留下未定义符号
# -Wl,-soname：必须与 driver.so 的 DT_NEEDED 完全一致（libasound.so.2）
# shellcheck disable=SC2086
$CC -shared -fPIC -nostdlib -O1 -w \
    -fno-unwind-tables -fno-asynchronous-unwind-tables \
    -Wl,-soname,libasound.so.2 \
    "$(winpath "$SRC")" -o "$(winpath "$OUT/libasound.so.2")"

echo "  已生成 $OUT/libasound.so.2（$(wc -c < "$OUT/libasound.so.2") B）"

# ---- 自证：导出符号必须覆盖 driver.so 引用的 snd_pcm_* ----
# ★★ NEED 清单的**唯一权威** = tools/driver_stub_coverage.py（它解析 driver.so 的
#   .dynsym 得出需求，第 163 轮收敛）。本脚本不再写第二份清单（"同一规则禁止写两处"）；
#   拿不到 ⇒ fail-closed 退出，绝不退化成"不校验"（那会让桩漂移静默通过）。
PY="${PY:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
NEED="$("$PY" "$ROOT/tools/driver_stub_coverage.py" --print-need alsa)" \
    || { echo "!! 取 NEED 清单失败：$PY $ROOT/tools/driver_stub_coverage.py --print-need alsa" >&2; exit 13; }
[ -n "$NEED" ] || { echo "!! NEED 清单为空（driver.so 解析失败？查 golden/sdcard_min/driver.so）" >&2; exit 13; }

if command -v arm-linux-gnueabihf-nm >/dev/null 2>&1; then
    NM=arm-linux-gnueabihf-nm
elif command -v nm >/dev/null 2>&1; then
    NM=nm
else
    NM=""
fi
if [ -n "$NM" ]; then
    got="$($NM -D --defined-only "$OUT/libasound.so.2" 2>/dev/null | awk '{print $NF}' | sort)"
    miss=""
    for s in $NEED; do
        echo "$got" | grep -qx "$s" || miss="$miss $s"
    done
    if [ -n "$miss" ]; then
        echo "  ★ 缺失符号:$miss" >&2
        exit 1
    fi
    echo "  自证：$(printf '%s' "$NEED" | wc -w) 个 snd_pcm_* 全部导出 ✓"
fi
