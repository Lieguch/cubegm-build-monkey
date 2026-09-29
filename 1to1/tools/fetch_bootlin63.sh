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
if command -v curl >/dev/null 2>&1; then
    EXP=$(curl -fsIL --connect-timeout 20 "$URL" 2>/dev/null | tr -d '\r' \
          | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')
fi
if [ -n "${EXP:-}" ]; then
    echo "   期望大小（Content-Length）= $EXP B"
else
    echo "   ★ 取不到 Content-Length ⇒ 仅做 bzip2 -t 完整性校验"
fi

_dl() {
    if command -v curl >/dev/null 2>&1; then
        curl -fL --retry 5 --retry-delay 3 -C - --connect-timeout 20 -o "$TB" "$URL"
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
    if [ -z "${EXP:-}" ] && [ "$NOW" -gt 0 ] && bzip2 -t "$TB" 2>/dev/null; then break; fi
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
bzip2 -t "$TB" 2>/dev/null || { echo "!! bzip2 完整性校验失败 ⇒ 删掉损坏包" >&2; rm -f "$TB"; exit 3; }
echo "   bzip2 -t 校验通过"

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
