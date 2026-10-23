#!/bin/sh
# cnb_upgrade_selftest.sh —— L4 目的 2 两个升级草稿的**首次编译 + 自测**（云上 zig/qemu）
#
# 背景：report/L4-evdev-sram-design.md §6 明确写「草稿未在目标编译链上编译通过」
#   （本机无 zig、bootlin63 是 Linux 二进制）。本脚本把这件事一次做完：
#     ① 编 `evdev_gamepad.c`（-DEVDEV_SELFTEST）→ 断言 struct input_event==16、BTN_* 映射
#     ② 编 `sram_persist.c`（-DSRAM_SELFTEST）→ **用真 core** dlopen + dlsym + size + round-trip
#     ③ 两处都用真设备 sysroot 跑（qemu-arm-static -L），输出逐条判据
#
# 用法：sh tools/cnb_upgrade_selftest.sh            # 新开工作区
#       WS_SN=<sn> UP_SET=none sh tools/cnb_upgrade_selftest.sh
set -u

# ★ 守卫自检（FAIL 即拒跑，不靠人看输出）
_guard() {
    for _py in python3 python; do
        command -v "$_py" >/dev/null 2>&1 || continue
        [ -f "tools/ssh_literal_guard.py" ] || return 0
        "$_py" tools/ssh_literal_guard.py "$0" >/tmp/_wslg.txt 2>&1 && return 0
        echo "!! ssh_literal_guard FAIL ⇒ 拒绝执行" >&2
        tail -6 /tmp/_wslg.txt >&2
        return 1
    done
    return 0
}
_guard || exit 9

REPO="${REPO:-lieguch/cubeGM}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CNB_DIR="/c/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/cnb"
export PATH="$PATH:$CNB_DIR"
OUTDIR="$ROOT/report/upgrade"
mkdir -p "$OUTDIR"
NONCE="$(date -u +%s 2>/dev/null || echo 0)-$$"
UP_SET="${UP_SET:-all}"

echo "== 1) 工作区 =="
SN="${WS_SN:-}"; A="${WS_SSH:-}"
if [ -z "$SN" ] && [ -z "$A" ]; then
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" \
        | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
fi
echo "   sn=${SN:-?}"
if [ -z "$A" ]; then
    i=0
    while [ -z "$A" ] && [ "$i" -lt 24 ]; do
        D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
        A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
        i=$((i + 1)); [ -n "$A" ] || sleep 12
    done
fi
[ -n "$A" ] || { echo "!! 未取到 ssh（可用 WS_SSH=）" >&2; exit 13; }
echo "   ssh=$A"
echo "$SN" > "$OUTDIR/.sn"; echo "$A" > "$OUTDIR/.ssh"

set_list() {
    TC=""
    [ -f cache_tc/bootlin63.tar.bz2 ] && TC="cache_tc/bootlin63.tar.bz2"
    case "$UP_SET" in
        all) echo "tools src/upgrade build/_exp/roms build/_exp/1941.zip golden/device_rootfs_min golden/sdcard_min/controller_db.txt golden/sdcard_min/cores/libemu_cps2.so golden/sdcard_min/cores/libemu_snes9x.so golden/sdcard_min/cores/libemu_md.so golden/sdcard_min/cores/libemu_mgba.so golden/sdcard_min/cores/libemu_tgbdual.so $TC" ;;
        src)  echo "tools src/upgrade build/_exp/roms" ;;
        none) echo "" ;;
        *) echo "!! 未知 UP_SET" >&2; return 1 ;;
    esac
}
SET="$(set_list)" || exit 9
upload_src() { if [ -z "$SET" ]; then :; else tar czf - $SET 2>/dev/null; fi; }
echo "== 2) 上传: ${SET:-（无）} =="

upload_src | timeout 3000 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=30 "$A" \
      "set -u
       for d in /workspace/1to1 /workspace; do [ -d \"\$d/tools\" ] && PROJ=\$d && break; done
       PROJ=\${PROJ:-}; L=/tmp/upgrade.log
       { echo \"PROJ=\$PROJ\"; date -u; } > \$L
       echo \"RUN-NONCE=$NONCE\" >> \$L
       [ -n \"\$PROJ\" ] || { echo 'PROJ 未找到'; exit 9; }
       cd \"\$PROJ\" || exit 9
       tar xzf - --no-same-owner 2>>\$L || echo '  (无上传流，沿用已有文件)' >> \$L

       echo '=== 依赖 ===' >> \$L
       for _w in 1 2 3 4 5 6 7 8 9 10 ; do
         [ -e /var/lib/dpkg/lock-frontend ] || break
         fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || break
         echo "  等 apt 锁释放（第 \$_w 次）" >> \$L
         sleep 10
       done
       apt-get clean >>\$L 2>&1 || true
       rm -rf /var/cache/apt/archives >>\$L 2>&1 || true
       mkdir -p /var/cache/apt/archives/partial >>\$L 2>&1 || true
       Q=\$(command -v qemu-arm-static || true)
       if [ -z \"\$Q\" ]; then
         (DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
          DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --reinstall qemu-user-static) >>\$L 2>&1 || true
         Q=\$(command -v qemu-arm-static || command -v qemu-arm || true)
       fi
       command -v bzip2 >/dev/null 2>&1 || (DEBIAN_FRONTEND=noninteractive apt-get install -y -qq bzip2) >>\$L 2>&1 || true
       echo \"qemu=\$Q bzip2=\$(command -v bzip2 || echo 缺)\" >> \$L
       [ -n \"\$Q\" ] || { echo '★★ 装不上 qemu'; exit 11; }

       ZIG=\$(python3 -c 'import os,ziglang;print(os.path.join(os.path.dirname(ziglang.__file__),\"zig\"))' 2>/dev/null || true)
       if [ -z \"\$ZIG\" ] || [ ! -x \"\$ZIG\" ]; then
         python3 -m pip install -q --break-system-packages ziglang >>\$L 2>&1 || true
         ZIG=\$(python3 -c 'import os,ziglang;print(os.path.join(os.path.dirname(ziglang.__file__),\"zig\"))' 2>/dev/null || true)
       fi
       echo \"zig=\${ZIG:-缺}\" >> \$L
       [ -n \"\$ZIG\" ] || { echo '★★ 无 zig'; exit 11; }

       echo '=== 设备真 sysroot ===' >> \$L
       rm -rf /arm-root-device; mkdir -p /arm-root-device
       cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>\$L
       rm -f /arm-root-device/MANIFEST.sha256
       [ -e /arm-root-device/lib/ld-linux-armhf.so.3 ] || ln -sf ld-2.29.so /arm-root-device/lib/ld-linux-armhf.so.3

       echo '=== 编译 src/upgrade 三件套（真模块）===' >> \$L
       \${ZIG} cc -target arm-linux-gnueabihf.2.29 -O2 -Wall -I src/upgrade \
         -o /tmp/upgrade_selftest \
         src/upgrade/selftest.c src/upgrade/sram_persist.c src/upgrade/evdev_gamepad.c \
         -ldl >>\$L 2>&1 && echo '  BUILD_OK' >> \$L || echo '  ** BUILD_FAIL' >> \$L

       echo '=== 铺全量手柄库 ===' >> \$L
       mkdir -p /sdcard/cubegm
       cp -f golden/sdcard_min/controller_db.txt /sdcard/cubegm/controller_db.txt 2>>\$L || true
       wc -l /sdcard/cubegm/controller_db.txt >> \$L 2>&1 || true
       mkdir -p /sdcard/000 && cp -f build/_exp/1941.zip /sdcard/000/1941.zip 2>>\$L || true

       echo '=== 跑自测（evdev 全量库 + sram 真 core）===' >> \$L
       for CN in cps2 md mgba snes9x ; do
         CORE=\"\$PROJ/golden/sdcard_min/cores/libemu_\$CN.so\"
         ROM=\"\$PROJ/build/_exp/roms/md_sram.bin\"
         if [ \"\$CN\" = \"cps2\" ]; then ROM=/sdcard/000/1941.zip; fi
         echo \"  --- core=\$CN rom=\$ROM ---\" >> \$L
         timeout 60 \$Q -L /arm-root-device \
           -E LD_LIBRARY_PATH=/arm-root-device/usr/lib:/arm-root-device/lib \
           -E CGM_CTRL_DB=/sdcard/cubegm/controller_db.txt \
           /tmp/upgrade_selftest \"\$CORE\" \"\$ROM\" /tmp >>\$L 2>&1
         echo \"    exit=\$?\" >> \$L
       done

       echo '=== .srm 产物 ===' >> \$L
       ls -l /tmp/_sram_selftest.srm 2>/dev/null | sed 's/^/  /' >> \$L || echo '  (无 .srm)' >> \$L
       echo REMOTE-DONE >> \$L
       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"
echo "   ssh rc=$?"

echo "== 3) 取回 =="
sh "$ROOT/tools/cnb_ws_fetch.sh" "$A" /tmp/upgrade.log "$OUTDIR/upgrade.log" 2>/dev/null || true
[ -f "$OUTDIR/upgrade.log" ] && grep -q "RUN-NONCE=$NONCE" "$OUTDIR/upgrade.log" || { echo "!! 无有效结果" >&2; exit 22; }

sed -n '1,120p' "$OUTDIR/upgrade.log"
echo "== 完成。产物在 $OUTDIR =="
echo "   省钱：cnb workspace workspace-stop --sn $SN"
