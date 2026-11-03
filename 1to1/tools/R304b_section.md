## R304b（2026-11-02）—— 二推（`ad13c99b`）CI 复核：**三轮同形**，qemu-behav 失败闭合定性为「100% 继承态」

- 二推触发的 3 run：`rkgame-rebuild` `41397083792` ✓ / `1to1-verify` `41397083752` ✓ / `1to1-qemu-behav` `41397083734` failure。
- 与 e5aef10e / 288fa2d0 两轮**判据行（去时间戳）diff 为空**，rebuild ELF 三轮恒 `642df312b238c7fe`。
  ⇒ 连续三轮、同一二进制、同一判据、同一失败点 ⇒ qemu-behav 的红是**可证明的继承态**（B6 观测天花板 + B6A 长期跟踪线，见 §0.50 C），与 R303/R304 的一切改动零相关。
- 证据留存（三份）：`_qemu_behav_log_prev.txt`（e5aef10e）/ `_qemu_behav_log.txt`（288fa2d0）/ `_qemu_behav_log2.txt`（ad13c99b）。
