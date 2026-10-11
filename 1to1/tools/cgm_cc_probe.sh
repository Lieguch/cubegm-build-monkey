#!/bin/sh
# ============================================================
# cgm_cc_probe.sh — 统一的 ARM 交叉编译器探测（**唯一权威来源**）
#
# 为什么需要这个文件（2026-10-04 第 138 轮，血泪）：
#   本项目**到处**硬编 `CC="${CC:-arm-linux-gnueabihf-gcc}"`，而三个环境各自只装其中一种：
#     · CNB 云开发工作区：只装了 ziglang（`pip install ziglang`，可执行文件**不在 PATH**）
#     · GitHub Actions：装 `gcc-arm-linux-gnueabihf`
#     · 本机 Windows：只有 `zig.exe`
#   ⇒ 硬编任何一种都会在其余两个失败。实测后果**连续三轮**：
#     · `build_guest_shim.sh`：静默降级为「用上一轮残留 .so」，报告照常产出（结论失真）
#     · `build_upstream.sh`：xunzip 自举失败 ⇒ `XUnzip.o` 缺失 ⇒ 整轮构建报废
#     · `link_full.sh`：`arm-linux-gnueabihf-gcc: command not found` ⇒ 无产物
#   ⇒ 根治办法不是"再复制一份探测代码"，而是**把探测收敛到一处**，
#     所有脚本 `.` 引用它 —— 这也是「同一规则禁止写两处」的直接应用。
#
# 用法（source 之后 `$CC` / `$CXX` 一定可用，或已 exit 13）：
#     . "$(dirname "$0")/cgm_cc_probe.sh"
#
# 探测顺序（从"最像工厂"到"最通用"）：
#   ① `$CC` / `$CC_ARM` 环境变量（调用方显式指定，最高优先）
#   ② `CC_ARM` 环境变量（桩脚本的既有约定）
#   ③ `arm-linux-gnueabihf-gcc`      ← 工厂同期（Bootlin/buildroot）
#   ④ `arm-buildroot-linux-gnueabihf-gcc`
#   ⑤ `gcc`（宿主；ARM 目标需配合 -march，能力较弱但可跑）
#   ⑥ `zig`（在 PATH）
#   ⑦ `zig` 作为 python 包（CNB 云开发的标准装法，可执行文件不在 PATH）
#
# ★ fail-closed：全都没有 ⇒ **exit 13**（不是继续跑）。
#   继续跑的后果是"全部编译失败"却看不出真因（实测已发生过三轮）。
# ============================================================

cgm_cc_probe() {
    # 已由调用方指定 ⇒ 尊重
    if [ -n "${CC:-}" ]; then
        :
    elif [ -n "${CC_ARM:-}" ]; then
        CC="$CC_ARM"
    elif command -v arm-linux-gnueabihf-gcc >/dev/null 2>&1; then
        CC="arm-linux-gnueabihf-gcc"
    elif command -v arm-buildroot-linux-gnueabihf-gcc >/dev/null 2>&1; then
        CC="arm-buildroot-linux-gnueabihf-gcc"
    elif command -v gcc >/dev/null 2>&1; then
        CC="gcc"
    elif command -v zig >/dev/null 2>&1; then
        CC="zig cc"
    else
        # ⑦ zig 作为 python 包（CNB 云开发：pip install ziglang）
        _zp=$(python3 -c 'import ziglang,os;print(os.path.join(os.path.dirname(ziglang.__file__),"zig"))' 2>/dev/null)
        if [ -n "$_zp" ] && [ -x "$_zp" ]; then
            CC="$_zp cc"
        else
            echo "!! 找不到任何 ARM 交叉编译器。" >&2
            echo "!!   试过：\$CC / \$CC_ARM / arm-linux-gnueabihf-gcc / arm-buildroot-linux-gnueabihf-gcc" >&2
            echo "!!        / gcc / zig / python 包 ziglang" >&2
            echo "!! ⇒ 继续跑只会产出「全部失败」却看不出真因（已踩过三轮）。" >&2
            echo "!!   修法：① 装宿主 arm-gcc（apt-get install gcc-arm-linux-gnueabihf）" >&2
            echo "!!        ② 或 pip install ziglang" >&2
            echo "!!        ③ 或显式 CC='<zig> cc' 调用。" >&2
            return 13
        fi
    fi

    # C++：把结尾的 cc / gcc 换成 c++ / g++。
    # ★ 必须**按后缀优先级**（gcc 先于 cc），否则 `arm-linux-gnueabihf-gcc`
    #   会先命中 "…cc$" 规则被切成 `arm-linux-gnueabihf-g c++`（实测踩过）。
    # ★ 用 `#` 作 sed 分隔符：模式里的 alternation `|` 与 `s|…|…|` 冲突（自证抓过）。
    CXX=$(printf '%s' "$CC" | sed -E \
        -e 's#(^|[/ ])arm-linux-gnueabihf-gcc$#\1arm-linux-gnueabihf-g++#' \
        -e 's#(^|[/ ])arm-buildroot-linux-gnueabihf-gcc$#\1arm-buildroot-linux-gnueabihf-g++#' \
        -e 's#(^|[/ ])gcc$#\1g++#' \
        -e 's#[[:space:]]+cc$# c++#')

    CGM_CC_SELF="$CC"
    CGM_CXX_SELF="$CXX"
    export CC CXX
    if [ "${CGM_CC_QUIET:-0}" != "1" ]; then
        echo "  [cc-probe] CC=$CC"
        echo "  [cc-probe] CXX=$CXX"
    fi
    return 0
}

# 只在被 source 时执行（避免被直接执行时无谓退出）
cgm_cc_probe || exit $?
