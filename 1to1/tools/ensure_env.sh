#!/bin/sh
# ensure_env.sh —— 云开发/CI 环境的**幂等自愈 + fail-closed 前置检查**
#
# ★ 为什么必须有这个（第 139 轮真实事故）：
#   CNB 云工作区跨天会被回收并重建容器 ⇒ 容器里 apt 装过的东西**全部丢失**。
#   第 139 轮实测：`/usr/bin/qemu-arm-static` 消失 ⇒ 所有差分实验 `exit=127`，
#   而当时我正在查"代码为什么不跑"，实际是**环境没了**。
#   更危险的是：`pty_exec.py` 会把 exec 失败包装成
#   `Error while loading …: Exec format error` 写到 **stdout** ⇒
#   两侧都失败时 `diff` 得到"逐字相同" ⇒ **假绿**。
#   本脚本把"环境是否可用"变成**显式的前置门禁**，让环境退化不再伪装成代码问题。
#
# 用法：
#   . tools/ensure_env.sh          # 装缺失的包；缺关键工具 ⇒ exit 13
#   CGM_ENV_NO_INSTALL=1 . tools/ensure_env.sh   # 只检查不安装（CI 用，缺即报错）
#
# 判据纪律：
#   · **只装"缺"的**（已存在就跳过 ⇒ 幂等，多次调用无副作用）
#   · **离线/无 root/无包管理器**时**不静默通过** ⇒ 明确 exit 13
#   · 装完**必须实测**（`qemu-arm-static --version` / `bzip2 --version`），
#     不能只看 `dpkg -s` 的返回值

set -u

CGM_ENV_NO_INSTALL="${CGM_ENV_NO_INSTALL:-0}"
CGM_ENV_QUIET="${CGM_ENV_QUIET:-0}"

say() { [ "$CGM_ENV_QUIET" = "1" ] || echo "$@"; }

# ---- 探测包管理器（三选一） ----
PM=""
for m in apt-get dnf yum apk; do
    if command -v "$m" >/dev/null 2>&1; then PM="$m"; break; fi
done
say "[env] 包管理器 = ${PM:-（无）}"

# ---- 逐个工具：<名字> <探测命令…> <apt 包名> ----
# 用法：need_tool "qemu-arm-static" "qemu-arm-static --version" "qemu-user-static"
missing_critical=""
install_one() {
    _name="$1"; _probe="$2"; _pkg="$3"
    if sh -c "$_probe" >/dev/null 2>&1; then
        say "[env] OK   $_name"
        return 0
    fi
    if [ "$CGM_ENV_NO_INSTALL" = "1" ]; then
        say "[env] 缺   $_name（只检查模式 ⇒ 报错退出）"
        missing_critical="$_name $missing_critical"
        return 1
    fi
    if [ -z "$PM" ]; then
        say "[env] 缺   $_name，且无包管理器可装"
        missing_critical="$_name $missing_critical"
        return 1
    fi
    say "[env] 装   $_name（apt 包：$_pkg）…"
    case "$PM" in
        apt-get)
            # ★★ 第 139 轮自证抓到的真缺陷（必须保留 --reinstall）：
            #   若「dpkg 记录为已安装、但文件被删/被 mv 走」（容器重建、清理脚本、手工删），
            #   普通 `apt-get install -y` 会判定"已是最新"⇒ **空操作、rc=0、什么都不装**，
            #   而后面的实测会失败 ⇒ 报「装了但仍不可用」。
            #   实测正是这样：`dpkg -s` 显示 `install ok installed`，
            #   但 `command -v qemu-arm-static` 为空。
            #   ⇒ 先按常规装；**装完实测失败则必须 --reinstall 强制重装**。
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$_pkg" >/dev/null 2>&1
            if ! sh -c "$_probe" >/dev/null 2>&1; then
                say "[env]      （dpkg 状态与实际不符 ⇒ --reinstall 强制重装）"
                DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --reinstall "$_pkg" >/dev/null 2>&1
            fi
            ;;
        dnf)     dnf install -y -q "$_pkg" >/dev/null 2>&1 ;;
        yum)     yum install -y -q "$_pkg" >/dev/null 2>&1 ;;
        apk)     apk add --no-cache "$_pkg" >/dev/null 2>&1 ;;
    esac
    # ★ 装完**实测**，不信包管理器的返回值
    if sh -c "$_probe" >/dev/null 2>&1; then
        say "[env] OK   $_name（已装并实测通过）"
        return 0
    fi
    say "[env] FAIL $_name（装了但仍不可用）"
    missing_critical="$_name $missing_critical"
    return 1
}

# qemu-user-static：差分验证的唯一执行引擎（第 139 轮：丢了就全盘 exit=127）
install_one "qemu-arm-static" "qemu-arm-static --version" "qemu-user-static"
# bzip2：tools/fetch_bootlin63.sh 解压 toolchain tarball 必需（缺则 fail-closed）
install_one "bzip2" "bzip2 --version" "bzip2"
# binutils：readelf/objdump 读 .ARM.attributes 与程序头（定位 ABI/段问题必需）
install_one "readelf" "readelf --version" "binutils"

if [ -n "$missing_critical" ]; then
    say ""
    say "[env] ★ 关键工具缺失且无法补齐：$missing_critical"
    say "[env]   ⇒ 这是**环境问题，不是代码问题**。禁止把 exit=127 / 空输出"
    say "[env]     当成 program's 行为（那会产生假绿）。请修好环境后重跑。"
    exit 13
fi

say "[env] 全部就绪"
exit 0
