#!/bin/sh
# ============================================================
# fetch_bootlin63.sh —— 幂等抓取「工厂同期工具链」Bootlin 2017.05（GCC 6.3 / glibc 2.24 /
#                      binutils 2.27）到 cache_tc/bootlin63。
#
# 为什么主链需要它（2026-09-28 取证）：
#   工厂 rkgame 的 `.gnu.version_r` / CRT DWARF 表明它与本工具链**同族**：
#     · glibc 2.24（工厂 CRT 的 DW_AT_producer / comp_dir 实证）
#     · binutils 2.27、GCC 6.x
#   而链接期需要四个**只在工具链里才有**的输入（设备 rootfs 只有运行时 .so）：
#     sysroot/usr/lib/crt1.o、sysroot/usr/lib/libc_nonshared.a、
#     sysroot/usr/lib/libpthread_nonshared.a、lib/gcc/<triple>/6.3.0/libgcc.a
#   同时 sysroot/lib/libc.so.6 等 .so 也直接用作链接输入
#   ⇒ 产物 DT_NEEDED = 7 项、符号版本需求、`__aeabi_*` 静态助手形态**全部与工厂对齐**。
#
# 幂等：cache_tc/bootlin63/.ok 存在即直接返回（**注意**：判据是 `-f` 而不是 `-x` ——
#       第 66 轮的教训：`.ok` 是 `touch` 建的 0644，用 `-x` 判会永远不命中、静默重下）。
#
# 环境：BOOTLIN63_URL 可覆盖源地址（默认 toolchains.bootlin.com）。
# ============================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 9

D="cache_tc/bootlin63"
URL="${BOOTLIN63_URL:-https://toolchains.bootlin.com/downloads/releases/toolchains/armv7-eabihf/tarballs/armv7-eabihf--glibc--bleeding-edge-2017.05-toolchains-1-1.tar.bz2}"

if [ -f "$D/.ok" ]; then
    echo "bootlin63 已就绪（cache hit）：$D"
    exit 0
fi

echo "== 抓取 Bootlin 2017.05（armv7-eabihf / glibc / bleeding-edge）=="
mkdir -p cache_tc
TB="cache_tc/bootlin63.tar.bz2"

# ★ 期望大小（Content-Length）。拿不到就退化为"只做 bzip2 -t 完整性校验"。
# 为什么必须核对（2026-09-29 实测缺陷）：旧版只看 `[ ! -s "$TB" ]`，
#   **59.7 MB 的截断包照样通过** ⇒ 解压才炸；而且失败时只删 $D **不删 $TB**
#   ⇒ 下一次直接复用**损坏缓存**、确定性再失败。本次云开发上就是这个现象。
EXP=""
# ★ 本地源模式：期望大小直接从本地文件取，**不发起任何网络请求**
if [ -n "${BOOTLIN63_LOCAL:-}" ] && [ -s "${BOOTLIN63_LOCAL}" ]; then
    EXP=$(stat -c%s "$BOOTLIN63_LOCAL" 2>/dev/null || stat -f%z "$BOOTLIN63_LOCAL" 2>/dev/null || echo "")
    echo "   本地 tar 模式：期望大小 = ${EXP:-?} B（不查Content-Length）"
elif command -v curl >/dev/null 2>&1; then
    EXP=$(curl -4 -fsIL --connect-timeout 20 "$URL" 2>/dev/null | tr -d '\r' \
          | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')
fi
if [ -n "${EXP:-}" ]; then
    echo "   期望大小（Content-Length）= $EXP B"
else
    echo "   ★ 取不到 Content-Length ⇒ 仅做 bzip2 -t 完整性校验"
fi

# ★★ 2026-10-03（第 121 轮，判据 TC-DOWNLOAD-DEFECT.md T5）**本地缓存源优先**。
#   病灶（实测云端 cnb-a2n-1k40p84gg）：CNB -> toolchains.bootlin.com（法国 OVH）
#   **IPv6 路由劣化**，即使`-4` 也只有 ~27 KB/s ⇒ 63 MB 要 **40 分钟**，
#   而**每换一个云工作区就要重下一次**（工作区是临时的，缓存不跨区）。
#   本机（Windows）对同一 URL **全速 >1 MB/s** ⇒ 正确做法是
#   **把 tar 当"待同步的构建输入"随源码一起送上去**，而不是让云端各自重下。
#   机制：`BOOTLIN63_LOCAL=<本地tar路径>`（或默认自动探测几个常见位置）⇒ 直接 cp，
#   完全跳过网络。判据 T5：指定 LOCAL 时 `_dl` 一次网络都不碰。
_dl() {
    # ---- 本地缓存优先（无网络开销）----
    if [ -n "${BOOTLIN63_LOCAL:-}" ]; then
        if [ -s "$BOOTLIN63_LOCAL" ]; then
            echo "   使用本地tar（BOOTLIN63_LOCAL）：$BOOTLIN63_LOCAL"
            cp -f "$BOOTLIN63_LOCAL" "$TB" && return 0
            echo "!! 本地 tar 复制失败" >&2
            return 4
        fi
        echo "!! BOOTLIN63_LOCAL 指向的文件不存在/为空：$BOOTLIN63_LOCAL" >&2
        return 4
    fi
    if command -v curl >/dev/null 2>&1; then
        # ★ `-4` 必带：IPv6 路由劣化（见上）；`--max-time` 不设上限，
        #   因为慢速下限时会把"仍在正常下载"误判为失败（宁可慢，不可假失败）。
        curl -4 -fL --retry 5 --retry-delay 3 -C - --connect-timeout 20 -o "$TB" "$URL"
    elif command -v wget >/dev/null 2>&1; then
        wget -c --tries=5 -O "$TB" "$URL"
    else
        echo "!! 既无 curl 也无 wget" >&2
        return 3
    fi
}

# 最多 4 轮：断点续传 + 大小核对（网络抖动能自愈，不自愈就 fail-closed）
_try=0
while :; do
    NOW=$(stat -c%s "$TB" 2>/dev/null || echo 0)
    if [ -n "${EXP:-}" ] && [ "$NOW" = "$EXP" ]; then break; fi
    # ★ 取不到Content-Length 时才靠 bzip2 判定；**bzip2 缺失则不能靠它**
    #   （否则永远不 break ⇒ 白下4 轮，见 2026-10-03 第121 轮的云端实测）。
    if [ -z "${EXP:-}" ] && [ "$NOW" -gt 0 ] \
       && { ! command -v bzip2 >/dev/null 2>&1 || bzip2 -t "$TB" 2>/dev/null; }; then
        break
    fi
    _try=$((_try + 1))
    [ "$_try" -gt 4 ] && break
    echo "   第 $_try 轮下载/续传（当前 $NOW / 期望 ${EXP:-?}）"
    _dl || true
    sleep 2
done

NOW=$(stat -c%s "$TB" 2>/dev/null || echo 0)
echo "  包大小 $NOW B"
if [ -n "${EXP:-}" ] && [ "$NOW" != "$EXP" ]; then
    echo "!! 下载不完整（$NOW != $EXP）⇒ 删掉半成品，避免毒化下一次" >&2
    rm -f "$TB"; exit 3
fi
# ★★ 2026-10-03（第 121 轮）**区分"校验器缺失"与"包损坏"**。
#   实测病灶：云工作区**没有 bzip2 命令**（`zsh: command not found: bzip2`）
#   ⇒ 旧版 `bzip2 -t "$TB" || {删包; exit 3;}` 会把**完好包误判为损坏并删掉**
#   ⇒ 而它删的正是刚上传/刚下载好的 63 MB（下一轮又得重传 40 分钟）。
#   根治：工具不存在 ⇒ **明确告知并降级为"只靠大小核对"**（不删包）；
#         工具存在且校验失败 ⇒ 才是真损坏，删包。
if command -v bzip2 >/dev/null 2>&1; then
    if bzip2 -t "$TB" 2>/dev/null; then
        echo "   bzip2 -t 校验通过"
    else
        echo "!! bzip2 完整性校验失败（工具在）⇒ 删掉损坏包" >&2
        rm -f "$TB"; exit 3
    fi
else
    echo "★ 本机**无 bzip2 命令** ⇒ 跳过完整性校验，仅靠大小核对（$NOW / ${EXP:-?}）"
    echo "  （不是'校验通过'，是**不可判**；解压失败会另行报错）"
fi

rm -rf "$D"; mkdir -p "$D"
# ★ 必须用 -j（.tar.bz2）—— 用错解压器的现象是"下载成功但解压失败"，与下载失败同表
tar -xjf "$TB" -C "$D" --strip-components=1 || { echo "!! 解压失败（确认是 .tar.bz2）" >&2; rm -rf "$D"; exit 4; }

TC="cache_tc/bootlin63/arm-buildroot-linux-gnueabihf"
for f in "$TC/sysroot/usr/lib/crt1.o" "$TC/sysroot/usr/lib/libc_nonshared.a" \
         "$TC/sysroot/lib/libc.so.6" "$TC/lib/libstdc++.so.6"; do
    [ -f "$f" ] || { echo "!! 解压后缺关键文件：$f" >&2; rm -rf "$D"; exit 5; }
done
LG=$(ls "$TC"/../lib/gcc/arm-buildroot-linux-gnueabihf/*/libgcc.a 2>/dev/null | head -1)
[ -n "$LG" ] || { echo "!! 解压后缺 libgcc.a" >&2; rm -rf "$D"; exit 6; }

touch "$D/.ok"
echo "bootlin63 就绪：$D"
