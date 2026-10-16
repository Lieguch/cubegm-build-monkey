## R183（2026-10-16）

### 一、日期

2026-10-16（CNB 云开发 `cnb-qq8-1k51guv63`，arm-linux-gnueabihf-gcc 14.2 + capstone 5.0.7；零 CI 额度）

### 二、完成事项

1. **P1（R182 待办 2）落地：`tools/dce_ref_diff.py` 接入工厂侧旁证，Δ 分诊自动化**：
   - 新增 `factory_blockread_hint(rel)`：按 TU 文件名解析对应**工厂函数**
     （`FUN_0002eac8_mui_load_state.c` → `mui_load_state`，剥 `.isra.N`/`.constprop.N` 分片后缀），
     跑 R182 的「被调函数间接读」分析，把块读调用点与覆盖槽附到 Δ 报告上（`<<工厂块读: …>>`）。
   - **旁证永不改变门禁结论**（不新增 hard-fail、不放宽任何一条）：文件名不匹配 / 无 symtab /
     无 ELF / 分析异常一律返回 None（优雅降级，绝不外抛）；`--no-factory-hint` 可关（A/B）。
   - 债务表（ALLOW）5 条现在**逐条自动附带**工厂侧块读实参清单 + 判定规则。

2. **P0 顺带修掉次数级判据的「码生成策略差」假阳（R183 实测定案）**：
   - 病灶：`-O0` 用 `movw+movt` **两条** reloc 物化一个符号地址，`-Os` 用字面量池 `.word` **一条**
     ⇒ 不归一时，「每条真实引用」在 -O0/-Os 之间**恒定差 1** ⇒ 次数级判据把策略差误报成"引用消失"
     （自证 ⑦ 因此 FAIL：两个不同符号各引用一次也报 -1）。
   - 修法：`reloc_counts` 改返回**物化点**数 —— 同符号、地址相差 4 的 movw/movt 对算**一个**点
     （`_count_sites`，模块级 `R_MOVW`/`R_MOVT` 类型表）。
   - 效果：`--count` 全量扫描的「引用次数下降」文件 **57 → 43**（消掉 14 个纯策略差假阳）。

3. **云机三重验证**：
   - `--self-test` **16 腿全过**（旧 6 + ⑥⑦ 次数级 + ⑧ 新增 8 腿：文件名提取 ×4 / 优雅降级 ×3 /
     已知答案 ×2 —— `mui_load_state` 旁证必含 `blockcopy`；`mui_menu` 旁证**不覆盖** b2320 槽 sp+0x1a4）；
   - 集合级全量门禁：**214 文件 / 0 编译失败 / 表外新增 Δ = 0 ⇒ PASS**；
   - 债务表 5 条的工厂侧旁证实测（见「新发现」）。

### 三、新发现与决策

1. **★ 5 条「合法 DCE」登记全部获工厂侧旁证支持（逐条算过，无重叠）**：

   | TU | b2320 槽（R179 实测） | 工厂侧块读实参覆盖槽 | 重叠？ |
   |---|---|---|---|
   | `mui_menu` | sp+0x1a4(#420) | filelist_run_game[sp+0x304]、FindZipItemA[sp+0x0] | **无** |
   | `mui_type` | sp+0x154(#340) | filelist_run_game[sp+0x358]、mui_LoadUIResource[sp+0x34] | **无** |
   | `mui_search` | sp+0x154(#340) | filelist_run_game[sp+0x358] | **无** |
   | `mui_recent` | sp+0x35c(#860) | popwindows/popoffwindows[sp+0x60..0x70 / sp+0x78..0x88] | **无** |
   | `mui_shoucang` | sp+0x1ac(#428) | popwindows/popoffwindows[sp+0x30..0x40]、filelist_run_game[sp+0x304] | **无** |

   ⇒ b2320 槽不在任何块读实参覆盖范围内 ⇒ 「写了从不读 ⇒ 合法 DCE」的 R179 结论**被独立判据交叉证实**。
2. **★ 次数级判据的噪声源是「码生成策略差」而非 CSE**（R183 更正 R180 的归因）：
   R180 把次数下降归因于"合法 CSE」，实测主因是 movw/movt（-O0）vs 字面量池（-Os）的
   **每条引用 2:1 的 reloc 数差**。归一后 ⑦ 反例（两个不同符号各一次）**真的**为空。
3. **决策**：工厂侧旁证只作**分诊信息**，不接入 pass/fail —— 因为它回答的是"原厂这些槽是否被读"，
   而"我方 -Os 是否真写了槽"要由产物侧 `verify_blk12.py` 回答；两把尺子互为交叉验证，不合并。

### 四、下一步待办

1. **P0 双远端推送**：R183 段 + `dce_ref_diff.py`（物化点归一 + 工厂旁证）+ `PROJECT-MEMORY.md` 纪律 167，
   推 GitHub + CNB（清单已含全部文件）。
2. **P1（可选）**：把 `--count` 的 43 个待核文件用同一把工厂旁证过一遍（现在只有集合级 Δ 文件挂了旁证），
   把「引用次数下降」清单也分成「疑似 UB-DCE / 疑似合法」两栏。
3. **P2**：B6 观测天花板突破（driver.so 私有画布）。
