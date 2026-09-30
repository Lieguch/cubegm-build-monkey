# 交付前全量审计与补漏（device drop 前置门）— 2026-09-27

> 用户口径：「**当你自认为达到交给用户实测前，你先全量进行审计和补漏**」。
> 本文是"投放真机之前必须为真"的清单 + 本轮审计**实测结果**。任何一格为 ✗ 就不投放。

---

## 一、本轮审计新增发现（2 项，都属"造了闸门却没上锁"）

| # | 发现 | 严重度 | 证据 | 处置 |
|---|---|---|---|---|
| 1 | **末尾标签门禁从未接线**：`tools/scan_trailing_label.py` 在整个仓库里**没有任何 workflow / 脚本调用它** ⇒ 它永远不会让构建变红。日志里"256 文件全树 0 处"是**手工跑过一次**的结果。 | ★★★ 门禁形同不存在 | `grep -n scan_trailing_label .github/workflows/*.yml tools/*.sh` → **0 命中** | 已加 CI 步骤 `id: s44`（含 `--selftest` + 全树扫描），并把 `ci_gate_summary.py` 的 `MIN_STEPS` 40 → **44**（防"步骤丢了还报绿"） |
| 2 | **该门禁自己的自证有 1 条失败**：`缺陷态 连续两个末尾标签 ⇒ 都报`，实测 `got=['B'] want=['A','B']` ⇒ `A: B: }` 形态**只报 B、漏报 A**。 | ★★ 检测盲区 | `python tools/scan_trailing_label.py --selftest` → 7 条 **失败 1 条** | 已修：跳过**标签链**再判有效下一条语句。修后 `--selftest` **7/7 通过**，全树扫描仍 PASS（256 文件 0 处，无误报） |

> ★ 这两条的价值：它们正属于用户反复强调的"**假绿**"家族 —— 一个不跑的门禁 + 一个自证失败却被当通过的检测器。

---

## 二、本轮审计：门禁自证全景（本地可跑部分）

| 门禁 | 自证结果 |
|---|---|
| `diff_exec --self-test` | **69 条，失败 0**（本轮新增 3 条，含"把 INFO 当加数"反例） |
| `audit_vs_factory --selftest` | **14 条，失败 0** |
| `dup_sym_gate --self-test` | **9 条，失败 0** |
| `diverge_cluster --self-test` | **11 条，失败 0** |
| `libc_model --self-test` | **32 条，失败 0** |
| `lint_setu_order --self-test` | **8 条，失败 0** |
| `lint_ci_reach --self-test` | **全部通过（仪器可用）** |
| `scan_trailing_label --selftest` | 修前 **7 条失败 1** → 修后 **7 条失败 0** |
| `scan_upstream_fingerprint` | 无新增 FAIL；4 项已知未对齐（基线豁免，见台账） |

**本地**跑不了、**必须走 CI**（依赖 `arm-linux-gnueabihf-objdump` / `readelf` 或 Linux 环境）：
`scan_cxx_abi` · `scan_symbol_delta` · `scan_dead_loop` · `scan_kr_argcount` · `scan_livein_args` ·
`ci_p2a_stb` · `fa_call_ctx` · `funcdump` · `factory_fn_stack` · `push_1to1` · `arm_dis`。
⇒ **交付前必须有一轮 CNB/GitHub CI 全绿**，本机自证不能替代。

---

## 三、投放真机前必须为真的清单（drop7）

| # | 项 | 判据（机械） | 现状 |
|---|---|---|---|
| 1 | 上游版本对齐 | mxml 2.9 ✓（DIVERGE 75→57）；libiconv 1.16（本轮实测中）；stb ≤1.22 / Helix 待做 | 进行中 |
| 2 | 行为尺回归 | `diff_exec` DIVERGE **不得回升**；`PASS+DIVERGE+TRUNC+SKIP == 共有函数` | ✓ 自洽校验已内置并 fail-closed |
| 3 | ABI / 链路 / 动态段 | `abi_check.py` / `link_audit` / `dyn_audit` 全 PASS | 待最终产物 |
| 4 | **投放前 sha256 对账**（硬规则，第 50 轮立） | 投放包内每个候选的 sha256 必须与**本轮产物**逐个相等；对不上就不投放 | 待做 |
| 5 | 一页部署卡 | 卡上必须有：卡盘符 `L:` / 目标目录 / 候选清单 / 期望现象 / 失败时留什么日志 | 待做 |
| 6 | 诚实声明 | 未验证项全列（见 §四） | 本文 |

---

## 四、诚实声明（**没有**验证的）

1. 重建产物**从未在真机上成功启动过**（2 次尝试均失败；根因已定位并修复；修复版未上机）。
2. 真机五项验收（19088 游戏 / 中文 UI / 全菜单 / 存档 / BGM）**0/5**。
3. 本机自证**不等于** CI 全绿：11 个门禁工具本机跑不了（见 §二）。
4. `INFO`（内联等价）桶是**重叠计数**，不可与 PASS/DIVERGE/TRUNC 相加。
5. mxml 换 2.9 后仍余 57 个 DIVERGE —— 其中 `_mxml_entity_cb` / `__libc_csu_init` 等 mxml 相邻项
   与 zlib/unzip 工具类、libiconv 表类仍在；**不代表"换完版本就收口了"**。
