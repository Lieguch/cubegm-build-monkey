## R305b（2026-11-02）—— R305 三推送（`c4caceed4a`）CI 结论：3 绿 1 红，`toolchain-ab` **首次反转**

### 1. 四 run 结论（head_sha `c4caceed4a36`，推送上传 7 blob / 跳过 1015 未变更，VERIFY 1022/1022 blobs match）

| workflow | run id | 结论 | 说明 |
|---|---|---|---|
| `rkgame-rebuild` | `41553016699` | ✓ success | job `rkgame rebuild + qemu e2e` 全步骤 success ⇒ **三处 Rule A 修复源码编译+链接通过，产出新 ELF** |
| `toolchain-ab` | `41553016789` | ✓ **success** | job `ab` 全步骤 success。**先示连续 5+ 轮 failure 后首次反转** |
| `1to1-verify` | `41553016796` | ✓ success | job `P2-A stb_truetype 版本锁定` 全步骤 success |
| `1to1-qemu-behav` | `41553016828` | ✗ failure | job `P5 qemu 行为差分（factory vs rebuild）`；失败 step = **12「行为采集 + 差分 ★ 硬门禁」**（step 13 帧像素级定位成功；14-28 观测步骤 skipped——与前三轮同构） |

- 真绿验证：三个 success run 的**全部 steps 均为 success/skipped**，无 `continue-on-error` 聚合绕过。

### 2. `toolchain-ab` 反转的分层标注

- **已实测**：本轮 success（全 step success），前 5+ 轮 failure（rkgame 1:1 e5aef10e 起）。
- **未实测的推断**：反转与 R305 修掉的 UB（malloc 未初始化尺寸 / 指针比较 / 非对齐访问）有关 —— 双工具链（gcc vs clang）对 UB 的优化敏感性差异会放大为判据差。**未做对照实验，不作根因结论**。

### 3. `1to1-qemu-behav` 失败：定位已确证，判据行同形 diff **缺口如实记录**

- 已确证：失败 step 与前三轮（e5aef10e / 288fa2d0 / ad13c99b）**同一 step（12 行为采集+差分硬门禁）**；step 13 观测步骤同前（success）；14-28 观测步骤同前（skipped）。
- **缺口**：本轮判据行原文**未取到** —— 三条直连通道全部被本机 FastGithub 代理拦截（job logs 401 / artifact zip 401 / run check-runs 404）；GitHub connector 为 `auth-required`，本回合请求授权被 skipped。
  ⇒ **未证明**「本轮判据行与前三轮 diff 为空 ⇒ 继承态」；本段**不默认** qemu-behav 的失败是继承态。
- 补证路径（二选一，均需一次用户动作或 CNB 额度）：
  ① 授权 GitHub connector → MCP check runs 取 step 12 判据行 → 与 `_qemu_behav_log_prev.txt` / `_qemu_behav_log.txt` / `_qemu_behav_log2.txt` 做去时间戳 diff；
  ② CNB 云开发按 `tools/ci_qemu_behav.sh` 同口径复现 step 12（不消耗 Actions 预算）。
- 分层：qemu-behav 的「B6 观测天花板·诚实红 / B6A 渲染保真度差距」是 **R171b/R224 起长期跟踪的既有观测项**，与本轮 ZIPENTRY 修复的因果关系**未测**（QEMU 行为采集是否覆盖 000.dat 解压路径未验证）。

### 4. 纪律

- 本轮推送触发 4 workflow 属**源码改动进入构建链**的正常构建验证，非「为附记烧 CI」；本段（纯文档）单独推送**不触发任何 workflow**（paths 排除 `1to1/*.md`）。
