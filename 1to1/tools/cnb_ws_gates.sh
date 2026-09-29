#!/bin/sh
# =============================================================================
# cnb_ws_gates.sh —— 一条命令：在 CNB**云开发工作区**里跑本机跑不了的门禁。
#
# 为什么不用 CNB 的**构建**流水线（2026-09-28 实测，平台原文）：
#   `Pipeline prepare error: Root Group's events CPU core-hours are insufficient for
#    pre-freezing(Freezing time:5.00 min, equivalent to 0.67 core-hours).`
#   ⇒ 根组织 CPU 配额耗尽 ⇒ **所有** pipeline 都卡在 Prepare
#     （连长期存在的 `rkgame-rebuild` 也一样）。云开发工作区走的是另一条配额路径，可用。
#
# 为什么必须**单连接**（上一次失败的教训）：
#   云开发容器会周期性重启（实测 `up 3 min`）＋约 15 分钟自动关闭。
#   把"上传"和"执行"拆成两次 SSH ⇒ 重启清空 /tmp ⇒ 命令毫无输出。
#   本脚本把 tar 直接**管道**进 ssh 的 stdin，并在**同一个会话**里装依赖 + 跑门禁。
#
# 用法:
#   sh tools/cnb_ws_gates.sh                 # 全套
#   sh tools/cnb_ws_gates.sh scan_symbol_delta scan_cxx_abi
# =============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CNB_DIR="/c/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/cnb"
export PATH="$PATH:$CNB_DIR"
REPO="lieguch/cubeGM"
ART="${ART:-$ROOT/build/rkgame.rebuilt.elf}"
WANT="$*"

[ -f "$ART" ] || { echo "!! 缺产物 $ART" >&2; exit 11; }

echo "== 1) 开工作区 =="
A="${WS_SSH:-}"
SN="${WS_SN:-}"
if [ -z "$A" ]; then
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    # 两种返回形态都要认：新建时给 `sn:`；已有运行中工作区时只给 workspace URL。
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
    echo "   sn=${SN:-?}"
fi

echo "== 2) 等 SSH 就绪 =="
# ★ WS_SSH 已给定时**不要**清空它（我第一版在这里写了 `A=""`，把外部传入的地址覆盖掉了）。
i=0
while [ -z "$A" ] && [ "$i" -lt 20 ]; do
    D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
    A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
    i=$((i + 1)); [ -n "$A" ] || sleep 12
done
[ -n "$A" ] || { echo "!! 未取到 ssh 地址（可用 WS_SSH=<user@host> 直接指定）" >&2; exit 13; }
echo "   ssh=$A"

echo "== 3) 单连接：上传 + 装依赖 + 跑门禁 =="
cd "$ROOT" || exit 9
# ★★ 判据用**后置条件**（文件在 + sha256 相等），不要用 tar 的退出码：
#   实测 `tar xzf -` 经 ssh 管道传输后会返回 rc=2（流末尾告警），但文件其实**已完整解出**。
#   旧写法 `tar xzf - || exit 8` 把这种"成功但 rc≠0"当失败 ⇒ 整条命令毫无输出。
EXP_SHA=$(sha256sum "build/$(basename "$ART")" | cut -d' ' -f1)
echo "   期望产物 sha256=${EXP_SHA%${EXP_SHA#????????????????}}…"
tar czf - tools "build/$(basename "$ART")" 2>/dev/null \
| timeout 1700 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o BatchMode=yes -o ConnectTimeout=25 "$A" \
      "set -u
       for d in /workspace/1to1 /workspace/1to1/* /workspace; do
           [ -d \"\$d/tools\" ] && PROJ=\$d && break
       done
       echo \"PROJ=\${PROJ:-未找到}\"
       cd \"\$PROJ\" || exit 9
       tar xzf - ; echo \"tar rc=\$?（仅参考）\"
       GOT=\$(sha256sum build/rkgame.rebuilt.elf 2>/dev/null | cut -d' ' -f1)
       echo \"GOT_SHA=\$GOT\"
       [ \"\$GOT\" = \"$EXP_SHA\" ] || { echo '★★ 产物 sha256 不符 ⇒ 中止（后置条件校验，不信 tar 的 rc）'; exit 8; }
       echo '--- 装依赖 ---'
       apt-get install -y -qq binutils-arm-linux-gnueabihf python3-pyelftools >/tmp/apt.log 2>&1
       echo \"apt rc=\$? objdump=\$(command -v arm-linux-gnueabihf-objdump || echo 缺)\"
       python3 -c 'import elftools' 2>/dev/null || python3 -m pip install -q --break-system-packages pyelftools capstone unicorn >>/tmp/apt.log 2>&1
       echo \"elftools=\$(python3 -c 'import elftools;print(\"OK\")' 2>&1 | tail -1)\"
       echo '--- 跑门禁 ---'
       sh tools/cnb_gates.sh $WANT 2>&1 | tail -35
       echo REMOTE-DONE" 2>&1 | tail -50
echo "== 完成（工作区 $SN 约 15 分钟后自动关闭）=="
