## R302（2026-11-01）—— 撤回 R301 修复（误判复核）+ 回滚重建 + 投放纠正

### 日期

2026-11-01（接 R301：上一轮"跳过 central directory uncompressed_size"修复经独立复核为误判，全部回滚）

### 完成事项

1. **误判复核（两份独立证据，非推断）**：
   - 证据一（反汇编）：工厂 `unzlocal_GetCurrentFileInfoInternal`（tool/factory_t1.txt，
     326 条指令）字段读取序列含 **getLong → sp+52**（= uncompressed_size 槽，
     结构体偏移 28，在 80 字节 memcpy 覆盖范围内）⇒ **工厂照样读这 4 字节**，
     "工厂跳过"的读法是错的。
   - 证据二（真机 trace 复读）：第 13 轮 trace.log 里 197 条中央目录条目
     （idx=0..196）名字**全部正确**（`1941_000.raw`→`arian_000.raw`，字母序、
     ASCII 干净），末次 `IO fread sz=15 n=1` 恰等于 `"arian_000.raw"` 长度 15
     ⇒ 解析器**字节对齐完美**；卡死是时间问题（jiffies 4748→4999）不是正确性问题。
   - 反事实：若不回滚，每条目错位 4B → 名字全 garbage → FindZipItemA 永不命中
     → 000.dat 缩略图功能整体报废（我引入的新回归）。
2. **回滚动作（逐字节）**：
   - 从远端 commit `3146e827146b` 取回修复前 `1to1/src/upstream/xunzip/unzip.cpp`
     （sha256 `e58433d41a0ed823caca95bbcfd11a90f1f96dfec09a8d8d49760fc22edc8f83`，
     与 `.XUnzip.src.sha256` 记录的修复前源码 sha 一致）覆盖本地。
   - 推送回滚 commit `100ec45dab04c34165f25a0aaab7212ffbd99853`（3 blobs，
     含 PROGRESS/PROJECT-MEMORY 同步），VERIFY 全通过。
3. **重建 + 确定性判定（CI 主动监控到完成）**：

   | workflow | run | 结论 | 关键产物 |
     |---|---|---|---|
     | 1to1-verify | #324 | success | rkgame.rebuilt.elf `642df312b238c7fe…` |
     | diag-build | #10 | success | rkgame.diag `8c6b505047897e00…` |
     | toolchain-ab | #53 | success | — |
     | rkgame-rebuild | #1199 | success | — |
     | 1to1-qemu-behav | #291 | failure | **既有诚实红**：#288/#289/#290 同 step 同形失败（rc=2，B6 全零基线 R171b） |

   - **交付版确定性**：`#324（回滚）== #322（10-25 修复前）` 逐字节相同
     （均 `642df312…`）⇒ 回滚确定 + 构建链确定（同源码重建得同一 sha256）。
   - **诊断版**：#10（`8c6b5050…`）与 #8（`f68569bf…`）仅差
     `src/diag/cgm_diag.c:301` 内嵌 `__DATE__/__TIME__`（"Nov 1 2026" vs
     "Oct 25 2026"）引起的字符串重排（mutex_lock×5 / REBOOT×2 / ====×21
     特征一致）⇒ 良性，代码功能相同。
4. **投放纠正（_sdcard_drop）**：
   - `cubegm/rkgame` 更换为 #10 回滚诊断版（`8c6b5050…`，原为作废的修复版
     `8689bb73…`）；`_archive/rkgame.rebuilt.elf` 更换为 #324 副本（原 `c289e55d…`）。
   - 新写 `DELIVERY-R302.txt`（权威清单，含撤回声明 + 证据链 + 三步流程）；
     `DELIVERY-R301.txt` 改写为 VOID 指向 R302。
   - **作废声明**：commit `13ca9538` 的 1to1-verify #323 / diag-build #9 产物
     （`c289e55d…` / `8689bb73…`）**不得使用**。

### 新发现与决策

1. **R301 的根因定案被推翻**：R301 断言"工厂机器码 @0x110d4 跳过 uncompressed_size"
   属读图错误；R300 原定的方向（**时序/看门狗**）重新成为唯一有效根因线。
2. **"第 12 轮清洁版 0.2s 闪退"说法无文档证据**：`真机验收日志/12/` 为空目录，
   GAP.md / PROJECT-MEMORY.md / PROGRESS.md 均无 round-12 记录 ⇒ 按未证实处理，
   不作为下一轮判据。
3. **纪律教训（写入记忆）**：反汇编结论上真机前必须过**两道独立检验**——
   ① 机器码侧行为与源码主张一致；② 真机观测数据与主张一致。R301 只做了
   机器码侧的单点读图，没拿第 13 轮 trace 交叉验证，导致"修复"反向引入回归。
   （与用户红线「"我没试过"≠"改不到"」同族：结论、假设、猜测必须分层标注。）

### 下一步待办

1. **原厂对照（P0，决定性）**：确认工厂打开 000.dat 时的 fread 形态
   （`fread sz=? n=?`）——判"我们逐字节 vs 工厂宽块读"。
   手段：反汇编 golden 003.dat 相关路径 + 取工厂原版真机日志（若可）。
2. **量化喂狗**：确认看门狗喂狗间隔与喂狗点（UpdateROM 的 reboot /
   driver.so 的 tick），判"间隔太短"还是"我们少了喂狗调用"。
3. 依 1/2 定修复：① 恢复工厂宽块读 ② filelist 遍历改缓存/异步 ③ 补喂狗调用。
4. 清理本轮临时脚本（`_monitor_ci.py` / `_download_artifacts.py` /
   `_download_r302.py` / `_unzip_prefix_rollback.cpp`）与 `_det_check/`。
