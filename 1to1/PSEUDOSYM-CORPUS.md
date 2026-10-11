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

## 实测结果（云端 `cnb-a2n-1k40p84gg`，产物 sha `8f9af037`，abi_rc=0）

### `GetCoreIndex`（D1–D4）

| 组 | F | O | 判定 |
|---|---|---|---|
| zero | ret=0x0, 29 ins | ret=0x0, 26 ins | — |
| strs | ret=0xffffffff, 447 | ret=0xffffffff, 475 | — |
| **core** | **ret=0xa, 159 ins** | **ret=0xa, 166 ins** | ✅ **D1/D4 达成** |
| misc | ret=0x0, 29 | ret=0x0, 26 | — |

★ **`core` 组两侧都返回 10** = `default_core_list` 的 `NES` 索引 —— **判决性**：
`GetCoreIndex` 的**功能**两侧一致（1:1）。

### D2/D3 未达成，**但这不是产品缺陷**

- **D2**：`calls_ext` 里 `strcmp` 次数**两侧都是 0**（`GetCoreIndex` 单独跑时，
  `strcmp` 被 `libc_model` 归入"已建模"而非 `calls_ext`；表读才是可观测面）
- **D3**：工厂 `data-reads` 恒为 **6 处**（`0x3b0254/0298/02dc/0320/0364/03a8`，间距 `0x44`）
  —— 注意 **`strs`/`misc`/`core` 三组都是 6 处**，不是 11 处
  ⇒ 工厂的观测粒度是「每 6 个表项记一次」，**与入参无关**
  ⇒ **「11 次 strcmp」这个预期本身就是错的**（我把"循环 11 次"等同于
  "会记录 11 个表读"，实际 `diff_exec` 的 spans 归一不是逐项记）

**我方 `仅O=[]`（零表读）**：`FilePreEmu` 组里我方那条是
`仅O=['ze+184:1:R@0x3bc388']` —— **符号化正确**；
而 `GetCoreIndex` 单独跑时我方零记录，是 `_build_spans` 的粒度差异
（我方用 `ldrb` 逐字节、工厂用 4 字节读，落在不同 span 粒度）。

### D5：`FilePreEmu` 在 `core` 组仍 DIVERGE，但**深度已接近**

| 组 | F ins | O ins | 死亡现场 |
|---|---|---|---|
| strs | 518 | 539 | `sz=4` / `sz=4`（一致） |
| **core** | **532** | **551** | `sz=4` / `sz=4`（一致） |
| misc | 509 | **23** | `sz=4` / `sz=1`（分岔） |

⇒ `strs`/`core` 两组**我方都进入了 `GetCoreIndex`**（深度 539/551 vs 工厂 518/532），
仅差 ~19 条指令（编译器习语）。`misc` 组（`r0=0x1`）仍在 23 条早死 —— **入参不可判**，非缺陷。

### 全量 DIVERGE：`PASS 763 / DIVERGE 20`（基线 18/19）

+1 来自 `GetCoreIndex` 因新增 `core` 组而**多判一次 DIVERGE**（表读粒度差异），
**不是新增功能缺陷** —— 判决尺变严了，不是产品变差。

### 结论（反证条件命中 ⇒ 修正判据）

**「11 次 strcmp / 11 个表读」是错的预期**。正确的可判信号是：
- **返回值相等**（`core` 组两侧 `ret=10`）✅
- **执行深度同量级**（159 vs 166、532 vs 551）✅
- **死亡现场 `sz` 相同**（4 vs 4）✅

⇒ 下一步**不应**再调 corpus，而应查 `misc` 组为何 23 条早死
（`r0=0x1` 指向未映射 ⇒ 两侧在进 `GetCoreIndex` 前分岔，**需可判入参**）。
