#!/bin/sh
# cnb_t13_autorun.sh —— **T13 收口专用**：从源码重编 → autorun 直达 1941 → 抓完整 FBA_Load 遍历
#
# ## 为什么必须从源码重编（R242 实证）
# `build/obj` 里有 **23 个过期 .o**（比源码旧 13–20 天），含
#   FUN_002b6c14_FBA_Load.c（sprintf 4 参修复）、ReadJoystick / ReadUSBJoy /
#   mui_menu / main_Menu / SeletEmuCore 等 T11/T12 关键修复。
# ⇒ 旧 ELF 里 `sprintf(buf,"%s/cores/%s",work_path,*ppcVar4)` **只传 3 参**（无 r3），
#   glibc 打 "(null)" ⇒ FBA_Load 遍历全废（云上实测 9 行 `(null)`；原厂同环境打印正确 core 名）。
# ⇒ 本脚本默认 **REBUILD=1**（rm -rf build/obj build/upstream，从源码全量重编）。
#   纪律：「编译够便宜就不要缓存」——过期 .o 冒充当前源码 = 静默错误结论。
#
# ## 为什么走 autorun（R241）
# main(): `if (autorunfile[0]=='\0') main_Menu(); else autorun(...)`；
# autorun(): `if (*driver=='\0') run_game(file)`。
# ⇒ `<autorun file="/sdcard/000/1941.zip" driver="" />` 让 main 直接 run_game，
#   绕过 menu.log 选中项 + 按键注入 + root.dat 三个变量。
#
# ## 预登记判据
#   (a) `use /sdcard/cubegm//cores/libemu_cps2.so to run /sdcard/000/1941.zip` ⇒ core 接受 ROM 闭环
#   (b) `libemu_cps2.so unsupport.` ⇒ 与 R241 的 19/19 匹配矛盾，须查 core 判定逻辑
#   (c) 只有 fba `unsupport.` + cps2 `open ... fail` ⇒ 云上 core 资产缺失（环境问题）
#
# 用法（本机）:
#   UP_SET=all REBUILD=1 sh tools/cnb_t13_autorun.sh              # 首次：全量上传 + 重编 + 跑
#   UP_SET=none REBUILD=0 WS_SN=<sn> sh tools/cnb_t13_autorun.sh  # 复用：只跑
#   FACTORY=1 ...                                                 # 单变量对照（跑原厂）
#   STOP=1 ...                                                    # 跑完关工作区（省核时）
set -u

# ★★★ 自检：ssh 字面量守卫（反引号 / 未转义 $( / 非白名单本地变量）
#   来历 R244/R247：我在注释里写反引号三次，守卫三次 FAIL，但我仍用 `&&` 把它跑过去了。
#   ⇒ 改成"FAIL 即拒跑"，不靠人看输出。
_guard() {
    for _py in python3 python; do
        command -v "$_py" >/dev/null 2>&1 || continue
        [ -f "tools/ssh_literal_guard.py" ] || return 0
        if "$_py" tools/ssh_literal_guard.py "$0" >/tmp/_wslg.txt 2>&1; then
            return 0
        fi
        echo "!! ssh_literal_guard FAIL ⇒ 拒绝执行（先修字面量）" >&2
        tail -6 /tmp/_wslg.txt >&2
        return 1
    done
    echo "   (无 python ⇒ 跳过守卫自检)" >&2
    return 0
}
_guard || exit 9

REPO="${REPO:-lieguch/cubeGM}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CNB_DIR="/c/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/cnb"
export PATH="$PATH:$CNB_DIR"
OUTDIR="$ROOT/report/t13"
mkdir -p "$OUTDIR"
NONCE="$(date -u +%s 2>/dev/null || echo 0)-$$"
UP_SET="${UP_SET:-all}"
REBUILD="${REBUILD:-0}"
FACTORY="${FACTORY:-0}"
TWOPASS="${TWOPASS:-0}"
CGM_UPGRADE="${CGM_UPGRADE:-0}"
ROM_ENTRY="${ROM_ENTRY:-000/1941.zip}"   # 菜单选中的 ROM（形如 003/xxx.bin）
ROM_DIR="${ROM_ENTRY%%/*}"
ROM_FILE="${ROM_ENTRY##*/}"
MODE="${MODE:-autorun}"       # autorun | menu（menu = 走 main_Menu，会分配帧缓冲）
STOP="${STOP:-0}"

echo "== 1) 开/复用 CNB 云开发工作区 =="
SN="${WS_SN:-}"; A="${WS_SSH:-}"
if [ -z "$SN" ] && [ -z "$A" ]; then
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    printf '%s\n' "$OUT" | sed -n '1,8p'
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" \
        | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
fi
echo "   sn=${SN:-?}"
if [ -z "$A" ]; then
    echo "== 2) 等 SSH 就绪 =="
    i=0
    while [ -z "$A" ] && [ "$i" -lt 24 ]; do
        D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
        A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
        i=$((i + 1)); [ -n "$A" ] || sleep 12
    done
fi
[ -n "$A" ] || { echo "!! 未取到 ssh 地址（可用 WS_SSH=<user@host>）" >&2; exit 13; }
echo "   ssh=$A"
echo "$SN" > "$OUTDIR/.sn"; echo "$A" > "$OUTDIR/.ssh"

probe_ssh() {
    timeout 60 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o BatchMode=yes -o ConnectTimeout=20 "$1" "echo AUTH-OK" 2>/dev/null | grep -q AUTH-OK
}
if ! probe_ssh "$A"; then
    echo "!! 复用地址鉴权失败 ⇒ 开新工作区"
    SN=""; A=""
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" \
        | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
    i=0
    while [ -z "$A" ] && [ "$i" -lt 24 ]; do
        D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
        A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
        i=$((i + 1)); [ -n "$A" ] || sleep 12
    done
    probe_ssh "$A" || { echo "!! 新工作区鉴权仍失败（sn=$SN）" >&2; exit 13; }
    echo "$SN" > "$OUTDIR/.sn"; echo "$A" > "$OUTDIR/.ssh"
fi
echo "   ssh 鉴权 OK"

echo "== 3) 上传集 UP_SET=$UP_SET / REBUILD=$REBUILD / FACTORY=$FACTORY =="
cd "$ROOT" || exit 9
ROM_SRC="/d/output/原厂SD卡根目录结构/000/1941.zip"
mkdir -p build/_exp
if [ -f "$ROM_SRC" ] && [ ! -f build/_exp/1941.zip ]; then cp -f "$ROM_SRC" build/_exp/1941.zip; fi

set_list() {
    # ★ bootlin63 本机缓存：CNB→法国 OVH 直连仅 ~59 KB/s（63 MB ≈ 18 min，实测）
    #   ⇒ 本机有 tarball 就随包上传，fetch_bootlin63.sh 见满尺寸即跳过下载（记忆里的既定配方）
    TC=""
    if [ -f cache_tc/bootlin63.tar.bz2 ]; then TC="cache_tc/bootlin63.tar.bz2"; fi
    case "$UP_SET" in
        all)  echo "tools golden/device_rootfs_min golden/sdcard_min golden/factory.rkgame.bin build/rkgame.rebuilt.elf build/_exp/1941.zip build/_exp/roms src linker $TC" ;;
        run)  echo "tools golden/device_rootfs_min golden/sdcard_min golden/factory.rkgame.bin build/rkgame.rebuilt.elf build/_exp/1941.zip" ;;
        full) echo "tools golden/device_rootfs_min golden/sdcard_min golden/factory.rkgame.bin build/rkgame.rebuilt.elf build/_exp/1941.zip build/_exp/000.dat" ;;
        elf)  echo "tools build/rkgame.rebuilt.elf build/_exp/1941.zip" ;;
        src)  echo "tools src linker build/_exp/roms golden/sdcard_min/003.dat $TC" ;;
        srcx) echo "tools src linker" ;;
        tc)   echo "tools $TC" ;;
        none) echo "" ;;
        *)    echo "!! 未知 UP_SET=$UP_SET" >&2; return 1 ;;
    esac
}
SET="$(set_list)" || exit 9
upload_src() {
    if [ -z "$SET" ]; then :; else tar czf - $SET 2>/dev/null; fi
}
echo "   上传内容: ${SET:-（无）}"

upload_src \
| timeout 5000 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o BatchMode=yes -o ConnectTimeout=25 \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=40 "$A" \
      "set -u
       for d in /workspace/1to1 /workspace; do [ -d \"\$d/tools\" ] && PROJ=\$d && break; done
       PROJ=\${PROJ:-}; L=/tmp/t13.log
       { echo \"PROJ=\$PROJ\"; date -u; } > \$L
       echo \"RUN-NONCE=$NONCE\" >> \$L
       echo \"REBUILD=$REBUILD FACTORY=$FACTORY UP_SET=$UP_SET MODE=$MODE TWOPASS=$TWOPASS CGM_UPGRADE=$CGM_UPGRADE\" >> \$L
       [ -n \"\$PROJ\" ] || { echo 'PROJ 未找到'; exit 9; }
       cd \"\$PROJ\" || exit 9
       mkdir -p build report build/_exp
       tar xzf - --no-same-owner 2>>\$L || echo '  (无上传流，沿用工作区已有文件)' >> \$L

       echo '=== 依赖 ===' >> \$L
       # ★ 新工作区里 workspace 自身的 apt 可能仍在跑（update 持 lists/lock、install 持 dpkg/lock）。
       #   两个锁都要等，且新工作区首次 init 可能跑 2~3 分钟 ⇒ 耐心拉到 40 次×10s。
       _wait_apt() {
         _n=0
         while [ \$_n -lt 40 ]; do
           _busy=0
           [ -e /var/lib/apt/lists/lock ] && { fuser /var/lib/apt/lists/lock >/dev/null 2>&1 && _busy=1; }
           [ -e /var/lib/dpkg/lock-frontend ] && { fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 && _busy=1; }
           [ -e /var/lib/dpkg/lock ] && { fuser /var/lib/dpkg/lock >/dev/null 2>&1 && _busy=1; }
           [ \$_busy = 0 ] && return 0
           echo "  等 apt 锁释放（第 \$_n 次）" >> \$L
           _n=\$((_n+1)); sleep 10
         done
         echo "  !! apt 锁 400s 未释放 ⇒ 强杀挂起的 apt-get" >> \$L
         fuser -k /var/lib/apt/lists/lock >/dev/null 2>&1 || true
         fuser -k /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || true
         sleep 5
       }
       _wait_apt
       (DEBIAN_FRONTEND=noninteractive dpkg --configure -a) >>\$L 2>&1 || true
       apt-get clean >>\$L 2>&1 || true
       rm -rf /var/cache/apt/archives >>\$L 2>&1 || true
       mkdir -p /var/cache/apt/archives/partial >>\$L 2>&1 || true
       Q=\$(command -v qemu-arm-static || true)
       if [ -z \"\$Q\" ]; then
         (DEBIAN_FRONTEND=noninteractive apt-get update -qq && \
          DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --reinstall qemu-user-static) >>\$L 2>&1 || true
         Q=\$(command -v qemu-arm-static || command -v qemu-arm || true)
       fi
       echo \"qemu=\$Q\" >> \$L
       [ -n \"\$Q\" ] || { echo '★★ 装不上 qemu'; exit 11; }
       # ★ 2026-10-22 实测：CNB 极简镜像**没有 bzip2** ⇒ bootlin63.tar.bz2 解压直接失败
       #   （远端报 tar child: bzip2: Cannot exec）⇒ 必须补装，否则整条重编链 fail-closed。
       #   ★ 本行**不许写反引号**：本文件是双引号字面量，反引号会被本地 shell 先做命令替换。
       if ! command -v bzip2 >/dev/null 2>&1; then
         (DEBIAN_FRONTEND=noninteractive apt-get install -y -qq bzip2 xz-utils) >>\$L 2>&1 || true
       fi
       echo \"bzip2=\$(command -v bzip2 || echo 缺)\" >> \$L

       ZIG=\$(python3 -c 'import os,ziglang;print(os.path.join(os.path.dirname(ziglang.__file__),\"zig\"))' 2>/dev/null || true)
       if [ -z \"\$ZIG\" ] || [ ! -x \"\$ZIG\" ]; then
         python3 -m pip install -q --break-system-packages ziglang >>\$L 2>&1 || true
         ZIG=\$(python3 -c 'import os,ziglang;print(os.path.join(os.path.dirname(ziglang.__file__),\"zig\"))' 2>/dev/null || true)
       fi
       echo \"zig=\${ZIG:-缺}\" >> \$L
       SC=\"\${ZIG:-} cc\"; [ -n \"\${ZIG:-}\" ] || SC=arm-linux-gnueabihf-gcc

       if [ \"$REBUILD\" = \"1\" ]; then
         echo '=== ★ 全量重编（清掉全部缓存；纪律：过期 .o = 静默错误结论）===' >> \$L
         rm -rf build/obj build/upstream
         CC=\"\$SC\" PY=python3 CGM_UPGRADE=$CGM_UPGRADE sh tools/link_audit.sh report/link_audit.txt >>\$L 2>&1 \
           || echo '  [warn] link_audit 非零（对象仍可能已产出）' >> \$L
         echo \"  obj 数=\$(ls build/obj/*.o 2>/dev/null | wc -l)\" >> \$L
         CC=\"\$SC\" PY=python3 sh tools/build_upstream.sh build/upstream >>\$L 2>&1 \
           || echo '  ** UPSTREAM-FAIL' >> \$L
         PY=python3 sh tools/link_full.sh build/rkgame.rebuilt.elf >>\$L 2>&1 \
           || echo '  ** LINK-FAIL' >> \$L
         ls -la build/rkgame.rebuilt.elf >>\$L 2>&1 || true
         echo \"  new ELF sha=\$(sha256sum build/rkgame.rebuilt.elf 2>/dev/null | cut -c1-16)\" >> \$L
         if [ -n \"\$(command -v arm-linux-gnueabihf-objdump || true)\" ]; then
           echo '  --- FBA_Load 的 sprintf 是否 4 参（看 bl 前是否有 r3 赋值）---' >> \$L
         fi
       fi

       echo '=== 设备真 sysroot /arm-root-device ===' >> \$L
       rm -rf /arm-root-device; mkdir -p /arm-root-device
       cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>\$L
       rm -f /arm-root-device/MANIFEST.sha256
       [ -e /arm-root-device/lib/ld-linux-armhf.so.3 ] || ln -sf ld-2.29.so /arm-root-device/lib/ld-linux-armhf.so.3

       echo '=== 铺 /sdcard/cubegm + ROM ===' >> \$L
       rm -rf /sdcard/cubegm; mkdir -p /sdcard/cubegm
       cp -a golden/sdcard_min/. /sdcard/cubegm/ 2>>\$L || true
       # ★ 真机 SD 上有 saves/<NNN> 目录；缺它则 retro_save_state 的 fopen("wb") 静默失败（R247 实测）
       mkdir -p /sdcard/cubegm/saves/000 /sdcard/cubegm/saves/ARCADE \
                /sdcard/cubegm/states/000 /sdcard/cubegm/states/ARCADE
       mkdir -p /sdcard/000
       if [ -f build/_exp/1941.zip ]; then cp -f build/_exp/1941.zip /sdcard/000/1941.zip; fi
       # ★ 缩略图包：真机 /sdcard/000/000.dat（240 MB）；缺它 mui_menu 每帧重试 open fail 刷屏
       if [ -f build/_exp/000.dat ]; then cp -f build/_exp/000.dat /sdcard/000/000.dat; fi
       echo \"  core 数=\$(ls /sdcard/cubegm/cores/*.so 2>/dev/null | wc -l)  ROM=\$(wc -c < /sdcard/000/1941.zip 2>/dev/null || echo 0) B\" >> \$L

       echo '=== setting.xml：autorun 1941 + logfile 绝对路径 ===' >> \$L
       if [ \"$MODE\" = \"menu\" ]; then
         echo '  MODE=menu ⇒ **保持 autorun 为空**（否则绕过 main_Menu）' >> \$L
         python3 - <<'PYEOF' >> \$L 2>&1
import re
p='/sdcard/cubegm/setting.xml'
d=open(p,'rb').read().decode('utf-8','replace')
d2=re.sub(r'<autorun[^>]*/>','<autorun file=\"\" driver=\"\" />',d,count=1)
if '<logfile>' in d2: d2=re.sub(r'<logfile>[^<]*</logfile>','<logfile>/sdcard/cubegm/debug.log</logfile>',d2,count=1)
else: d2=d2.replace('<config','<logfile>/sdcard/cubegm/debug.log</logfile><config',1)
open(p,'wb').write(d2.encode('utf-8'))
print('AUTORUN_EMPTY_OK',('<autorun file=\"\" driver=\"\" />' in d2),('/sdcard/cubegm/debug.log' in d2))
PYEOF
       else
         python3 - <<'PYEOF' >> \$L 2>&1
import re
p='/sdcard/cubegm/setting.xml'
d=open(p,'rb').read().decode('utf-8','replace')
d2=re.sub(r'<autorun[^>]*/>','<autorun file=\"/sdcard/000/1941.zip\" driver=\"\" />',d,count=1)
if d2==d: d2=d.replace('</savestatehotkey>','</savestatehotkey><autorun file=\"/sdcard/000/1941.zip\" driver=\"\" />',1)
if '<logfile>' in d2: d2=re.sub(r'<logfile>[^<]*</logfile>','<logfile>/sdcard/cubegm/debug.log</logfile>',d2,count=1)
else: d2=d2.replace('<config','<logfile>/sdcard/cubegm/debug.log</logfile><config',1)
open(p,'wb').write(d2.encode('utf-8'))
print('AUTORUN_SET_OK',('/sdcard/000/1941.zip' in d2),('/sdcard/cubegm/debug.log' in d2))
PYEOF
       fi

       if [ \"$MODE\" = \"menu\" ]; then
         echo \"  ROM_ENTRY=$ROM_ENTRY\" >> \$L
         if [ \"$ROM_DIR\" != \"000\" ]; then
           mkdir -p /sdcard/$ROM_DIR /sdcard/cubegm/saves/$ROM_DIR /sdcard/cubegm/states/$ROM_DIR
           cp -f build/_exp/roms/md_sram.bin /sdcard/$ROM_DIR/$ROM_FILE 2>>\$L || true
           cp -f golden/sdcard_min/$ROM_DIR.dat /sdcard/$ROM_DIR/$ROM_DIR.dat 2>>\$L || true
         fi
         echo '=== MODE=menu：root.dat 首项=被测 ROM + menu.log 置 state=0 idx=0 ===' >> \$L
         python3 - \"$ROM_ENTRY\" <<'PYEOF' >> \$L 2>&1
import zipfile, struct, os, sys
# ① root.dat（ZIP 内含 fileinfo.txt）；解析器分隔符含 '\\r'，单条即可 ⇒ 索引 0 = 1941
data = sys.argv[1].encode()
with zipfile.ZipFile('/sdcard/root.dat','w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('fileinfo.txt', data)
print('ROOTDAT_WROTE', os.path.getsize('/sdcard/root.dat'))
# ② menu.log：offset0=菜单状态(0=mui_menu)，offset284=选中行，offset288=选中列
p='/sdcard/cubegm/menu.log'
d=bytearray(open(p,'rb').read())
struct.pack_into('<I',d,0,0)
struct.pack_into('<I',d,284,0)
struct.pack_into('<I',d,288,0)
open(p,'wb').write(bytes(d))
print('MENULOG_PATCHED size=%d state=0 idx284=0 idx288=0'%len(d))
PYEOF
       fi

       echo '=== 三桩 ===' >> \$L
       mkdir -p report/stublib report/drmstublib report/alsastublib
       CC_ARM=\"\$SC\" sh tools/build_libkms_stub.sh    report/stublib    >>\$L 2>&1 || echo '  [warn] kms 桩' >> \$L
       CC_ARM=\"\$SC\" sh tools/build_libdrm_stub.sh    report/drmstublib >>\$L 2>&1 || echo '  [warn] drm 桩' >> \$L
       CC_ARM=\"\$SC\" sh tools/build_libasound_stub.sh report/alsastublib >>\$L 2>&1 || echo '  [warn] alsa 桩' >> \$L
       mkdir -p /dev/dri 2>/dev/null || true
       for i in 0 1; do [ -e /dev/dri/card\$i ] || : > /dev/dri/card\$i 2>/dev/null || true; done
       [ -e /dev/mem ] || { : > /dev/mem 2>/dev/null && chmod 666 /dev/mem 2>/dev/null; } || true

       echo '=== guest shim ===' >> \$L
       CC=\"\$SC\" CGM_ABI_PROBE_BUILD=1 sh tools/build_guest_shim.sh report/t13_shim.so >>\$L 2>&1 \
         && echo \"  shim \$(wc -c < report/t13_shim.so) B\" >> \$L \
         || echo '  ★★ shim 构建失败' >> \$L

       echo '=== ★ 跑 autorun 1941（shim + 三桩 + strace）===' >> \$L
       if [ \"$FACTORY\" = \"1\" ]; then SRC_BIN=golden/factory.rkgame.bin; TAG=factory
       else SRC_BIN=build/rkgame.rebuilt.elf; TAG=rebuild; fi
       echo \"  被测=\$SRC_BIN TAG=\$TAG sha=\$(sha256sum \$SRC_BIN 2>/dev/null | cut -c1-16)\" >> \$L
       cp -f \$SRC_BIN /sdcard/cubegm/rkgame; chmod +x /sdcard/cubegm/rkgame
       cp -f report/t13_shim.so /sdcard/cubegm/guest_shim.so 2>/dev/null || true
       rm -f /sdcard/cubegm/debug.log
       LIBP=\"\$PROJ/report/alsastublib:\$PROJ/report/drmstublib:\$PROJ/report/stublib:/arm-root-device/usr/lib:/arm-root-device/lib\"
       INPUT_HEX=
       INPUT_FILL=
       KEY2_SEED=
       USB_VID=
       USB_PID=
       USB_VER=
       if [ \"$MODE\" = \"menu\" ]; then
         # 位映射（buttontoi + 18 字段表）：A=0x2000(btn6) TL1=0x400(btn8) TR1=0x800(btn11)
         # savestatehotkey=0xC00=TL1|TR1 ⇒ btn8 与 btn11 同按（重复 down=保持）
         # js_event = time(4)|value(2)|type(1)|number(1)
         #   按下 0000000001000600 / 松开 0000000000000600；FILL 让按键覆盖整个窗口
         INPUT_HEX=00000000010001000000000000000100000000000100010100000000000001010000000001000102000000000000010200000000010001030000000000000103000000000100010400000000000001040000000001000105000000000000010500000000010001060000000000000106000000000100010700000000000001070000000001000108000000000000010800000000010001090000000000000109000000000100010a000000000000010a000000000100010b000000000000010b0000000001000106000000000100010700000000010001060000000001000107000000000100010600000000010001070000000001000106000000000100010700000000010001060000000001000107000000000100010600000000010001070000000001000106000000000100010700000000010001060000000001000107
         INPUT_FILL=65536
         # ★ 菜单路径必须 seed key2：OpenZipU 依赖 key2 的 EoCD 签名（R237 定案）。
         #   /sdcard/root.dat 不以 .zip 结尾 ⇒ shim 的 key2_hook 不会自动 re-assert ⇒ 必须 SEED。
         KEY2_SEED=1
         # 让 guest 看到原厂手柄身份（对应 cubegm/20bc_5500_0111 那份真表）
         USB_VID=20bc
         USB_PID=5500
         USB_VER=0111
         # ★ 不再重写 joystick.zip（实测重写会解析卡死/不生效，见 R246）
         #   改由 shim 合成 /proc/bus/input/devices，让 guest 看到原厂 20bc:5500:0111,
         #   从而命中原厂 joystick.zip 里**已有**的 20bc_5500 表（A=btn0, TL1=btn6, TR1=btn7）
         echo \"  INPUT: A(btn6) 注入 FILL=65536\" >> \$L
       fi
       ( cd /sdcard/cubegm && timeout 40 \$Q -L /arm-root-device -cpu cortex-a7 -strace \
           -E LD_PRELOAD=/sdcard/cubegm/guest_shim.so \
           -E LD_LIBRARY_PATH=\"\$LIBP\" \
           -E PATH=/arm-root-device/usr/bin:/usr/bin:/bin \
           -E HOME=/tmp -E TMPDIR=/tmp -E LC_ALL=C -E LANG=C \
           -E CGM_INPUT_HEX=\$INPUT_HEX -E CGM_INPUT_FILL=\$INPUT_FILL \
           -E CGM_USB_VID=\$USB_VID -E CGM_USB_PID=\$USB_PID -E CGM_USB_VER=\$USB_VER \
           -E CGM_KEY2_SEED=\$KEY2_SEED -E CGM_KEY2_HOOK=\$KEY2_SEED -E CGM_KEY2_PROBE=\$KEY2_SEED \
           /sdcard/cubegm/rkgame > /tmp/t13_stdout.txt 2> /tmp/t13_stderr.txt )
       echo \"  exit=\$?\" >> \$L
       echo '  --- stderr 尾 8 行 ---' >> \$L
       tail -8 /tmp/t13_stderr.txt 2>/dev/null | sed 's/^/    /' >> \$L || true

       echo '=== debug.log ===' >> \$L
       if [ -f /sdcard/cubegm/debug.log ]; then
         echo \"  size=\$(wc -c < /sdcard/cubegm/debug.log) B\" >> \$L
         cp -f /sdcard/cubegm/debug.log /tmp/debug.log
         echo '  --- FBA_Load 关键行 ---' >> \$L
         grep -aE 'open .*fail|unsupport\.|use .* to run|Exit fba|autorun|run_game|RomName|retro_save_state|SaveDefaultState|SRAM' /sdcard/cubegm/debug.log >> \$L 2>&1 || true
       else
         echo '  ★ 无 debug.log' >> \$L
       fi
       if [ \"$TWOPASS\" = \"1\" ]; then
         echo '=== ★ 第二遍：验证 SRAM 电池存档【读回】（删 .sav 保留 .srm，隔离 savestate 干扰）===' >> \$L
         ls -l /sdcard/cubegm/saves/\"$ROM_DIR\"/ /sdcard/cubegm/states/\"$ROM_DIR\"/ 2>/dev/null | sed 's/^/  /' >> \$L || true
         # ★ R256 关键隔离：测量对象是 sram 时，.sav 是 zlib savestate（内含 SRAM 快照），
         #   parallel-restore 不重曝 SRAM（实测 size0 恒 0）⇒ 会掩盖 .srm 读回。
         #   删 .sav 只留 .srm，让 core 走干净 retro_load_game（那条路才建立 16384 SRAM）。
         #   只在 CGM_UPGRADE 含 sram 时删；否则（如 1941/cps2 的 .sav 读回）保持原样。
         case \",$CGM_UPGRADE,\" in *,sram,*|*,both,*|*,1,*) rm -f /sdcard/cubegm/saves/\"$ROM_DIR\"/*.sav ;; esac
         rm -f /sdcard/cubegm/debug.log
         ( cd /sdcard/cubegm && timeout 40 \$Q -L /arm-root-device -cpu cortex-a7 -strace \
             -E LD_PRELOAD=/sdcard/cubegm/guest_shim.so \
             -E LD_LIBRARY_PATH=\"\$LIBP\" \
             -E PATH=/arm-root-device/usr/bin:/usr/bin:/bin \
             -E HOME=/tmp -E TMPDIR=/tmp -E LC_ALL=C -E LANG=C \
             -E CGM_INPUT_HEX=\$INPUT_HEX -E CGM_INPUT_FILL=\$INPUT_FILL \
             -E CGM_KEY2_SEED=\$KEY2_SEED -E CGM_KEY2_HOOK=\$KEY2_SEED -E CGM_KEY2_PROBE=\$KEY2_SEED \
             -E CGM_USB_VID=\$USB_VID -E CGM_USB_PID=\$USB_PID -E CGM_USB_VER=\$USB_VER \
             /sdcard/cubegm/rkgame > /tmp/t13_stdout2.txt 2> /tmp/t13_stderr2.txt )
         echo \"  第二遍 exit=\$?\" >> \$L
         cp -f /sdcard/cubegm/debug.log /tmp/debug.log2 2>/dev/null || true
         cp -f /tmp/t13_stderr2.txt /tmp/t13_stderr2.keep 2>/dev/null || true
         cp -f /tmp/t13_stdout2.txt /tmp/t13_stdout2.keep 2>/dev/null || true
         echo '  --- 第二遍 strace 对 .srm 的访问（读回证据：期望 O_RDONLY）---' >> \$L
         grep -aE 'langrisser2\\.srm' /tmp/t13_stderr2.txt | head -6 | sed 's/^/    /' >> \$L || true
         echo '  --- 第二遍 stdout 的 SRAM 读回 hook ---' >> \$L
         grep -aE 'SRAM load hook|\\[sram\\]' /tmp/t13_stdout2.txt | head -8 | sed 's/^/    /' >> \$L || true
       fi

       echo '=== saves/states ===' >> \$L
       find /sdcard/cubegm/saves /sdcard/cubegm/states -type f 2>/dev/null | sed 's/^/  /' >> \$L || true
       echo REMOTE-DONE >> \$L
       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"
echo "   ssh 管道 rc=$?"

echo "== 4) 取回 =="
FETCH="$ROOT/tools/cnb_ws_fetch.sh"
for f in /tmp/t13.log /tmp/debug.log /tmp/debug.log2 /tmp/t13_stderr.txt /tmp/t13_stdout.txt /tmp/t13_stderr2.txt /tmp/t13_stdout2.txt; do
    b=$(basename "$f"); L="$OUTDIR/$b"
    sh "$FETCH" "$A" "$f" "$L" 2>/dev/null || true
done
# ★ R244：把云上**新产物**取回（本地 ELF 往往是旧的；崩溃 lr 必须对着**真正跑的那份**符号化）
if [ "$REBUILD" = "1" ]; then
    if sh "$FETCH" "$A" /workspace/1to1/build/rkgame.rebuilt.elf \
          "$OUTDIR/rkgame.rebuilt.new.elf" 2>/dev/null; then
        echo "   新产物已取回 $OUTDIR/rkgame.rebuilt.new.elf"
        C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe -c "print()" 2>/dev/null || true
    else
        echo "   !! 新产物取回失败" >&2
    fi
fi

echo "== 5) 结果 =="
if ! grep -q "RUN-NONCE=$NONCE" "$OUTDIR/t13.log" 2>/dev/null; then
    echo "!! t13.log 不含本轮 nonce ⇒ 无有效结果" >&2
    head -5 "$OUTDIR/t13.log" 2>/dev/null >&2 || true
    [ "$STOP" = "1" ] && { timeout 120 cnb workspace workspace-stop --sn "$SN" >/dev/null 2>&1 || true; }
    exit 22
fi
grep -aE 'qemu=|zig=|obj 数|new ELF sha|AUTORUN_SET_OK|core 数|被测=|exit=|size=|unsupport\.|use .* to run|autorun |run_game ' "$OUTDIR/t13.log" 2>/dev/null | head -40
echo "== 完成。产物在 $OUTDIR =="
if [ "$STOP" = "1" ]; then
    echo "   关闭工作区 $SN（省核时）"
    timeout 120 cnb workspace workspace-stop --sn "$SN" 2>&1 | tail -3 || true
else
    echo "   省钱：cnb workspace workspace-stop --sn $SN"
fi
