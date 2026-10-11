# 判据：`toolchain_ab.sh` 内嵌的 `ensure_tc` 也有慢下载缺陷（根治，不绕过）

**预登记**：动手改之前（2026-10-03，第 121 轮）。

## 病灶（云端`cnb-a2n-1k40p84gg` 实测）

```
curl -4 -fL --retry 5 --retry-delay 3 -C - --connect-timeout 20 \
     -o cache_tc/bootlin63.tar.bz2 https://toolchains.bootlin.com/...2017.05...tar.bz2
```
13 分钟只下了 21.4 MB / 63 MB（≈27 KB/s），`toolchain_ab.sh` 整体卡死。

## 根因（两处，缺一不可）

| # | 缺陷 | 依据 |
|---|---|---|
| **1** | `toolchain_ab.sh:82` 的 `curl -fsSL --retry 3 --max-time 900` **缺 `-4`** | HANDOFF §3.3 已实测：CNB→bootlin(法国 OVH) **IPv6 路由劣化**，默认 ~18 KB/s；强制 IPv4 提速 **4.3×** |
| **2** | 同处 **`--max-time 900`（15 分钟）** 在慢速下**必然超时** | 63 MB ÷ 27 KB/s ≈ 39 分钟 ≫ 15 分钟 |

★ 关键：**HANDOFF §3.3 只修了 `tools/fetch_bootlin63.sh`（独立脚本）**，
但 `toolchain_ab.sh` 里的 `ensure_tc()` 是**另一份内嵌副本**，**没被修到**
⇒ 同一个 URL 有**两处curl**，只有一处带 `-4`。

##为什么必须用真工具链（不是"可以省"）

`build_upstream.sh:83-91`：上游库用 `-nostdinc` 编译，头搜索顺序必须是
「组件自己的头 → GCC include → GCC include-fixed → sysroot/usr/include」。
**缺 Bootlin 的 glibc 2.24 头就`exit 4` 硬失败**（不假绿）。
⇒ 即便只跑 `zig-Os` 腿（`NEED_GCC=0`），`build_upstream` 仍需要它。

## 根治

**统一到一份 curl**（纪律：同一规则禁止写两处）：
`ensure_tc()` 不再自己拼 curl，而是**复用 `tools/fetch_bootlin63.sh`**；
并给 `fetch_bootlin63.sh` 的 `--max-time` 提到能容纳慢速的量级。

## 判据

- **T1** `grep -c 'curl.*toolchains.bootlin.com' tools/toolchain_ab.sh` = **0**（不再有内嵌副本）
- **T2** `fetch_bootlin63.sh` 两处 curl 均带 `-4`
- **T3** `--max-time` ≥ 3000（能容纳 27 KB/s 的极端慢速）
- **T4** 云端 `zig-Os` 单腿能在 **≤ 25 分钟**内完成 `toolchain_ab.sh`（含 214+25 文件编译与全量 diff）
- **T5** `BOOTLIN63_LOCAL=<本地tar>` 模式：`_dl` **一次网络都不碰**（直接 `cp`），
  且 `EXP`（期望大小）也**从本地 stat 取**、不查 Content-Length

**反证条件**：T4 不成立 ⇒ 慢速不只来自 curl（还有别的环节），
需`sh -x` 逐段计时，**不得**继续加超时硬扛。

## 已落地的根治（代码）

| 位置 | 改动 |
|---|---|
| `tools/toolchain_ab.sh` `ensure_tc()` | **删除内嵌 curl**，改为 `sh tools/fetch_bootlin63.sh`（T1）；新增**关键输入自检**（`gcc.br_real` + sysroot 必须在） |
| `tools/fetch_bootlin63.sh` `_dl()` | 新增**本地源优先**：`BOOTLIN63_LOCAL` ⇒ 直接 `cp`，零网络（T5） |
| `tools/fetch_bootlin63.sh` EXP段 | 本地源模式下 `EXP` 从本地 `stat` 取，**不查 Content-Length** |

★ 顺带修掉一个「**注释粘连**」事故：程序化替换 `ensure_tc` 时正则非贪婪匹配到函数内
第一个 `}`，把下一段注释与函数头粘连 ⇒ `sh -n` 报语法错。
**判据：`sh -n` 必须过**（这类改动靠肉眼看不出来）。

## 实测结果（云端 `cnb-a2n-1k40p84gg`）

### T5 ✅ 完整跑通（零网络）

```
$ BOOTLIN63_LOCAL=/tmp/tc.tar.bz2 sh tools/fetch_bootlin63.sh
   本地 tar 模式：期望大小 = 63685320 B（不查Content-Length）
  包大小 63685320 B
   bzip2 -t 校验通过
bootlin63 就绪：cache_tc/bootlin63
```

### T1 ✅ / T2 ✅（代码层，见上）

### ★★ 连带根治 2 处（都是本轮**实测踩到**的）

| 病灶 | 现象 | 根治 |
|---|---|---|
| **bzip2 命令不存在** | 云工作区 `zsh: command not found: bzip2`。旧版 `bzip2 -t "$TB" || {删包; exit 3;}` 把**完好包误判为损坏并删掉**（下一轮又得重传 40 分钟）；`tar -xjf` 也依赖它⇒ **根本无法解压** | ① 校验段先 `command -v bzip2`：**缺失 ⇒ 明确标注"不可判"并降级为只靠大小核对，不删包**；存在且失败才是真损坏 ② 下载循环的 break 条件同样加保护（否则 bzip2 缺失时**永远不 break ⇒ 白下 4 轮**）③ 环境侧 `apt-get install -y bzip2` |
| **僵尸 curl 覆盖已上传的完整包** | `pkill -f fetch_bootlin63` 只杀父进程，**curl 子进程存活**继续 `-C -` 续传，把 63 MB 覆盖回 7.5 MB | 必须按 **PID 精确 kill**（`ps -eo pid,args\| grep …\| kill -9`）；`pkill -f` 不足|

### 顺带确认的门禁行为（正确）

`toolchain_ab.sh` 在 0/1 腿量到时明确报
**「★ 判决不成立（0/1 条腿量到）⇒ 退出码 3（不可判，不得当作通过）」**
⇒ 没把构建失败当成「无差异」。这是 fail-closed 该有的样子。
