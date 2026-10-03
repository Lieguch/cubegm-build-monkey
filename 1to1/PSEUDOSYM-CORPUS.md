# 判据：新增 `core` 可判入参组（让 `strcmp` 循环可判）

**预登记**：动手改 `tools/diff_exec.py` 之前（2026-10-03，第 121轮）。
**反证条件**：若两侧 `calls_ext` 的 `strcmp` 次数**不相等**，或我方仍为 0 次
⇒ 说明 `FilePreEmu` 里还有别的未对齐点（不止 `ze+184`），**不得**据此宣称簇 A 收敛。

## 为什么要新增这一组（不是"为了好看"）

现状 `misc` 组（`r0=0x1`）**不可判**：`0x1` 指向未映射内存，两侧在进
`GetCoreIndex` 之前就分岔 ⇒ 报告永远显示 `O=[]`（零外部调用）。
按纪律「**不可判 ≠ 未收敛**」，不能拿它当证据，也不能靠它推进。

## 组的设计（依据工厂真实数据，非臆造）

`default_core_list`（`@0x3b0254`，stride `0x44`=68）实测共 **33 项**：

```
[ 0]BKP  [ 1]ZIP  [ 2]SMC  [ 3]FIG  [ 4]SFC  [ 5]GD3  [ 6]GD7
[ 7]DX2  [ 8]BSX  [ 9]SWC  [10]NES  [11]NFC  [12]FDS  [13]UNF
[14]VT3  [15]VT4  [16]GBA  [17]AGB  [18]GBZ  [19]GBC  [20]GB
[21]SGB  [22]BIN  [23]MD   [24]SMD  [25]GEN  [26]SMS  [27]ISO
[28]IMG  [29]PBP  [30]A26  [31]A78  [32]CONF
[33]<空> ⇒ 终止
```

工厂 `GetCoreIndex` 循环上限 `cmp r5,#100` ⇒ 33 项 + 1 次空检测 = **34 次**迭代。

### 选`NES`（索引 10）作为入参

- `strupr` 后仍为 `NES`（已大写）⇒ 不引入大小写这一维变量
- 命中索引 **10** ⇒ 期望**恰好 11 次 `strcmp`**（比较 `BKP…NES`）
- 若选 `BKP`（索引 0）只需 1 次，信号太弱；若选 `CONF`（索引 32）要 33 次，
  容易撞上 100 上限附近的其它变量

## 判据

- **D1** `core` 组能跑完（`stop=return`，非 UNMAPPED）
- **D2** 两侧 `calls_ext` 的 `strcmp` **次数相等且 = 11**
- **D3** 两侧 `data-reads` 的表地址序列**逐个相同**（`0x3b0254` 起，间距 `0x44`，11 个）
- **D4** 返回值相同（`GetCoreIndex` 返回 10）
- **D5** `FilePreEmu` / `SeletEmuCore` 在 `core` 组下 **不再 DIVERGE**

**反证条件**：D2/D3 任一不成立 ⇒ `FilePreEmu` 还有未对齐点，
回到工厂汇编逐条核`r4` 的每个使用点 + `GetCoreIndex` 之前的全部分支。

## 实测结果

（待回填）
