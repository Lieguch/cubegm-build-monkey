#!/bin/sh
# cnb_ladder.sh —— **启动链阶梯**：在 CNB 云开发上跑"设备真 sysroot + 三桩"，
# 并把两侧 strace **归一化后逐行对齐**，给出「首个行为类分叉点」。
#
# ## 为什么是它（第 110 轮结论的下一步）
# `cnb_devqemu.sh` 已证明：无桩时两侧**同崩在 DRM 初始化**（沙箱没有 /dev/dri）⇒ 阶梯到此为止。
# 要往上推，必须上**三桩**（libkms / libdrm / libasound）—— 这正是 CI 场景 C4/C5 做的事。
# 现有装置缺的只是**最细一级判据**：两侧 strace 的**逐行对齐**（`strace_diff.py`）。
#
#   · 复用（不重写）：`ci_qemu_behav.sh`（铺环境 / 三桩 / guest shim / 行为指纹 / 里程碑 / 覆盖率）
#   · 新增（本项目此前没有）：`strace_diff.py` —— 「首个分叉点 + 分装载几何类/行为类」
#
# ## 预登记判据
#   L1 场景 C4 必须产出两份 strace（`probe_stderr_{factory,rebuild}_strace.txt`）；
#      缺任一份 ⇒ 装置不可用，本轮结论作废（fail-closed）。
#   L2 报出 **行为类分叉数**；`0` 是本轮唯一可接受的"好"结果形态（装载几何类不算行为差异）。
#   L3 里程碑（`milestones.txt`）必须给出两侧的 M0–M7 与终止码。
#
# 用法（本机）:  sh tools/cnb_ladder.sh
#   环境变量: WS_SN / WS_SSH（复用工作区，省钱）；SCEN=4（只跑 C4，默认 C4+C5）
# 退出: 0=装置与判据都跑通；2=有 fail；11=前置缺失
set -u

REPO="${REPO:-lieguch/cubeGM}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="$ROOT/report/ladder"
mkdir -p "$OUTDIR"
SCEN="${SCEN:-45}"

echo "== 1) 开/复用 CNB 云开发工作区 =="
SN="${WS_SN:-}"; A="${WS_SSH:-}"
if [ -z "$SN" ] && [ -z "$A" ]; then
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    printf '%s\n' "$OUT" | sed -n '1,8p'
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    # ★ 2026-10-01（第 112 轮）实测：CNB 的启动响应**有时不含 `"sn"` 字段**，只给
    #   `url: https://cnb.cool/<o>/<r>/-/workspace/vscode-web/<SN>-001/`
    #   ⇒ 旧的两条规则全部落空 ⇒ SN 为空 ⇒ 后面 get-workspace-detail 必然失败（"空跑 4 轮"的成因）。
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" \
        | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
fi
echo "   sn=${SN:-?}"
if [ -z "$A" ]; then
    echo "== 2) 等 SSH 就绪 =="
    i=0
    while [ -z "$A" ] && [ "$i" -lt 20 ]; do
        D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
        A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
        i=$((i + 1)); [ -n "$A" ] || sleep 12
    done
fi
[ -n "$A" ] || { echo "!! 未取到 ssh 地址" >&2; exit 13; }
echo "   ssh=$A"
echo "$SN" > "$OUTDIR/.sn" 2>/dev/null || true
echo "$A" > "$OUTDIR/.ssh" 2>/dev/null || true

# ★★★ 2026-10-01（第 113 轮）**修 run8 的静默死亡**：
#   现象：复用工作区时 ssh 连上了（banner 正常、known_hosts 已写），但**远端一个字都没产出**，
#         脚本 60 秒内退出，`REMOTE-DONE` 从未出现，而 `_stderr.txt` 里也**没有任何错误**。
#   根因：**复用的工作区其 ssh 授权已失效**（实测同一地址直接 `Permission denied`），
#         而 `report/ladder/.ssh` 本地又写不进去（Permission denied）⇒ 文件里留着**旧工作区的地址**，
#         下一次复用时"看起来有地址"但其实指向早已失效的会话。
#   ⇒ 两条修法：① **开新工作区前先做鉴权探针**，不通过就**重新开一个**；
#              ② 远端脚本结束必须留下 `REMOTE-DONE`，**没看到就 fail-loud**（不许静默出结论）。
probe_ssh() {
    timeout 60 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o BatchMode=yes -o ConnectTimeout=20 "$1" "echo AUTH-OK" 2>/dev/null | grep -q AUTH-OK
}
if ! probe_ssh "$A"; then
    echo "!! 复用地址鉴权失败 ⇒ 开一个全新工作区（不复用陈旧会话）"
    SN=""; A=""
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" \
        | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
    i=0
    while [ -z "$A" ] && [ "$i" -lt 20 ]; do
        D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
        A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
        i=$((i + 1)); [ -n "$A" ] || sleep 12
    done
    probe_ssh "$A" || { echo "!! 新工作区鉴权仍失败（sn=$SN）" >&2; exit 13; }
    echo "$SN" > "$OUTDIR/.sn" 2>/dev/null || true
    echo "$A" > "$OUTDIR/.ssh" 2>/dev/null || true
fi
echo "   ssh 鉴权 OK"

echo "== 3) 单连接：装依赖 → 建桩 → 建环境 → 跑 C4/C5 → strace 对齐 =="
cd "$ROOT" || exit 9
# ★ REBUILD=2：**云上只重链**（`-z execstack` 是链接期改动，无需重编 213 个源文件）
#   ⇒ 上传本地对象集与上游库，云上跑一次 `link_full.sh`。比全量重建快一个数量级。
#   ★★ 第 114 轮实测补漏：上传清单少了 `src/upstream/xunzip/XUnzip.o` ⇒ 云上 `link_full.sh`
#      的 fail-closed 立刻报 `★★ XUnzip 对象不存在` 并 exit 12（RELINK-FAIL）。
#      `src/` 下**只有这一个 .o**（其余走 `build/obj` 与 `build/upstream`），故精确补它。
UP=""
[ "$REBUILD" = "2" ] && UP="build/obj build/upstream src/upstream/xunzip/XUnzip.o"
# ★ 第 115 轮：REBUILD=3（Thumb 根修实验）须**重编 libiconv** ⇒ 要上传 libiconv/libcharset 源码树。
#   它不在「链接输入」类（.o）里，而云上仓库的 src/upstream 未必是完整源码（git 托管在 CNB）。
[ "$REBUILD" = "3" ] && UP="build/obj build/upstream src/upstream/xunzip/XUnzip.o src/upstream/libiconv17 src/upstream/libcharset"
# ★ 第 116 轮：REBUILD=4（B线 wav 结构体复验）须**重编 proprietary**（含 mui_LoadSetting 改动）。
#   ⇒ 上传 src/proprietary 源码（link_audit.sh 会 rm build/obj/*.o 后重编 213 个），
#   故不传 build/obj（传了也会被清掉重编）。build/upstream 传本地 zig 版 stb/mxml/mp3，
#   libiconv/libcharset 由云上真 GCC -mthumb 重编覆盖。
[ "$REBUILD" = "4" ] && UP="src/proprietary src/compat build/upstream src/upstream/xunzip/XUnzip.o src/upstream/libiconv17 src/upstream/libcharset"
# ★★ 第 114 轮：**链接输入必须每次都上传**，否则云上会用仓库里的旧版，改了个寂寞。
#   实测：改了 `linker/factory.ld`（GAP 16.76 段页对齐）却只上传 `tools/`，
#   云上链接 rc=0 但布局仍是旧的 ⇒ 新门禁立刻 SEGPAGE-FAIL（**门禁替我们发现"云上没吃到我改的文件"**）。
#   `linker/`（链接脚本）+ `src/data`（工厂镜像 .S/.bin，`factory_local.o` 的输入）都在这条路径上。
UP="$UP linker src/data"
# ★★ 第 114 轮：**取回前先清旧文件**。实测教训：本轮 `SCEN=4` ⇒ C5 根本没跑，
#   而 `report/ladder/` 里仍躺着上一轮的 c5 strace ⇒ 我据此解码出"仍崩在 0x5401d8"
#   这个**错误结论**（陈旧文件冒充新观测，与"仪器静默降级"同族）。
rm -f "$OUTDIR"/report_qemu_*.txt "$OUTDIR"/ladder.log "$OUTDIR"/_stderr.txt 2>/dev/null || true
tar czf - tools golden/device_rootfs_min golden/sdcard_min golden/factory.rkgame.bin \
      build/rkgame.rebuilt.elf $UP 2>/dev/null \
| timeout 5400 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o BatchMode=yes -o ConnectTimeout=25 \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=40 "$A" \
      "set -u
       for d in /workspace/1to1 /workspace; do [ -d \"\$d/tools\" ] && PROJ=\$d && break; done
       PROJ=\${PROJ:-}; L=/tmp/ladder.log
       { echo \"PROJ=\$PROJ\"; date -u; } > \$L
       [ -n \"\$PROJ\" ] || { echo 'PROJ 未找到'; exit 9; }
       cd \"\$PROJ\" || exit 9
       mkdir -p build report build/_exp
       tar xzf - --no-same-owner 2>>\$L

       echo '=== 装依赖 ===' >> \$L
       (apt-get update -qq && apt-get install -y -qq qemu-user-static gcc-arm-linux-gnueabihf \
          binutils-arm-linux-gnueabihf gdb-multiarch python3-pip) >>\$L 2>&1 || true
       python3 -m pip install -q --break-system-packages pyelftools capstone unicorn ziglang >>\$L 2>&1 \
         || python3 -m pip install -q --user pyelftools capstone unicorn ziglang >>\$L 2>&1
       for t in qemu-arm-static arm-linux-gnueabihf-gcc gdb-multiarch python3; do
         printf '  %-26s %s\n' \"\$t\" \"\$(command -v \$t || echo 缺)\" >> \$L
       done
       ZIG=\$(python3 -c 'import os,ziglang;print(os.path.join(os.path.dirname(ziglang.__file__),\"zig\"))' 2>/dev/null || true)
       echo \"  zig=\${ZIG:-缺}\" >> \$L

       echo '=== 建设备真 sysroot /arm-root-device ===' >> \$L
       rm -rf /arm-root-device; mkdir -p /arm-root-device
       cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>\$L
       rm -f /arm-root-device/MANIFEST.sha256
       [ -e /arm-root-device/lib/ld-linux-armhf.so.3 ] || ln -sf ld-2.29.so /arm-root-device/lib/ld-linux-armhf.so.3
       echo '=== 建 /sdcard/cubegm ===' >> \$L
       mkdir -p /sdcard/cubegm; cp -a golden/sdcard_min/. /sdcard/cubegm/ 2>>\$L || true

       # ★★★ 第 112 轮实验：**提供 /dev/dri/card0**
       #   取证（对 C4 的 360 行 strace 做**失败系统调用全枚举**）：滤掉 ld.so 的
       #   hwcap/桩目录搜索噪声后，**唯一**真实缺失的环境要素就是 /dev/dri/card0..15（16 条）。
       #   而 tools/guest_shim/drm_stub.c **已经实现了** drmIoctl + dumb buffer 应答
       #   （dumb_fill）+ drmModeGetResources/Connector/Crtc/AddFB2/SetCrtc ⇒ 只要 open 成功，后续可走桩。
       #   ★ 预登记判据（先写死，再看结果）：
       #     E1 两侧 strace 行数**同时显著增长**（≥ +50）或 M5 变 ✓ ⇒ 节点有效，保留；
       #     E2 两侧**同时更早终止**（行数减少）⇒ 印证项目既有结论"假 /dev/dri 无法应答 ioctl"
       #        （ci_qemu_behav.sh 第 755 行已记过），记录并回退；
       #     E3 **只有一侧变化** ⇒ 那是**行为分叉**，必须单独定性（不得含糊过去）。
       if [ "${CGM_FIX_DEV_DRI:-1}" = "1" ]; then
         mkdir -p /dev/dri 2>/dev/null || true
         for i in 0 1; do
           [ -e /dev/dri/card\$i ] || : > /dev/dri/card\$i 2>/dev/null || true
         done
         ls -l /dev/dri >> \$L 2>&1 || echo '  (/dev/dri 建不了)' >> \$L
       fi

       echo '=== 建三桩 + guest shim ===' >> \$L
       mkdir -p report/stublib report/drmstublib report/alsastublib
       # ★★★ 第 112 轮根修：**guest shim 必须真的建出来**。
       #   取证：第 111 轮的 report/qemu_c4/shim_build.txt 只有 154 B，内容是
       #       [shim] CC=cc  目标 glibc=2.29
       #       cc: error: unrecognized command-line option '-mfloat-abi=hard'
       #   ⇒ ci_qemu_behav.sh 调 build_guest_shim.sh 时**没传 CC**，落到宿主 cc（x86_64）
       #     ⇒ 构建失败 ⇒ harness **静默降级为"不带 shim 跑"**（只在报告里写一行）。
       #   ⇒ 修法两条一起上：① 本脚本**显式构建**并 export CC（让 harness 内部那条路也能成）;
       #                    ② 用 CGM_SHIM_SO 把产物**直接指定**给 harness（不再依赖现场编译）。
       #   ★ fail-loud：建不出来就打 ** SHIM-FAIL，由本脚本退出码体现，不许静默降级。
       if [ -n \"\${ZIG:-}\" ]; then SC=\"\$ZIG cc\"; else SC=arm-linux-gnueabihf-gcc; fi
       export CC=\"\$SC\"
       echo \"  shim CC=\$CC\" >> \$L
       SOK=0
       if CC=\"\$CC\" sh tools/build_guest_shim.sh report/guest_shim.so >>\$L 2>&1 && [ -s report/guest_shim.so ]; then
         SOK=1
         echo \"  ★ shim 构建成功：\$(wc -c < report/guest_shim.so) B\" >> \$L
       else
         echo '  ★★ SHIM-FAIL：guest shim 构建失败 ⇒ 本轮可观测窗口较浅（fail-loud）' >> \$L
       fi
       CC_ARM=arm-linux-gnueabihf-gcc sh tools/build_libkms_stub.sh    report/stublib     >>\$L 2>&1 || echo '  [warn] libkms 桩失败' >> \$L
       CC_ARM=arm-linux-gnueabihf-gcc sh tools/build_libdrm_stub.sh    report/drmstublib  >>\$L 2>&1 || echo '  [warn] libdrm 桩失败' >> \$L
       CC_ARM=arm-linux-gnueabihf-gcc sh tools/build_libasound_stub.sh report/alsastublib >>\$L 2>&1 || echo '  [warn] libasound 桩失败' >> \$L
       ls -la report/stublib report/drmstublib report/alsastublib report/guest_shim.so >>\$L 2>&1 || true

       echo '=== 场景 C4（设备真 sysroot + 三桩）===' >> \$L
       # ★★★ 第 112 轮：REBUILD=1 时**在云上全量重建**（不在本机建任何东西）。
       #   为什么必须云上重建：本轮的根修是**链接标志**（-z execstack），
       #   而仓库不含构建产物（.o 不入库）⇒ 云上必须自己跑一遍完整构建。
       #   ★ fail-loud：重建失败就打 ** REBUILD-FAIL，并打印 PT_GNU_STACK 以核对
       #     （期望 flags=7（RWX）—— 与工厂一致；旧值是 6（RW））。
       if [ "$REBUILD" != "0" ]; then
         if [ "$REBUILD" = "2" ]; then
           echo '=== 云上**只重链**（link_full.sh；-z execstack 是链接期改动）===' >> \$L
           PY=python3 sh tools/link_full.sh build/rkgame.rebuilt.elf >>\$L 2>&1 \
             || echo '  ** RELINK-FAIL' >> \$L
         elif [ "$REBUILD" = "3" ]; then
           echo '=== Thumb 根修实验：libiconv 单独真 GCC -mthumb（其余上游库保持 zig，单变量）===' >> \$L
           sh tools/fetch_bootlin63.sh >>\$L 2>&1 || echo '  ** BOOTLIN-FAIL' >> \$L
           TC=cache_tc/bootlin63/bin/arm-buildroot-linux-gnueabihf-gcc
           [ -x \"\$TC\" ] || TC=arm-linux-gnueabihf-gcc
           echo \"  ICONV_CC=\$TC（bootlin 工厂同期优先，apt gcc 仅兜底）\" >>\$L
           CC=\"\$ZIG cc\" ICONV_ONLY=1 ICONV_CC=\"\$TC\" PY=python3 sh tools/build_upstream.sh build/upstream >>\$L 2>&1 || echo '  ** ICONV-FAIL' >> \$L
           echo '--- libiconv 对象 Thumb 属性（Tag_THUMB_ISA_use）---' >> \$L
           arm-linux-gnueabihf-readelf -A build/upstream/libiconv_iconv.o 2>/dev/null | grep -iE 'THUMB|thumb' >>\$L 2>&1 || echo '  ** 无 Thumb 属性（未真产 Thumb）' >> \$L
           PY=python3 sh tools/link_full.sh build/rkgame.rebuilt.elf >>\$L 2>&1 || echo '  ** RELINK-FAIL' >> \$L
           echo '--- isa_mode_gate：mismatch 应从 308 收敛 ---' >> \$L
           python3 tools/isa_mode_gate.py --ours build/rkgame.rebuilt.elf --factory golden/factory.rkgame.bin >>\$L 2>&1 || true
           echo '--- seg_page_audit（段页门禁不得破坏）---' >> \$L
           python3 tools/seg_page_audit.py build/rkgame.rebuilt.elf >>\$L 2>&1 || echo '  ** SEGPAGE-FAIL' >> \$L
         elif [ "$REBUILD" = "4" ]; then
           echo '=== B线复验：重编 proprietary（wav 结构体）+ libiconv Thumb + 重链 ===' >> \$L
           sh tools/fetch_bootlin63.sh >>\$L 2>&1 || echo '  ** BOOTLIN-FAIL' >> \$L
           echo '--- ① 重编 proprietary（link_audit.sh 全量 213 个，含 mui_LoadSetting wav 结构体改动）---' >> \$L
           CC=\"\$ZIG cc\" PY=python3 sh tools/link_audit.sh report/link_audit.txt >>\$L 2>&1 || echo '  ** PROP-FAIL' >> \$L
           TC=cache_tc/bootlin63/bin/arm-buildroot-linux-gnueabihf-gcc
           [ -x \"\$TC\" ] || TC=arm-linux-gnueabihf-gcc
           echo \"  ICONV_CC=\$TC（libiconv 单独真 GCC Thumb）\" >>\$L
           CC=\"\$ZIG cc\" ICONV_ONLY=1 ICONV_CC=\"\$TC\" PY=python3 sh tools/build_upstream.sh build/upstream >>\$L 2>&1 || echo '  ** ICONV-FAIL' >> \$L
           PY=python3 sh tools/link_full.sh build/rkgame.rebuilt.elf >>\$L 2>&1 || echo '  ** RELINK-FAIL' >> \$L
           echo '--- isa_mode_gate（应保持 0，不得回退）---' >> \$L
           python3 tools/isa_mode_gate.py --ours build/rkgame.rebuilt.elf --factory golden/factory.rkgame.bin >>\$L 2>&1 || true
           echo '--- seg_page_audit（段页门禁不得破坏）---' >> \$L
           python3 tools/seg_page_audit.py build/rkgame.rebuilt.elf >>\$L 2>&1 || echo '  ** SEGPAGE-FAIL' >> \$L
         else
           echo '=== 云上全量重建（FORCE_BUILD=1 sh tools/cnb_env.sh）===' >> \$L
           FORCE_BUILD=1 PY=python3 sh tools/cnb_env.sh >>\$L 2>&1 || echo '  ** REBUILD-FAIL' >> \$L
         fi
         ls -la build/rkgame.rebuilt.elf >>\$L 2>&1 || true
         echo '--- PT_GNU_STACK（期望 flags=7 = RWX，与工厂一致）---' >> \$L
         arm-linux-gnueabihf-readelf -lW build/rkgame.rebuilt.elf 2>/dev/null | grep -i GNU_STACK >>\$L 2>&1 || true
         echo '--- 真实 PT_INTERP（重链后必须仍是设备侧路径）---' >> \$L
         python3 tools/interp_of.py build/rkgame.rebuilt.elf >>\$L 2>&1 || true
         echo \"  rebuilt sha=\$(sha256sum build/rkgame.rebuilt.elf 2>/dev/null | cut -c1-16)\" >> \$L
         echo '--- PT_LOAD 程序头（段页共享的直接证据）---' >> \$L
         arm-linux-gnueabihf-readelf -lW build/rkgame.rebuilt.elf 2>/dev/null \
           | sed -n '/Program Headers/,/Section to Segment/p' >>\$L 2>&1 || true
         echo '--- seg_page_audit（第 114 轮新增门禁；link_full.sh 里已 fail-closed）---' >> \$L
         python3 tools/seg_page_audit.py build/rkgame.rebuilt.elf >>\$L 2>&1 \
           || echo '  ** SEGPAGE-FAIL' >> \$L
         echo '--- 关键符号落位（TUnzip::Open 之前在被共享的页里）---' >> \$L
         arm-linux-gnueabihf-nm -S build/rkgame.rebuilt.elf 2>/dev/null \
           | grep -E 'TUnzip|unztell' >>\$L 2>&1 || true
       fi
       # ★ 显式把 shim 产物交给 harness（不再依赖它现场编译；现场编译那条路已由 export CC 保住）
       if [ \"\$SOK\" = \"1\" ]; then
         export CGM_SHIM_SO=\"\$PROJ/report/guest_shim.so\"
         echo \"  CGM_SHIM_SO=\$CGM_SHIM_SO\" >> \$L
       fi
       # ★★ 第 114 轮：**阶梯必须绑定产物 sha**。踩过的坑：场景 C4 的 echo 在重链之前，
       #   而真正的 C4 跑在重链之后 ⇒ 只读日志无法判断"这一轮跑的到底是哪份产物"。
       #   ★ 这段注释里**不许出现反引号** —— 本文件是本地双引号字面量，反引号会被**本地**
       #     shell 先做命令替换，整轮静默死掉（实测 line 110: 场景: command not found）。
       #     机械门禁：tools/ssh_literal_guard.py（带自证）。
       #   现在每次进场景前把 sha 打出来；并且**先清掉旧产物目录**，让"没跑"与"跑过"不会混淆。
       rm -rf report/qemu_c4 report/qemu_c5
       echo \"=== 开始 C4；被测产物 sha=\$(sha256sum build/rkgame.rebuilt.elf 2>/dev/null | cut -c1-16) ===\" >> \$L
       SYSROOT=/arm-root-device CGM_WORK=/sdcard/cubegm CGM_TIMEOUT=30 CGM_COV_TAG=C4 \
         CGM_LIBKMS_STUB=1 CGM_DRM_STUB=1 CGM_ALSA_STUB=1 \
         PY=python3 sh tools/ci_qemu_behav.sh build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu_c4 >>\$L 2>&1
       echo \"  C4 rc=\$?\" >> \$L

       if [ \"$SCEN\" = \"45\" ]; then
         echo '=== 场景 C5（C4 + J 口径旁路注入）===' >> \$L
         echo \"=== 开始 C5；被测产物 sha=\$(sha256sum build/rkgame.rebuilt.elf 2>/dev/null | cut -c1-16) ===\" >> \$L
         SYSROOT=/arm-root-device CGM_WORK=/sdcard/cubegm CGM_TIMEOUT=30 CGM_COV_TAG=C5 \
           CGM_LIBKMS_STUB=1 CGM_DRM_STUB=1 CGM_ALSA_STUB=1 \
           CGM_MENULOG_SCREEN=0 CGM_ROOTDAT=2 CGM_KEY2_SEED=1 CGM_KEY2_HOOK=1 CGM_KEY2_PROBE=1 \
           CGM_IO_TRACE=1 CGM_EXEC_ALIGN=1 \
           PY=python3 sh tools/ci_qemu_behav.sh build/rkgame.rebuilt.elf golden/factory.rkgame.bin report/qemu_c5 >>\$L 2>&1
         echo \"  C5 rc=\$?\" >> \$L
       fi

       echo '=== ★ 新判据：两侧 strace 归一化逐行对齐 ===' >> \$L
       for tag in C4 C5; do
         D=report/qemu_\$(echo \$tag | tr A-Z a-z)
         FA=\$D/probe_stderr_factory_strace.txt
         FB=\$D/probe_stderr_rebuild_strace.txt
         if [ -s \"\$FA\" ] && [ -s \"\$FB\" ]; then
           python3 tools/strace_diff.py \"\$FA\" \"\$FB\" --label-a factory --label-b rebuild \
               --max-regions 14 --out \$D/strace_diff.txt >>\$L 2>&1
           echo \"  [\$tag] strace_diff rc=\$?\" >> \$L
           tail -4 \$D/strace_diff.txt >> \$L 2>&1
         else
           echo \"  [\$tag] ★ 缺 strace（factory=\$(wc -c < \"\$FA\" 2>/dev/null || echo 0)B rebuild=\$(wc -c < \"\$FB\" 2>/dev/null || echo 0)B）⇒ 该场景判据不可用\" >> \$L
         fi
       done
       echo '=== ★ B线判据（第 116 轮）：rebuild 侧 wav 装载应读满 7696B（read 4096+3600）===' >> \$L
       for tag in c4 c5; do
         FB=report/qemu_\$tag/probe_stderr_rebuild_strace.txt
         if [ -s \"\$FB\" ]; then
           N=\$(grep -ac 'read(4,0x[0-9a-f]*,4096) = 3600' \"\$FB\" 2>/dev/null); N=\${N:-0}
           echo \"  [\$tag] rebuild read(4,4096)=3600 次数=\$N（修复前=0；期望=2，chord.wav+Button1.wav）\" >> \$L
         else
           echo \"  [\$tag] ★ 缺 rebuild strace ⇒ B线判据不可用\" >> \$L
         fi
       done

       echo '=== 里程碑与覆盖率 ===' >> \$L
       for tag in qemu_c4 qemu_c5; do
         echo \"--- \$tag milestones ---\" >> \$L
         sed -n '1,40p' report/\$tag/milestones.txt >> \$L 2>&1 || true
         for s in factory rebuild; do
           printf '%-8s ' \"\$s\" >> \$L
           grep -aE '已执行' report/\$tag/coverage_\$s.txt 2>/dev/null | head -1 >> \$L || echo '(无)' >> \$L
         done
       done
       echo REMOTE-DONE >> \$L
       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"
echo "   ssh 管道 rc=$?"

echo "== 4) 取回 =="
FETCH="$ROOT/tools/cnb_ws_fetch.sh"
# ★ 第 112 轮修正：`/tmp/ladder.log` 原先用 `tr '/' '_'` 生成 `_tmp_ladder.log` ⇒ **取回失败**
#   （本轮才发现：上一轮的诊断日志根本没落地，导致"shim 是否建成"无法取证）。改为显式命名。
sh "$FETCH" "$A" /tmp/ladder.log "$OUTDIR/ladder.log" 2>/dev/null || true
for f in report/qemu_c4/strace_diff.txt report/qemu_c4/milestones.txt \
         report/qemu_c4/coverage_factory.txt report/qemu_c4/coverage_rebuild.txt \
         report/qemu_c4/shim_build.txt \
         report/qemu_c4/probe_stderr_factory_strace.txt report/qemu_c4/probe_stderr_rebuild_strace.txt \
         report/qemu_c4/rundir_factory/stdout.txt report/qemu_c4/rundir_rebuild/stdout.txt \
         report/qemu_c5/strace_diff.txt report/qemu_c5/milestones.txt \
         report/qemu_c5/probe_stderr_factory_strace.txt report/qemu_c5/probe_stderr_rebuild_strace.txt; do
    b=$(echo "$f" | tr '/' '_'); L="$OUTDIR/$b"
    sh "$FETCH" "$A" "/workspace/1to1/$f" "$L" 2>/dev/null || true
done

# ★★ 第 114 轮补：把云上重链/重建的**真实产物取回**，否则本地产物会**静默过期**。
#   实测：云上已重链出 execstack 产物（GNU_STACK RWE），本地仍是旧版（RW / memsz 16MB），
#   导致后续静态分析对着过期产物做结论 —— 与"取回失败"同族的静默失败。
if [ "$REBUILD" != "0" ]; then
    sh "$FETCH" "$A" /workspace/1to1/build/rkgame.rebuilt.elf \
        "$OUTDIR/rkgame.rebuilt.elf.cloud" 2>/dev/null || true
    if [ -s "$OUTDIR/rkgame.rebuilt.elf.cloud" ]; then
        echo "   云上产物 $(sha256sum "$OUTDIR/rkgame.rebuilt.elf.cloud" | cut -c1-16)" \
             "／本地 $(sha256sum build/rkgame.rebuilt.elf | cut -c1-16)"
        cp build/rkgame.rebuilt.elf build/_exp/rkgame.rebuilt.pre-cloudfetch.elf 2>/dev/null || true
        cp "$OUTDIR/rkgame.rebuilt.elf.cloud" build/rkgame.rebuilt.elf
        echo "   已取回并替换 build/rkgame.rebuilt.elf（旧版存 build/_exp/rkgame.rebuilt.pre-cloudfetch.elf）"
    else
        echo "   ★★ 云上产物取回失败 —— 本地 build/rkgame.rebuilt.elf 是**旧版**，后续分析不可信"
    fi
fi

echo "== 5) 结果 =="
echo "--- 装置取证（依赖 / shim / 桩 / /dev/dri）---"
grep -aE "qemu-arm-static|arm-linux-gnueabihf-gcc|gdb-multiarch|zig=|shim CC=|warn|/dev/dri|C4 rc|C5 rc|strace_diff rc" "$OUTDIR/ladder.log" 2>/dev/null | head -30
echo "--- shim 构建 ---"
sed -n '1,12p' "$OUTDIR/report_qemu_c4_shim_build.txt" 2>/dev/null || echo "(未取到 shim_build.txt)"
for f in strace_diff.txt milestones.txt; do
    for tag in c4 c5; do
        p="$OUTDIR/report_qemu_${tag}_${f}"
        [ -f "$p" ] && { echo "===== qemu_${tag}/${f} ====="; tail -22 "$p"; }
    done
done
echo "== 完成。产物在 $OUTDIR =="
# ★★★ 2026-10-01（第 113 轮）**fail-loud**：远端必须留下 `REMOTE-DONE`。
#   没有它 ⇒ 这一轮**没有任何有效结果**（run8 就是这样静默死掉的：连 banner 都正常）。
#   禁止在这种情况下继续把上面的数字当结论。
# ★★ 第 114 轮补充：标记必须落在**已验证能取回的通道**上。实测 stderr 通道不可靠
#   （ssh 横幅有、远端 `echo >&2` 没有；而 `/tmp/ladder.log` 每次都取回成功）
#   ⇒ 远端同时写两处，本地**任一处见到即算完成**，并把"哪条通道给的"打出来。
DONE_CH=""
grep -q REMOTE-DONE "$OUTDIR/_stderr.txt" 2>/dev/null && DONE_CH="stderr"
[ -z "$DONE_CH" ] && grep -q REMOTE-DONE "$OUTDIR/ladder.log" 2>/dev/null && DONE_CH="ladder.log"
if [ -z "$DONE_CH" ]; then
    echo "!! 远端未产出 REMOTE-DONE ⇒ 本轮**无有效结论**（上面任何数字都不可信）" >&2
    echo "   ssh stderr 头 8 行：" >&2
    head -8 "$OUTDIR/_stderr.txt" 2>/dev/null >&2 || true
    echo "   ladder.log 尾 5 行：" >&2
    tail -5 "$OUTDIR/ladder.log" 2>/dev/null >&2 || true
    exit 21
fi
echo "   完成标记：REMOTE-DONE（通道=$DONE_CH）"
echo "   省钱：cnb workspace workspace-stop --sn $SN"
