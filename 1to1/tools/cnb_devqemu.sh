#!/bin/sh
# cnb_devqemu.sh —— **设备真 sysroot 的 qemu 启动链检验**（在 CNB 云开发上跑，本机不需要任何环境）
#
# ## 为什么必须有它（第 110 轮审计的结论）
# 项目已有的三套云执行器都不覆盖这件事：
#   · cnb_ruler.sh    → 跑**函数级行为尺**（Unicorn，逐函数，不经过 ld.so）
#   · cnb_ws_gates.sh → 跑**依赖 arm objdump 的静态门禁**
#   · cnb_ca_exp.sh   → 编译器对齐实验
# 而**没有任何一处**回答这两个问题：
#   ① 产物在**设备的那套 glibc 2.29 + 真实依赖库**下，ld.so 到底能不能把它加载起来？
#   ② 加载起来之后，它**走到哪一步**才死？
# ★ 这两问正是「真机零日志」的两层。第 109 轮已证明：`PT_INTERP` 写成了 Windows 宿主路径，
#   于是**内核 execve 直接 ENOENT**——而这条**在 qemu 上同样会暴露**（qemu 用自己的
#   `<sysroot><interp>` 查文件）。本脚本就是把这条判据机械化的地方。
#
# 判据（预登记，先写死再看结果）
#   V1 工厂侧必须 RAN（能被 qemu 加载并进入程序）——它是整个装置的**阳性对照**；
#      若工厂都不 RAN，说明是**装置坏了**，本轮结论一律作废。
#   V2 我方产物必须**至少能被加载**（无 "Could not open '<interp>'" / "No such file"）。
#      不能加载 ⇒ **FAIL**（这正是第 109 轮的形态）。
#   V3 用 `-strace` 记录**走到了第几个系统调用**，作为"走了多远"的刻度；
#      ★ 不预设期望值（沙箱没有真硬件，死在 MMIO 是正常的），只要求**可比**。
#
# 用法（本机）:  sh tools/cnb_devqemu.sh
#   可选环境变量:  WS_SN / WS_SSH（复用已开的工作区，省钱）
#                  STEPS=1 只跑工厂+我方（默认还跑负对照）
# 退出: 0=装置与产物都通过 V1/V2；2=有 FAIL；11=前置缺失
set -u

REPO="${REPO:-lieguch/cubeGM}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="$ROOT/report/devqemu"
mkdir -p "$OUTDIR"

echo "== 1) 开/复用 CNB 云开发工作区 =="
SN="${WS_SN:-}"
A="${WS_SSH:-}"
if [ -z "$SN" ] && [ -z "$A" ]; then
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    printf '%s\n' "$OUT" | sed -n '1,8p'
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    # ★ 2026-10-01：CNB 启动响应有时**不含 `"sn"`**，只给 url（含 `<SN>-001/`）⇒ 补第三条规则
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
[ -n "$A" ] || { echo "!! 未取到 ssh 地址（可用 WS_SSH=<user@host> 指定）" >&2; exit 13; }
echo "   ssh=$A"
echo "$SN" > "$OUTDIR/.sn"; echo "$A" > "$OUTDIR/.ssh"

echo "== 3) 单连接：上传 → 装 qemu → 建设备 sysroot → 三点启动链 =="
cd "$ROOT" || exit 9
NEG="build/_exp/rkgame.rebuilt.pre-interpfix.elf"
if [ ! -f "$NEG" ]; then NEG=""; echo "   （无负对照文件，跳过第三点）"; fi
STEPS="${STEPS:-2}"

tar czf - tools golden/device_rootfs_min golden/sdcard_min golden/factory.rkgame.bin \
      build/rkgame.rebuilt.elf $NEG 2>/dev/null \
| timeout 3500 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o BatchMode=yes -o ConnectTimeout=25 \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=20 "$A" \
      "set -u
       for d in /workspace/1to1 /workspace; do [ -d \"\$d/tools\" ] && PROJ=\$d && break; done
       PROJ=\${PROJ:-}
       L=/tmp/devqemu.log
       { echo \"PROJ=\$PROJ\"; date -u; } > \$L
       [ -n \"\$PROJ\" ] || { echo 'PROJ 未找到'; exit 9; }
       cd \"\$PROJ\" || exit 9
       mkdir -p build report build/_exp
       tar xzf - --no-same-owner 2>>\$L

       echo '--- 装 qemu-user-static ---' >> \$L
       (sudo apt-get update -qq && sudo apt-get install -y -qq qemu-user-static) >>\$L 2>&1 \
         || (apt-get update -qq && apt-get install -y -qq qemu-user-static) >>\$L 2>&1
       Q=\$(command -v qemu-arm-static || command -v qemu-arm || true)
       echo \"qemu=\$Q\" >> \$L
       [ -n \"\$Q\" ] || { echo '★★ 装不上 qemu-user-static ⇒ 装置不可用（fail-closed）' ; exit 11; }

       echo '--- 建【设备真 sysroot】/arm-root-device ---' >> \$L
       rm -rf /arm-root-device; mkdir -p /arm-root-device
       cp -a golden/device_rootfs_min/. /arm-root-device/ 2>>\$L
       rm -f /arm-root-device/MANIFEST.sha256
       # 设备上 /lib/ld-linux-armhf.so.3 是指向 ld-2.29.so 的软链；Windows 检出会丢成普通文件
       if [ ! -e /arm-root-device/lib/ld-linux-armhf.so.3 ]; then
         ln -sf ld-2.29.so /arm-root-device/lib/ld-linux-armhf.so.3
       fi
       ls -l /arm-root-device/lib/ld-linux-armhf.so.3 >> \$L 2>&1

       echo '--- 建 /sdcard/cubegm（真机同款工作目录）---' >> \$L
       mkdir -p /sdcard/cubegm
       cp -a golden/sdcard_min/. /sdcard/cubegm/ 2>>\$L || true
       # ★ 让 /dev/mem 存在（真机有；沙箱没有 ⇒ 程序 open 失败 ⇒ NULL+4 崩，
       #   而**工厂也会同样崩** ⇒ 那是环境伪影，不是我们的缺陷）
       [ -e /dev/mem ] || { : > /dev/mem 2>/dev/null && chmod 666 /dev/mem 2>/dev/null; } || true
       ls -l /dev/mem >> \$L 2>&1 || echo '  (/dev/mem 建不了)' >> \$L

       echo '--- 真实 PT_INTERP（先把答案写死）---' >> \$L
       python3 - <<'PYEOF' >> \$L 2>&1
import struct
def ip(p):
    try: d=open(p,'rb').read()
    except Exception as e: return 'MISSING(%s)'%e
    if bytes(d[:4]) != bytes((0x7f, 0x45, 0x4c, 0x46)): return 'NOT-ELF'
    po=struct.unpack_from('<I',d,28)[0]; pe=struct.unpack_from('<H',d,42)[0]; pn=struct.unpack_from('<H',d,44)[0]
    for i in range(pn):
        o=po+i*pe
        t,off,va,pa,fsz=struct.unpack_from('<5I',d,o)
        if t==3:
            raw=d[off:off+fsz]; z=raw.find(0)
            return (raw[:z] if z>=0 else raw).decode('latin-1')
    return '(static: no PT_INTERP)'
for p in ('golden/factory.rkgame.bin','build/rkgame.rebuilt.elf','build/_exp/rkgame.rebuilt.pre-interpfix.elf'):
    print('  %-46s %r' % (p, ip(p)))
PYEOF

       chmod +x golden/factory.rkgame.bin build/rkgame.rebuilt.elf 2>/dev/null || true
       [ -f build/_exp/rkgame.rebuilt.pre-interpfix.elf ] && chmod +x build/_exp/rkgame.rebuilt.pre-interpfix.elf

       # ---- 三点启动链：每点都记 退出码 + 首行错误 + strace 末尾 ----
       # ★ 关键：**把被测二进制放到 /sdcard/cubegm/<name>**，并以**绝对路径**调用。
       #   原因：程序的 `get_executable_path()` 取的是**自身路径的目录**
       #   （实测工厂侧 trace 里出现 `open .../golden//driver.so`）⇒ 只有把二进制放进
       #   真机同款目录，`driver.so`/`font.ttf`/`cores/` 才会被找到，里程碑才可比。
       run_point() {
         label=\$1; bin=\$2
         echo \"########## \$label  \$bin ##########\" >> \$L
         if [ ! -f \"\$bin\" ]; then echo '  SKIP（文件不存在）' >> \$L; return; fi
         cp -f \"\$bin\" /sdcard/cubegm/rkgame 2>/dev/null || true
         chmod +x /sdcard/cubegm/rkgame 2>/dev/null || true
         ( cd /sdcard/cubegm && timeout 40 \$Q -L /arm-root-device -cpu cortex-a7 -strace \
             /sdcard/cubegm/rkgame > /tmp/o_\$label.txt 2> /tmp/e_\$label.txt )
         rc=\$?
         echo \"  exit=\$rc\" >> \$L
         echo '  --- stderr 头 6 行 ---' >> \$L
         head -6 /tmp/e_\$label.txt | sed 's/^/    /' >> \$L
         n=\$(wc -l < /tmp/e_\$label.txt)
         echo \"  stderr 行数=\$n\" >> \$L
         echo '  --- strace 末尾 8 行（走到哪一步）---' >> \$L
         tail -8 /tmp/e_\$label.txt | sed 's/^/    /' >> \$L
         echo '  --- 关键里程碑（真机可比刻度）---' >> \$L
         for kw in 'ld.so.cache' 'driver.so' 'libemu' 'font.ttf' 'ui_cn.zip' 'cores' \
                   '/dev/mem' '/dev/fb' '/dev/dri' 'ioctl' 'menu.log' 'setting.xml' 'rt_sigaction'; do
           c=\$(grep -ac \"\$kw\" /tmp/e_\$label.txt 2>/dev/null || echo 0)
           [ \"\$c\" -gt 0 ] && echo \"    hit\$c  \$kw\" >> \$L
         done
         echo '  --- 关键字形判定 ---' >> \$L
         # ★ 只有 **qemu 自己**报的错才算 LOAD-FAILED（`qemu-arm-static: ...`）；
         #   被追踪程序里失败的 openat 不算（那是程序行为，工厂也会有）。
         if grep -qE '^qemu-arm[a-z0-9-]*:' /tmp/e_\$label.txt; then
             echo '    ★ LOAD-FAILED：qemu 无法加载（解释器/依赖不可达）' >> \$L
             grep -m1 -E '^qemu-arm[a-z0-9-]*:' /tmp/e_\$label.txt | sed 's/^/      /' >> \$L
         elif [ \"\$n\" = \"0\" ]; then
             echo '    ★ 无任何输出（连 strace 都没有）⇒ 未进入程序' >> \$L
         elif [ \"\$rc\" = \"124\" ]; then echo '    RAN-AND-TIMEOUT（活着/忙等）' >> \$L
         else echo \"    RAN-AND-DIED rc=\$rc\" >> \$L; fi
       }
       run_point factory  golden/factory.rkgame.bin
       run_point ours     build/rkgame.rebuilt.elf
       if [ -f build/_exp/rkgame.rebuilt.pre-interpfix.elf ] && [ \"$STEPS\" != \"1\" ]; then
         run_point negctl build/_exp/rkgame.rebuilt.pre-interpfix.elf
       fi
       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"
echo "   ssh 管道 rc=$?"

echo "== 4) 取回 =="
FETCH="$ROOT/tools/cnb_ws_fetch.sh"
for f in /tmp/devqemu.log /tmp/e_factory.txt /tmp/e_ours.txt /tmp/e_negctl.txt; do
    b=$(basename "$f"); L="$OUTDIR/$b"
    if [ "$f" = "/tmp/devqemu.log" ]; then
        sh "$FETCH" "$A" "$f" "$L" || echo "   !! 取回失败 $f" >&2
    else
        sh "$FETCH" "$A" "$f" "$L" 2>/dev/null || true
    fi
done

echo "== 5) 结果 =="
cat "$OUTDIR/devqemu.log" 2>/dev/null | sed -n '1,200p'
echo "== 完成。产物在 $OUTDIR =="
echo "   省钱：cnb workspace workspace-stop --sn $SN"
