#!/bin/sh
# =============================================================================
# _r305_cnb_verify.sh —— 本机驱动：起/复用 CNB 云开发 → 上传 → 远端跑 → 取回 → stop
#
# 模式照 tools/cnb_devqemu.sh（SN 三规则解析 / SSH ServerAlive / tar 管道上传）。
# 判据：远端 report/qemu/behav_diff.txt 判据行 vs 本地三份基线（去时间戳 diff）。
# =============================================================================
set -u
# ★ 归档进 tools/ 后，仓库根 = 本脚本目录的上一级
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 9
REPO="${REPO:-lieguch/cubeGM}"
OUTDIR="$ROOT/report/_r305_cnb"
mkdir -p "$OUTDIR"
ELF="$ROOT/_sdcard_drop/latest_rebuilt/rkgame.rebuilt.elf"
SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=25 -o ServerAliveInterval=30 -o ServerAliveCountMax=20"

echo "== 0) 前置"
[ -s "$ELF" ] || { echo "缺 $ELF"; exit 11; }
cp -f "$ELF" build/_r305_elf
echo "   ELF=$(sha256sum build/_r305_elf | cut -c1-16) $(wc -c <build/_r305_elf) B"

echo "== 1) 起/复用 workspace"
SN="${WS_SN:-}"
A="${WS_SSH:-}"
if [ -z "$SN" ] && [ -z "$A" ]; then
  OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
  printf '%s\n' "$OUT" | sed -n '1,6p'
  SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
  [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
fi
echo "   sn=${SN:-?}"
[ -n "$SN" ] && echo "$SN" > "$OUTDIR/.sn"
[ -n "$A" ] && echo "$A" > "$OUTDIR/.ssh"

echo "== 2) 等 SSH 就绪"
if [ -z "$A" ]; then
  i=0
  while [ -z "$A" ] && [ "$i" -lt 20 ]; do
    D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
    A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
    i=$((i + 1)); [ -n "$A" ] || sleep 12
  done
fi
[ -n "$A" ] || { echo "!! 未取到 ssh 地址（可用 WS_SSH=<user@host> 指定）" >&2; exit 13; }
echo "   ssh=$A"
echo "$A" > "$OUTDIR/.ssh"

echo "== 3) 上传 → 远端跑 → 取回（单连接）"
tar czf - tools build/_r305_elf build_r305_remote.sh golden/device_rootfs_min 2>/dev/null \
 | timeout 3500 ssh $SSH_OPTS "$A" \
   "set -u
    for d in /workspace/1to1 /workspace; do [ -d \"\$d/tools\" ] && P=\$d && break; done
    [ -n \"\${P:-}\" ] || { echo 'PROJ 未找到' >&2; exit 9; }
    cd \"\$P\" || exit 9
    mkdir -p build
    tar xzf - --no-same-owner
    sh build_r305_remote.sh > /tmp/r305_remote_out.log 2>&1; rc=\$?
    echo \"REMOTE_RC=\$rc\"
    tail -60 /tmp/r305_remote_out.log
    if [ -f /tmp/r305_report.tgz ]; then echo __B64_START__; base64 /tmp/r305_report.tgz; echo __B64_END__; fi" \
 > "$OUTDIR/remote_run.log" 2>&1
RC_LINE=$(grep -m1 'REMOTE_RC=' "$OUTDIR/remote_run.log" || echo "REMOTE_RC=?")
echo "   $RC_LINE"
echo "   remote log: $OUTDIR/remote_run.log ($(wc -c <"$OUTDIR/remote_run.log") B)"

echo "== 4) 解出判据包"
python - "$OUTDIR/remote_run.log" <<'PY'
import base64, os, re, sys, tarfile
src = sys.argv[1]
raw = open(src, 'rb').read().decode('utf-8', 'replace')
m = re.search(r'__B64_START__\s*\n(.*?)\n__B64_END__', raw, re.S)
if not m:
    print('!! 未找到 __B64_START__/__B64_END__ 标记 ⇒ 取回失败'); sys.exit(2)
blob = re.sub(r'[^A-Za-z0-9+/=]', '', m.group(1))
data = base64.b64decode(blob + '=' * (-len(blob) % 4))
d = os.path.dirname(src)
out = os.path.join(d, 'r305_report.tgz')
open(out, 'wb').write(data)
print('pkg %d B -> %s' % (len(data), out))
tf = tarfile.open(out)
for n in tf.getnames():
    m2 = tf.extractfile(n)
    if m2 is None: continue
    rel = n.split('report/qemu/')[-1]
    p = os.path.join(d, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'wb').write(m2.read())
print('解出:', sorted(os.listdir(d)))
PY


echo "== 5) 判据文件就位情况"
ls -la "$OUTDIR" | head -12
