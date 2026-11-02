## R303（2026-11-02）—— 根因反转：R300「000.dat 遍历超时」被证伪；定位到**诊断仪自伤**；交付去自伤 + 内核取证版诊断仪

### A. 跨轮交叉验证：R300 根因被推翻（此前 §0.48 C 节"有效根因线"作废）
把 `_sdcard_drop/真机验收日志/{1..13}` 全部 trace.log 逐轮解析（BOOT enter 的 jiffies /
末行 jiffies / 事件直方图 / snapshot 位置）：

| round | lines | BOOT enter | 末行 | Δ存活 | BOOT 次数 | 是否开 000.dat | fread 次数 |
|---|---|---|---|---|---|---|---|
| 1 | 23,488 | 3551 | 82757 | 792.1 s | **11** | 否 | 1,521 |
| 2 | 2,033 | 3547 | 4315 | 7.7 s | 1 | 否 | —（早崩，有 crash.txt） |
| 3 | 2,065 | 3547 | 4316 | 7.7 s | 1 | 否 | —（早崩，crash.txt 7,459 B） |
| 4 | 2,126 | 3551 | 5008 | 14.57 s | 1 | **否** | 1,515 |
| 5 | 2,147 | 3566 | 5051 | 14.85 s | 1 | 否 | 1,515 |
| 6 | 13,582 | 3590 | 48660 | 450.7 s | **4** | 否 | 1,515 |
| 7 | 2,097 | 3541 | 5079 | 15.38 s | 1 | 否 | 1,515 |
| 8 | 2,144 | 3586 | 5016 | 14.30 s | 1 | 否 | 1,515 |
| 9 | 2,222 | 3575 | 5031 | 14.56 s | 1 | 否 | 1,515 |
| 10 | 2,219 | 3643 | 5026 | 13.83 s | 1 | 否 | 1,515 |
| 11 | 2,155 | 3545 | 5028 | 14.83 s | 1 | 否 | 1,515 |
| 13 | 22,216 | 3592 | 5000 | 14.08 s | 1 | **是** | 20,971 |

结论（三条互相独立）：
1. **round 4~11 从未打开 000.dat**，fread 仅 1,515 次，却死在与 round 13（20,971 次
   fread、正在猛跑 zip）**同一绝对 jiffies 窗口 4999~5079** ⇒ 与 zip/IO 负载无关。
2. round 1 存活 792 s / 11 次进程重启、round 6 存活 450 s / 4 次重启 ⇒
   **设备不会在"开机 50 s"处整机复位** ⇒ "设备/内核固定超时复位"这一猜测也被否掉。
3. 所有 trace 末行**以完整换行结束**（无半行截断）⇒ 不是写盘中途断电式撕裂。

### B. 根因反转：真正的嫌疑是**诊断仪自己**（快照风暴）
- **形态证据**：round 4/7/8/11 的全部 25~35 条 `## snapshot` **集中在同一个 jiffies**
  （5008 / 4962~5028 / 4999~5000）；而这些轮的 `frames.snap.bin` = **0 字节**
  （文件已创建、写入全失败）。round 13 的同文件 = 2,992,776 B。
- **代码机制**（`src/diag/cgm_diag.c`）：
  `cgm_tick()` 用 `g_last_snap = m + 1` ⇒ 下一次 `m - g_last_snap` = -1 ⇒
  **无符号下溢成 4294967295** ⇒ `>= CGM_SNAP_MS` 恒真 ⇒ **每个 instrument 调用触发一次快照**；
  每次快照 `dump_ring()` = 65536 × 12 B = **786 KB 写 SD 卡**
  ⇒ 末尾一次突发 **~27 MB 写盘** ⇒ 卡写爆 / 写阻塞 ⇒ 进程定格、日志终止。
  （`g_ms` 每 128 次调用才刷新，低事件率阶段下溢窗口持续存在。）
- **写失败不可见**：旧 `wraw()` 遇 `write() <= 0` 直接 return ⇒ 错误被静默吞掉，
  所以"0 字节 + 有快照记录"这一矛盾此前无法判读。
- **次生缺陷**：1 字节 fread（round 13：18,216 次）逐条写行 ⇒ ~900 KB/轮纯日志放大；
  R265 把 SIGALRM/SIGVTALRM/SIGPROF 挂 on_alarm **吞掉**（R270 起 diag 默认已不武装
  定时器 ⇒ 继续吞只会掩盖"真正的杀手"）。

### C. 本轮改动（只动诊断仪两文件，**零业务逻辑改动**）
`src/diag/cgm_diag.c`
1. `wraw()` 记 `g_werr` / `g_werr_no`（errno），由周期行带出。
2. `cgm_do_snap()`：**周期快照不再落盘**（只留一行计数）；环形帧历史改由崩溃/退出
   路径一次性落盘。
3. `cgm_tick()`：cadence 改**有符号差**（32 位回绕安全）、`g_last_snap = m`；
   新增弱符号钩子 `cgm_kernel_periodic()`。
4. 新增 `on_timer_sig()`：SIGALRM/SIGVTALRM/SIGPROF 改为「记录一行 → 恢复默认动作
   → 重发」= 留证据但**不改结局**（诊断仪纪律）。
`src/diag/cgm_wrap.c`
5. `__wrap_fread`：1 字节读只计数（`fread1`）不写行。
6. 新增内核侧取证：`cgm_kernel_boot()`（启动一次）与 `cgm_kernel_periodic()`（每 5 s）：
   statfs 剩余空间 + shm 心跳增量（shmget 0x4d2，与原厂 ShareMemCreat 同 key/大小）
   + `/proc` 全进程表 + watchdog sysfs（identity/state/timeout/bootstatus）
   + `/proc/sys/kernel/watchdog{,_thresh}` + panic + uptime/loadavg ⇒ 落 `proc.txt`。
   全部走 `__real_*` 原函数，不经 --wrap ⇒ 不递归、不污染 trace.log。

### D. CI 与产物（主动监控，已完成）
- 推送：`tools/push_1to1.py` → commit `e5aef10e413946182210ff623f7398bec5f691b4`
  （增量 2 blob；VERIFY 1018/1018）。
- `diag-build` run **41389453203 → success**；构建门禁 PASS(0 项失败)、0 warning；
  artifact `rkgame-diag` id 13116469265。
- 产物：`94715fe00db12ea5e15a77fc3a4f2bf1c7ef31c754417e81fb4b045ac9e44b86`
  （5,465,236 B）⇒ `_sdcard_drop/latest_diag/rkgame.diag` = `_sdcard_drop/cubegm/rkgame`，
  侧车 `rkgame.diag.sha256` 同步。**CI 侧 sha256 与本地逐位一致。**
- 交付清单：`_sdcard_drop/DELIVERY-R303.txt`（权威）。
- 下载通道备注：artifact 302 到 `*.blob.core.windows.net`，**必须手动跳转且不带
  Authorization 头**（带了会被 Azure 判 401 InvalidAuthenticationToken）。

### E. 下一步（关键路径在用户侧：一次 5~10 分钟的单变量对照）
1. **实验 A（最决定性）**：删/改名 SD 卡 `cubegm/_diag/` → 把
   `latest_rebuilt/rkgame.rebuilt.elf`（`642df312…`，无任何诊断仪）复制成
   `cubegm/rkgame` → 上电静置 3 分钟 → 只回「重启了？首次重启距上电多少秒？」
   · 3 分钟不重启 ⇒ 故障源在诊断仪/写盘侧，本轮已修；
   · 仍固定 ~14.5 s ⇒ 与诊断仪无关 ⇒ 用新 diag 的 proc.txt + "## KS" 抓设备/内核侧。
   顺手看一眼 SD 卡**剩余空间**（第 4/7/8/11 轮写失败的最可能原因就是卡满）。
2. **实验 B**：换回本轮 diag（`94715fe0…`）跑 3 分钟，回传 `_diag/` 全目录。
   先看三样：`## KS` 行（sd_free/sd_avail/shm_delta）、`## snapshot` 行（werr/errno）、
   `proc.txt`（watchdog 状态 + 设备上的守护进程）。
3. **待澄清**：上一轮"清洁版也无限重启（0.2s 闪无日志）"——第 12 轮目录为空、
   无任何文档记录，且 0.2s 与第 4~13 轮签名（BOOT enter + ~14.5 s）对不上 ⇒ 按未证实处理，
   请在实验 A 直接回答"启动即崩"还是"跑十几秒后死"。

### F. 纪律教训
**仪器自身必须零干扰，且自身缺陷要能被自己看见。** 本项目连续多轮被"诊断仪的
写放大/信号吞掉"带偏方向，而真正的被测对象（复刻程序）反而被怀疑了 8 轮。
⇒ 新增门禁：① 任何周期落盘量必须与"真机 SD 卡写入预算"对账（本例 786 KB/次 ×
风暴次数 = ~27 MB）；② 写失败必须有 errno 计数；③ 诊断仪不得**吞**被测对象可能被
杀它的信号（记录 + 转发）。另：**"多轮一致"要用来证伪，也要用来证真**——
round 4~11 未开 000.dat 却同窗死亡，正是它证伪了 R300。
