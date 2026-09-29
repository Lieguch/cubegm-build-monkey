#!/bin/sh
# =============================================================================
# cnb_ruler.sh —— 在 **CNB 云开发** 跑「行为尺」（`diff_exec --batch`），本机内存不够时的正路。
#
# ## 为什么这是对的（不是权宜）
# 用户口径：**CNB 托管 + CNB 云开发 + GitHub 构建**。行为尺是**纯计算**，属于"云开发"的活；
# 本机 Windows 的提交限额被 pagefile=0 卡死（提交可用 ~0.07 GB），尺子**根本跑不成整批**。
# 云开发：16 GB 内存、无 pagefile 约束、`keepAliveTimeout: 18h`（`.cnb.yml` 的 `$: vscode`）。
#
# ## 一次会话跑两件事
#   ① **默认路径**：产出权威报告 + **不截断明细**（`--dump-rows`，归类唯一合法数据源）；
#   ② **`CGM_MACHINE_REUSE=1`**：验证"执行环境复用"改造是否**逐字等价**
#      （期望 共有 782 ｜ PASS 737 ｜ DIVERGE 40 ｜ TRUNC 5 ｜ REFDEAD 0 ｜ SKIP 0）。
#
# ## 两个必须遵守的通道纪律（前几轮实测踩出来的）
#   * **单连接**做"上传 + 运行"（拆成两次 SSH 会因回收丢 /tmp）；
#   * **回传必须分块**：CNB 的 SSH 会**静默截断较大的 stdout**（2.5 / 3.4 MB 处），
#     所以用 `tools/cnb_ws_fetch.sh`（`dd` 分块 + sha256 对账）。本脚本复用同一个 `_fetch`。
#
# 用法:  sh tools/cnb_ruler.sh
# 退出码: 0 成功 / 9 前置缺失 / 13 未取到 SSH / 14 回传校验失败
# =============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CNB_DIR="/c/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/cnb"
export PATH="$PATH:$CNB_DIR"
REPO="lieguch/cubeGM"
OUTDIR="${OUTDIR:-D:/output/_ruler_cloud}"
PYX="${PYX:-python}"

for d in tools ledger golden/factory.rkgame.bin golden/ghidra-perfn.tar.gz build/rkgame.rebuilt.elf; do
    [ -e "$ROOT/$d" ] || { echo "!! 缺前置 $d" >&2; exit 9; }
done
mkdir -p "$OUTDIR"

echo "== 1) 开/复用云开发工作区（读 HEAD 的 .cnb.yml：keepAliveTimeout=18h）=="
SN="${WS_SN:-}"
A="${WS_SSH:-}"
if [ -z "$SN" ] && [ -z "$A" ]; then
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    printf '%s\n' "$OUT" | sed -n '1,8p'
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
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

echo "== 3) 单连接：上传 → 装依赖 → 跑两遍尺子（默认 + 复用）=="
cd "$ROOT" || exit 9
tar czf - tools ledger golden/factory.rkgame.bin golden/ghidra-perfn.tar.gz build/rkgame.rebuilt.elf 2>/dev/null \
| timeout 3500 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o BatchMode=yes -o ConnectTimeout=25 \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=20 "$A" \
      "set -u
       for d in /workspace/1to1 /workspace; do [ -d \"\$d/tools\" ] && PROJ=\$d && break; done
       PROJ=\${PROJ:-}
       { echo \"PROJ=\$PROJ\"; date -u; } > /tmp/ruler_run.log
       [ -n \"\$PROJ\" ] || { echo 'PROJ 未找到'; exit 9; }
       cd \"\$PROJ\" || exit 9
       mkdir -p build report
       tar xzf - --no-same-owner 2>>/tmp/ruler_run.log
       echo '--- 装依赖 ---' >> /tmp/ruler_run.log
       (apt-get update -qq && apt-get install -y -qq python3-pip curl ca-certificates) >>/tmp/ruler_run.log 2>&1
       python3 -m pip install -q --break-system-packages pyelftools capstone unicorn >>/tmp/ruler_run.log 2>&1 \
         || python3 -m pip install -q pyelftools capstone unicorn >>/tmp/ruler_run.log 2>&1
       python3 -c 'import elftools,capstone,unicorn;print(\"deps OK\")' >>/tmp/ruler_run.log 2>&1
       echo '--- ① 默认路径 ---' >> /tmp/ruler_run.log
       python3 tools/diff_exec.py --batch --steps 3000 --ours build/rkgame.rebuilt.elf \
           --out report/_cloud_diff.txt --dump-rows report/_cloud_rows.json >>/tmp/ruler_run.log 2>&1
       echo \"default rc=\$?\" >> /tmp/ruler_run.log
       echo '--- ② CGM_MACHINE_REUSE=1（对账用）---' >> /tmp/ruler_run.log
       CGM_MACHINE_REUSE=1 python3 tools/diff_exec.py --batch --steps 3000 --ours build/rkgame.rebuilt.elf \
           --out report/_cloud_diff_reuse.txt >>/tmp/ruler_run.log 2>&1
       echo \"reuse rc=\$?\" >> /tmp/ruler_run.log
       echo '--- 汇总行 ---' >> /tmp/ruler_run.log
       grep -a '共有函数\\|汇总：PASS\\|自洽校验\\|明细已写出' report/_cloud_diff.txt >>/tmp/ruler_run.log 2>&1
       grep -a '共有函数\\|汇总：PASS\\|自洽校验' report/_cloud_diff_reuse.txt >>/tmp/ruler_run.log 2>&1
       echo REMOTE-DONE >&2" > "$OUTDIR/_stdout.bin" 2> "$OUTDIR/_stderr.txt"
echo "   ssh 管道 rc=$?"

echo "== 4) 分块取回（含 sha256 对账）=="
FETCH="$ROOT/tools/cnb_ws_fetch.sh"
for f in report/_cloud_diff.txt report/_cloud_diff_reuse.txt report/_cloud_rows.json; do
    L="$OUTDIR/$(basename "$f")"
    if ! sh "$FETCH" "$A" "/workspace/1to1/$f" "$L"; then
        sh "$FETCH" "$A" "/workspace/$f" "$L" || echo "   !! 取回失败：$f" >&2
    fi
done
sh "$FETCH" "$A" /tmp/ruler_run.log "$OUTDIR/ruler_run.log" || true

echo "== 5) 结果 =="
sed -n '1,200p' "$OUTDIR/ruler_run.log" 2>/dev/null | grep -aE "共有函数|汇总：PASS|自洽校验|明细已写出|rc=|deps OK|PROJ" || true
echo "== 完成。产物在 $OUTDIR =="
echo "   记得省钱：cnb workspace workspace-stop --sn $SN"
