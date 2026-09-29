#!/bin/sh
# =============================================================================
# cnb_ca_exp.sh —— 在 CNB**云原生开发工作区**里跑「编译器对齐」实验（GCC 6.3 单变量）。
#
# ## 平台分工（2026-09-29 定，与用户口径一致：CNB 托管 + CNB 云开发 + GitHub 构建）
#   云开发**只承担只有 Linux 能做的那一段**：用 bootlin63（GCC 6.3 / glibc 2.24 / binutils 2.27，
#   与工厂 GCC 6.2.0 + gold 1.12 + glibc 2.24 同族）**交叉编译 + 用 ld.lld 链接**，
#   产出 `build/ab/gcc63.elf`。
#   行为尺（`diff_exec.py`，Unicorn 纯用户态）**本机 Windows 一样能跑** ⇒ 云上 `CA_SKIP_RULER=1`
#   跳过第 8~9 步，把产物取回本机用 `tools/ca_judge.sh` 判。
#   ⇒ 云上单次会话只花 ~10 分钟，不再踩「无心跳被回收」的坑。
#
# ## 为什么必须**单连接**（历史教训）
#   工作区回收 = 检测不到心跳超过 keepAliveTimeout（`.cnb.yml` 的 `$: vscode` 已声明 18h）。
#   把"上传"和"执行"拆成两次 SSH，一旦会话空闲被回收，`/tmp` 与服务就没了。
#   本脚本把 tar **管道**进同一个 ssh 的 stdin，并在**同一会话**里装依赖 + 跑实验 + 回传。
#
# ## 串流纪律（本次踩到的坑）
#   stdin = 上传的 tar，stdout = **回传的 tar** ⇒ 远端**任何日志都不能写 stdout**，
#   一律重定向进 `/tmp/ca_run.log`，最后把这个文件一起打进回传包。
#
# 前置: `.cnb.yml` 的 `$: vscode` 已声明 `keepAliveTimeout: 18h`（commit 392b514）。
# 用法:  sh tools/cnb_ca_exp.sh
# 产物:  build/ab/gcc63.elf（本机，供 ca_judge.sh）· report/_ca_all.txt（云上日志）
# 退出码: 0 成功 / 9 前置缺失 / 11 远端实验失败 / 13 未取到 SSH / 14 回传包校验失败
# =============================================================================
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CNB_DIR="/c/Users/Administrator/.workbuddy/binaries/node/cli-connector-packages/cnb"
export PATH="$PATH:$CNB_DIR"
REPO="lieguch/cubeGM"
PYX="${PYX:-python}"
RET="${RET:-D:/output/_ca_return.tar.gz}"
ERR="${ERR:-D:/output/_ca_ssh_err.txt}"

for d in src tools ledger build/rkgame.rebuilt.elf report/_final_diff.txt cache_tc/bootlin63.tar.bz2; do
    [ -e "$ROOT/$d" ] || { echo "!! 缺前置 $d" >&2; exit 9; }
done
# ★ 为什么把 64 MB 的 bootlin63 包一起上传（而不是让云上去下）：
#   2026-09-29 实测 —— 云上下到 59,703,296 B 就断了（期望 63,685,320 B），bzip2 报
#   "Compressed file ends unexpectedly"。本地这份是**已验证完整**的（bzip2 -t 通过），
#   传上去 = 把"网络不确定性"从关键路径上摘掉（也正是本轮要的"根本解法"）。
echo "   已备本地工具链包 cache_tc/bootlin63.tar.bz2（$(stat -c%s "$ROOT/cache_tc/bootlin63.tar.bz2") B，bzip2 -t 已验证）"

echo "== 1) 开工作区（读 HEAD 的 .cnb.yml，含 keepAliveTimeout=18h）=="
SN="${WS_SN:-}"
if [ -z "$SN" ]; then
    OUT=$(timeout 300 cnb workspace start-workspace --repo "$REPO" --branch main 2>&1)
    printf '%s\n' "$OUT" | sed -n '1,10p'
    SN=$(printf '%s' "$OUT" | sed -n 's/.*"sn": *"\([^"]*\)".*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's/.*sn: *\(cnb-[^ ]*\).*/\1/p' | head -1)
    [ -n "$SN" ] || SN=$(printf '%s' "$OUT" | sed -n 's#.*/workspace/[a-z-]*/\(cnb-[a-z0-9]*-[a-z0-9]*\)-[0-9]*/.*#\1#p' | head -1)
fi
echo "   sn=${SN:-?}"

echo "== 2) 等 SSH 就绪 =="
A="${WS_SSH:-}"
i=0
while [ -z "$A" ] && [ "$i" -lt 20 ]; do
    D=$(timeout 90 cnb workspace get-workspace-detail --repo "$REPO" --sn "$SN" 2>&1)
    A=$(printf '%s' "$D" | sed -n 's/^ *ssh: *ssh *\([^ ]*@[^ ]*\)$/\1/p' | head -1)
    i=$((i + 1)); [ -n "$A" ] || sleep 12
done
[ -n "$A" ] || { echo "!! 未取到 ssh 地址（可用 WS_SSH=<user@host> 指定）" >&2; exit 13; }
echo "   ssh=$A"

echo "== 3) 单连接：上传 → 装依赖 → 编译+链接（跳过尺子）→ 回传 =="
cd "$ROOT" || exit 9
tar czf - src tools ledger build/rkgame.rebuilt.elf report/_final_diff.txt cache_tc/bootlin63.tar.bz2 2>/dev/null \
| timeout 3500 ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o BatchMode=yes -o ConnectTimeout=25 \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=20 "$A" \
      "set -u
       for d in /workspace/1to1 /workspace; do [ -d \"\$d/src\" ] && PROJ=\$d && break; done
       PROJ=\${PROJ:-}
       if [ -z \"\$PROJ\" ]; then echo 'PROJ 未找到' > /tmp/ca_run.log; tar czf - /tmp/ca_run.log 2>/dev/null; exit 9; fi
       cd \"\$PROJ\" || exit 9
       mkdir -p build/ab report
       { echo \"PROJ=\$PROJ\"; echo \"PWD=\$(pwd)\"; } > /tmp/ca_run.log
       tar xzf - --no-same-owner 2>>/tmp/ca_run.log; echo \"untar rc=\$?（仅参考）\" >> /tmp/ca_run.log
       echo \"--- 落地核对 ---\" >> /tmp/ca_run.log
       echo \"src/*.c = \$(find src -name '*.c' | wc -l) ; tools/*.sh = \$(ls -1 tools/*.sh | wc -l)\" >> /tmp/ca_run.log
       echo \"--- 装依赖 ---\" >> /tmp/ca_run.log
       (apt-get update -qq && apt-get install -y -qq binutils-arm-linux-gnueabihf python3-pip curl ca-certificates bzip2) >>/tmp/ca_run.log 2>&1
       echo \"apt rc=\$? objdump=\$(command -v arm-linux-gnueabihf-objdump || echo 缺)\" >> /tmp/ca_run.log
       python3 -m pip install -q --break-system-packages pyelftools capstone unicorn ziglang >>/tmp/ca_run.log 2>&1 \
         || python3 -m pip install -q pyelftools capstone unicorn ziglang >>/tmp/ca_run.log 2>&1
       python3 -c 'import elftools,capstone,unicorn,ziglang;print(\"deps OK\")' >>/tmp/ca_run.log 2>&1 || echo 'deps 有缺' >>/tmp/ca_run.log
       echo \"--- 编译器对齐实验（CA_SKIP_RULER=1）---\" >>/tmp/ca_run.log
       CA_SKIP_RULER=1 BASE_DV=${BASE_DV:-44} sh tools/_ca_all.sh >>/tmp/ca_run.log 2>&1
       echo \"ca_all rc=\$?\" >>/tmp/ca_run.log
       echo \"--- 回传 ---\" >>/tmp/ca_run.log
       ls -la build/ab/gcc63.elf report/_ca_all.txt >>/tmp/ca_run.log 2>&1
       tar czf - build/ab/gcc63.elf report/_ca_all.txt /tmp/ca_run.log 2>/dev/null
       echo REMOTE-DONE >&2" \
      > "$RET" 2> "$ERR"
rc=$?
echo "   ssh 管道 rc=$rc （stderr → $ERR）"
[ -s "$RET" ] || { echo "!! 回传包为空：$RET" >&2; sed -n '1,20p' "$ERR" >&2; exit 14; }
echo "   回传包 $(stat -c%s "$RET") B"
# ★ 校验用 python tarfile，不用 `tar tzf >/dev/null`：MSYS 的 tar 在管道重定向下会**假失败**
#   （本轮实测：`tar tzf` 单独跑 rc=0，脚本里却判成"不是有效 tar.gz"，白丢一次实验）。
RET="$RET" "$PYX" - <<'PYE'
import os, sys, tarfile
p = os.environ['RET']
try:
    with tarfile.open(p, 'r:gz') as t:
        names = t.getnames()
except Exception as e:
    print('!! 回传包不是有效 tar.gz：%s' % e, file=sys.stderr); sys.exit(14)
print('   回传成员：%s' % (names,))
if 'build/ab/gcc63.elf' not in names:
    print('!! 回传包缺 gcc63.elf（远端实验失败）', file=sys.stderr)
    log = [n for n in names if n.endswith('ca_run.log')]
    if log:
        with tarfile.open(p, 'r:gz') as t:
            sys.stderr.write(t.extractfile(log[0]).read().decode('utf-8', 'replace')[-4000:])
    sys.exit(11)
PYE
[ $? -eq 0 ] || exit $?

echo "== 4) 解包到本地 =="
# ★ 解包也用 python（MSYS 的 tar 会把 `tmp/...` 落到奇怪位置，且带 uid 告警）
RET="$RET" ROOT="$ROOT" "$PYX" - <<'PYE'
import os, sys, tarfile
p, root = os.environ['RET'], os.environ['ROOT']
rlog = os.path.join(root, '..', '_ca_remote_run.log')
with tarfile.open(p, 'r:gz') as t:
    for m in t.getmembers():
        if m.name.startswith('tmp/'):
            with open(rlog, 'wb') as fh:
                fh.write(t.extractfile(m).read())
            continue
        m.uid = m.gid = 0
        m.uname = m.gname = ''
        t.extract(m, root, set_attrs=False)
print('   已解包；远端运行日志 → %s' % os.path.normpath(rlog))
PYE
ls -la "$ROOT/build/ab/gcc63.elf" 2>/dev/null || echo "!! 本地未解出 gcc63.elf"
echo "== 云上日志尾部（完整见 report/_ca_all.txt）=="
tail -34 "$ROOT/../_ca_remote_run.log" 2>/dev/null || true
echo "== 下一步：sh tools/ca_judge.sh（本机跑行为尺 + 判决，基线自证）=="
