## R304（2026-11-02）—— R303 文档推送 + CI 主动监控到 closure；qemu-behav 失败定性为「既有红、零回归」；B6A 长期线分层归档

### A. 本轮推送（doc-only）
- commit `288fa2d0cb71403dc81cd83c5c1768d90c0be070`，增量 3 blob：
  `PROGRESS.md`（980,631 B）/ `PROJECT-MEMORY.md`（558,192 B）/ `tools/R303_section.md`（7,023 B）；
  VERIFY 1019/1019 blobs match。**代码/二进制零变更**。

### B. CI 主动监控（本轮内查+判，不建自动化）
| run | workflow | 结论 |
|---|---|---|
| 41392369138 | rkgame-rebuild | success |
| 41392369177 | 1to1-verify | success |
| 41392369144 | 1to1-qemu-behav | failure（step 12 硬门禁 rc=2） |

### C. qemu-behav 失败定性：既有红，**非本轮回归**（A 轮级证据）
- 与上轮 `41389453113`（head e5aef10e）**jobs/steps 逐位一致**：同样只红 step 12；
  PASS/FAIL 判据行（去时间戳）**diff 为空**：
  `B6 b5449dc5 vs b5449dc5`、`B6A dfdaf563(1280x720x2560) vs ffc51130(1280x720x2560)`、`B6R 3072 vs 3072`。
- 两轮 rebuild ELF 同为 `642df312b238c7fe`（确定性构建同值）⇒ CI 侧二进制没动过；
  且该 ELF 与 R303 的 src/diag 改动零交集（diag 是独立构建轨）。
- B1~B8b、M0/M1/M4/M7/MX 全 PASS、里程碑差集为空 ⇒ **行为流与工厂完全同步**，
  红只落在「画面内容观测」两层。

### D. 两层红的分层归档（防混为一谈）
1. **B6 全零基线** = 观测天花板·诚实红（R171b 钉死）：两侧都没测到像素（`b5449dc5`），
   语义是「没测到」而非「不一致」；根因是 DRM 桩 1280×1280 AR24 与实参
   1280×720 RGB565 几何/格式双双不同构（R221）。
2. **B6A** = 长期跟踪的**渲染保真度差距**（时间线）：
   - R221 初测：factory `dfdaf563` vs rebuild `dfdaf563` ⇒ 当时 **B6A PASS**；
   - R224 起：rebuild 确定性偏离为 `ae825958`，factory 恒 `dfdaf563`（6/6 稳定、零交集）；
   - R303 后（本轮）：rebuild 演进为 `ffc51130`，factory 仍 `dfdaf563`（与 R221 云开发实测同值）；
   - 已排除两条解释：采样帧差（factory vs control 6/6 同值、rebuild 6/6 另一值）、
     工具链噪声（换本地工具链构建的同源 ELF 哈希照旧）。
   - 待办（沿用 R221/R224 口径，**非新天花板**）：云开发用 rebuild ELF 逐帧
     `[abiprobe] disp#N` 序列对拍 + 16 条带分区哈希（R224 已有仪器）定位差异屏幕区域。
   - 【分层标注】「rebuild 帧内容确定性偏离 factory」= 已实测；「`ffc51130` 具体差在哪」= 未实测，
     上述逐帧对拍未跑之前不得下任何根因结论。

### E. 纪律留痕
- doc-only 推送也照样主动监控到 closure（不等失败来问）；判回归第一问永远是「代码/二进制变了吗」。
- 已知红也逐轮取证：本轮两份对比日志 `_qemu_behav_log.txt`（288fa2d0）/
  `_qemu_behav_log_prev.txt`（e5aef10e），结论可复算。
- 会话临时分析脚本已清理（8 个 `_*.py`）；两份 CI 日志作为证据留存项目根目录。
